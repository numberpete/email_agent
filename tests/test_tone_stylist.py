import json
import logging
import pytest

from langchain_core.messages import AIMessage, HumanMessage

from src.agents.tone_stylist_agent import ToneStylistAgent


class StubRunnable:
    """Minimal stub for self.agent that supports .ainvoke()."""

    def __init__(self, content: str):
        self._content = content

    async def ainvoke(self, _input):
        return AIMessage(content=self._content)


@pytest.fixture
def logger():
    lg = logging.getLogger("test.tone_stylist")
    if not lg.handlers:
        lg.addHandler(logging.NullHandler())
    lg.setLevel(logging.DEBUG)
    return lg


@pytest.fixture
def tone_agent(logger):
    # Construct agent with any LLM (will be replaced by StubRunnable anyway)
    # We pass a trivial callable so BaseAgent __init__ can build a prompt|llm chain
    # but we will override agent.agent in each test for deterministic output.
    dummy_llm = lambda x: AIMessage(content="{}")  # sync callable is fine; we override below
    agent = ToneStylistAgent(llm=dummy_llm, logger=logger)
    return agent


def _base_state(**overrides):
    state = {
        "messages": [HumanMessage(content="Please draft an email to my recruiter.")],
        "raw_input": "Please draft an email to my recruiter.",
        "parsed_input": {},
        "constraints": {},
        "tone_params": {},
        "requires_clarification": False,
        "draft": "",
        "personalized_draft": "",
        "validation_report": {},
        "retry_count": 0,
    }
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_tone_ui_override_used(tone_agent):
    # UI override is authoritative when tone_params has a tone_label
    state = _base_state(tone_params={"tone_label": "formal"})

    # Even if model would say something else, override should win.
    tone_agent.agent = StubRunnable(
        content=json.dumps(
            {
                "tone_params": {
                    "tone_label": "friendly",
                    "formality": 10,
                    "warmth": 90,
                    "directness": 40,
                    "confidence": 0.9,
                    "do": ["be warm"],
                    "dont": ["be stiff"],
                    "lexical_hints": {"greetings": ["Hey"], "closings": ["Cheers"], "phrases": ["Just checking in"]},
                },
                "reason": "model output",
            }
        )
    )

    msgs, updates = await tone_agent._execute(state)

    assert isinstance(msgs, list) and msgs
    assert updates["tone_source"] == "ui"
    assert updates["tone_params"]["tone_label"] == "formal"


@pytest.mark.asyncio
async def test_tone_model_json_normalizes_fields(tone_agent):
    # Model returns valid JSON but with missing / weird fields; agent should normalize/clamp.
    tone_agent.agent = StubRunnable(
        content=json.dumps(
            {
                "tone_params": {
                    "tone_label": "friendly",
                    "formality": 150,         # should clamp to 100
                    "warmth": -10,            # should clamp to 0
                    "directness": "80",       # should coerce to int
                    "confidence": 1.5,        # should clamp to 1.0
                    "do": "not-a-list",       # should become []
                    "dont": None,             # should become []
                    "lexical_hints": "oops",  # should become dict with lists
                },
                "reason": "Implied friendly tone.",
            }
        )
    )

    state = _base_state(tone_params={})  # (auto)
    msgs, updates = await tone_agent._execute(state)

    tp = updates["tone_params"]
    assert updates["tone_source"] == "model"
    assert tp["tone_label"] == "friendly"
    assert tp["formality"] == 100
    assert tp["warmth"] == 0
    assert tp["directness"] == 80
    assert tp["confidence"] == 1.0
    assert isinstance(tp["do"], list)
    assert isinstance(tp["dont"], list)
    assert isinstance(tp["lexical_hints"], dict)
    assert isinstance(tp["lexical_hints"].get("greetings"), list)
    assert isinstance(tp["lexical_hints"].get("closings"), list)
    assert isinstance(tp["lexical_hints"].get("phrases"), list)


@pytest.mark.asyncio
async def test_tone_non_json_fails_soft_to_default(tone_agent):
    # Model returns non-JSON -> agent should fail-soft to default neutral
    tone_agent.agent = StubRunnable(content="**PASS** this is not JSON")

    state = _base_state(tone_params={})
    msgs, updates = await tone_agent._execute(state)

    assert updates["tone_source"] == "default"
    assert updates["tone_params"]["tone_label"] == "neutral"
    # Ensure some expected default structure exists
    assert "lexical_hints" in updates["tone_params"]
    assert isinstance(updates["tone_params"]["lexical_hints"], dict)


@pytest.mark.asyncio
async def test_tone_empty_tone_params_fails_soft_to_default(tone_agent):
    # Model returns valid JSON but empty tone_params -> fail-soft to default neutral
    tone_agent.agent = StubRunnable(
        content=json.dumps(
            {
                "tone_params": {},
                "reason": "Could not determine tone.",
            }
        )
    )

    state = _base_state(tone_params={})
    msgs, updates = await tone_agent._execute(state)

    # This assumes you implemented the "empty tone_params => default" behavior (#3).
    assert updates["tone_source"] == "default"
    assert updates["tone_params"]["tone_label"] == "neutral"
