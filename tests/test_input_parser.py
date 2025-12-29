import json
import logging
import pytest

from langchain_core.messages import AIMessage, HumanMessage

from src.agents.input_parser_agent import InputParsingAgent


class StubRunnable:
    """Minimal stub for self.agent that supports .ainvoke()."""

    def __init__(self, content: str):
        self._content = content

    async def ainvoke(self, _input):
        return AIMessage(content=self._content)


@pytest.fixture
def logger():
    lg = logging.getLogger("test.input_parser")
    if not lg.handlers:
        lg.addHandler(logging.NullHandler())
    lg.setLevel(logging.DEBUG)
    return lg


@pytest.fixture
def parser_agent(logger):
    # Dummy llm (won't be used because we overwrite agent.agent with StubRunnable)
    dummy_llm = lambda x: AIMessage(content="{}")
    agent = InputParsingAgent(llm=dummy_llm, logger=logger)
    return agent


def _base_state(**overrides):
    state = {
        "messages": [HumanMessage(content="Draft an email to my recruiter asking for an update.")],
        "raw_input": "Draft an email to my recruiter asking for an update.",
        "requires_clarification": False,
        "parsed_input": {},
        "constraints": {},
        "tone_params": {},  # may be set by workflow/UI
        "validation_report": {},
        "retry_count": 0,
    }
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_input_parser_success_no_clarification(parser_agent):
    parser_agent.agent = StubRunnable(
        content=json.dumps(
            {
                "requires_clarification": False,
                "clarification_questions": [],
                "parsed_input": {
                    "primary_request": "Ask recruiter for application status update",
                    "recipient": {"role": "recruiter"},
                },
                "constraints": {"length": "short"},
                # If your InputParsingAgent prompt still outputs these fields, they can exist.
                # The agent should ignore or not include them in updates (depending on your current code).
                "tone_params": {},
            }
        )
    )

    state = _base_state()
    msgs, updates = await parser_agent._execute(state)

    assert isinstance(msgs, list) and msgs
    assert updates.get("requires_clarification") is False
    assert isinstance(updates.get("parsed_input"), dict)
    assert updates["parsed_input"].get("primary_request")
    assert isinstance(updates.get("constraints"), dict)
    assert updates["constraints"].get("length") == "short"

    # You typically set validation_report={"status":"OK"} on success.
    vr = updates.get("validation_report") or {}
    assert vr.get("status") in {"OK", "PASS", None}  # allow slight variance


@pytest.mark.asyncio
async def test_input_parser_requires_clarification(parser_agent):
    parser_agent.agent = StubRunnable(
        content=json.dumps(
            {
                "requires_clarification": True,
                "clarification_questions": [
                    "Who is the recipient (name/role) and your relationship?",
                    "What is the main goal of the email?",
                ],
                "parsed_input": {},
                "constraints": {},
                "tone_params": {},
            }
        )
    )

    state = _base_state()
    msgs, updates = await parser_agent._execute(state)

    assert updates.get("requires_clarification") is True

    # Should return a user-facing message with questions
    assert isinstance(msgs, list) and msgs
    assert isinstance(msgs[0], AIMessage)
    assert "I need a bit more information" in msgs[0].content

    vr = updates.get("validation_report") or {}
    assert vr.get("status") == "NEEDS_CLARIFICATION"
    assert isinstance(vr.get("questions"), list)
    assert len(vr.get("questions")) >= 1


@pytest.mark.asyncio
async def test_input_parser_non_json_fails_soft(parser_agent):
    # Non-JSON output (common LLM failure) should not crash the graph.
    parser_agent.agent = StubRunnable(content="**PASS** Not JSON.")

    state = _base_state()
    msgs, updates = await parser_agent._execute(state)

    assert updates.get("requires_clarification") is True
    assert updates.get("parsed_input") == {}
    assert updates.get("constraints") == {}

    vr = updates.get("validation_report") or {}
    assert vr.get("status") == "NEEDS_CLARIFICATION"
    assert "questions" in vr
    assert isinstance(vr["questions"], list)
    assert len(vr["questions"]) >= 1

    assert isinstance(msgs, list) and msgs
    assert "I need a bit more information" in msgs[0].content


@pytest.mark.asyncio
async def test_input_parser_does_not_overwrite_ui_tone(parser_agent):
    """
    This enforces your architectural choice:
    InputParsingAgent should NOT clobber UI-provided tone_params.
    """
    parser_agent.agent = StubRunnable(
        content=json.dumps(
            {
                "requires_clarification": False,
                "clarification_questions": [],
                "parsed_input": {"primary_request": "Ask recruiter for update"},
                "constraints": {"length": "short"},
                # Even if model outputs this, InputParsingAgent should not update it.
                "tone_params": {},
            }
        )
    )

    state = _base_state(tone_params={"tone_label": "formal"})

    msgs, updates = await parser_agent._execute(state)

    # Assert that the parser did not emit tone_params updates.
    # If your implementation still returns "tone_params" in updates, this test will fail
    # (and that's a signal to remove it from InputParsingAgent updates).
    assert "tone_params" not in updates, "InputParsingAgent should not overwrite or set tone_params"

    # Ensure original state isn't assumed overwritten by updates
    assert state.get("tone_params", {}).get("tone_label") == "formal"
