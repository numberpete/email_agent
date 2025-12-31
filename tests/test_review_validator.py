import json
import pytest

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from src.agents.review_validator_agent import ReviewValidatorAgent
from tests.utils.mock_llm import MOCK_LLM


class DummyLogger:
    def debug(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass


class FakeChain:
    """Async stub that mimics .ainvoke() and returns an AIMessage."""
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_input = None

    async def ainvoke(self, inp):
        self.last_input = inp
        return AIMessage(content=self.response_text)


@pytest.mark.asyncio
async def test_validator_pass_persists_revision_instructions_and_is_valid():  
    agent = ReviewValidatorAgent(llm=MOCK_LLM, logger=DummyLogger())

    model_json = {
        "status": "PASS",
        "summary": "Looks good.",
        "issues": [],
        "suggested_edits": {"apply_minor_fixes": True, "recommended_tone": None},
        "revision_instructions": "",
    }
    agent.agent = FakeChain(json.dumps(model_json))

    state = {
        "messages": [HumanMessage(content="write email")],
        "draft": "Hello\n\nThanks,\nPeter",
        "personalized_draft": "Hello Jordan,\n\nThanks,\nPeter",
        "tone_params": {"tone_label": "formal"},
        "intent": "request",
        "constraints": {"length": "short"},
    }

    msgs, updates = await agent._execute(state)

    assert len(msgs) == 1
    assert "validation_report" in updates
    assert updates["is_valid"] is True

    report = updates["validation_report"]
    assert report["status"] == "PASS"
    assert report["revision_instructions"] == ""
    assert isinstance(report["issues"], list)


@pytest.mark.asyncio
async def test_validator_fail_includes_revision_instructions_and_is_invalid():
    agent = ReviewValidatorAgent(llm=MOCK_LLM, logger=DummyLogger())

    model_json = {
        "status": "FAIL",
        "summary": "Tone is too aggressive.",
        "issues": [
            {
                "category": "tone",
                "severity": "high",
                "detail": "The language is confrontational.",
                "suggested_fix": "Use neutral phrasing.",
            }
        ],
        "suggested_edits": {"apply_minor_fixes": False, "recommended_tone": "professional"},
        "revision_instructions": "Rewrite the email with a calmer, professional tone; remove confrontational phrasing.",
    }
    agent.agent = FakeChain(json.dumps(model_json))

    state = {
        "messages": [HumanMessage(content="email")],
        "draft": "Fix this now or else.",
        "tone_params": {"tone_label": "assertive"},
        "intent": "request",
        "constraints": {},
    }

    _, updates = await agent._execute(state)

    report = updates["validation_report"]
    assert report["status"] == "FAIL"
    assert updates["is_valid"] is False
    assert "revision_instructions" in report
    assert report["revision_instructions"].startswith("Rewrite")


@pytest.mark.asyncio
async def test_validator_high_severity_casing_forces_fail():
    agent = ReviewValidatorAgent(llm=MOCK_LLM, logger=DummyLogger())

    # Model returns PASS but includes "High" severity issue -> must coerce to FAIL
    model_json = {
        "status": "PASS",
        "summary": "Seems okay.",
        "issues": [
            {
                "category": "clarity",
                "severity": "High",
                "detail": "Unclear ask.",
                "suggested_fix": "State the request explicitly.",
            }
        ],
        "suggested_edits": {"apply_minor_fixes": False, "recommended_tone": None},
        "revision_instructions": "Clarify the request and make the ask explicit.",
    }
    agent.agent = FakeChain(json.dumps(model_json))

    state = {
        "messages": [HumanMessage(content="email")],
        "draft": "We should do it.",
        "constraints": {},
        "tone_params": {},
        "intent": "other",
    }

    _, updates = await agent._execute(state)

    report = updates["validation_report"]
    assert report["status"] == "FAIL"
    assert updates["is_valid"] is False


@pytest.mark.asyncio
async def test_validator_fail_without_revision_instructions_gets_default():
    agent = ReviewValidatorAgent(llm=MOCK_LLM, logger=DummyLogger())

    model_json = {
        "status": "FAIL",
        "summary": "Needs work.",
        "issues": [{"category": "other", "severity": "medium", "detail": "Vague.", "suggested_fix": None}],
        "suggested_edits": {"apply_minor_fixes": False, "recommended_tone": None},
        "revision_instructions": "",
    }
    agent.agent = FakeChain(json.dumps(model_json))

    state = {
        "messages": [HumanMessage(content="email")],
        "draft": "Thing.",
        "constraints": {},
        "tone_params": {},
        "intent": "other",
    }

    _, updates = await agent._execute(state)
    report = updates["validation_report"]

    assert report["status"] == "FAIL"
    assert updates["is_valid"] is False
    assert report["revision_instructions"]  # non-empty default added


@pytest.mark.asyncio
async def test_validator_non_json_output_fails_soft_and_shape_is_stable():
    agent = ReviewValidatorAgent(llm=MOCK_LLM, logger=DummyLogger())

    agent.agent = FakeChain("**PASS** Looks great")  # not JSON

    state = {
        "messages": [HumanMessage(content="email")],
        "draft": "Hello",
        "constraints": {},
        "tone_params": {},
        "intent": "info",
    }

    msgs, updates = await agent._execute(state)

    assert updates["is_valid"] is False
    report = updates["validation_report"]
    assert report["status"] == "FAIL"
    assert "revision_instructions" in report
    assert isinstance(report["issues"], list)
    assert len(msgs) == 1  # the FAIL-soft AIMessage


@pytest.mark.asyncio
async def test_validator_sends_reduced_state_json_payload():
    agent = ReviewValidatorAgent(llm=MOCK_LLM, logger=DummyLogger())

    # Minimal PASS response
    agent.agent = FakeChain(
        json.dumps(
            {
                "status": "PASS",
                "summary": "OK",
                "issues": [],
                "suggested_edits": {"apply_minor_fixes": True, "recommended_tone": None},
                "revision_instructions": "",
            }
        )
    )

    state = {
        "messages": [HumanMessage(content="email")],
        "draft": "draft",
        "personalized_draft": "personalized",
        "tone_params": {"tone_label": "formal"},
        "intent": "follow_up",
        "constraints": {"length": "short"},
        "user_context": {"name": "Peter"},  # should NOT be included in reduced payload
        "memory_updates": {"foo": "bar"},   # should NOT be included
    }

    await agent._execute(state)

    # Validate that the agent invoked the chain with state_json that only contains the reduced keys.
    assert agent.agent.last_input is not None
    assert "state_json" in agent.agent.last_input

    raw_state_json = agent.agent.last_input["state_json"]
    payload = raw_state_json if isinstance(raw_state_json, dict) else json.loads(raw_state_json)
    assert set(payload.keys()) == {"draft", "tone_params", "intent", "constraints"}
    assert payload["draft"] == "personalized"

@pytest.mark.asyncio
async def test_validator_passes_on_clean_draft():
    agent = ReviewValidatorAgent(llm=MOCK_LLM, logger=DummyLogger())

    # Force the agent to use our stub chain instead of a real LLM runnable
    agent.agent = FakeChain(
        json.dumps(
            {
                "status": "PASS",
                "summary": "Looks good.",
                "issues": [],
                "suggested_edits": {"apply_minor_fixes": True, "recommended_tone": None},
                "revision_instructions": "",
            }
        )
    )

    state = {
        "messages": [HumanMessage(content="Write an email")],
        "draft": "Hello Jordan,\n\nCould you please replace the item?\n\nThanks,\nPeter",
        "personalized_draft": "",
        "tone_params": {"tone_label": "formal"},
        "intent": "request",
        "constraints": {},
    }

    _, updates = await agent._execute(state)

    report = updates["validation_report"]
    assert report["status"] == "PASS"
    assert updates["is_valid"] is True
    assert report.get("revision_instructions", "") == ""


@pytest.mark.asyncio
async def test_validator_fails_when_high_severity_issue_present():
    agent = ReviewValidatorAgent(llm=MOCK_LLM, logger=DummyLogger())
    agent.agent = FakeChain(
        json.dumps(
            {
                "status": "PASS",  # model claims PASS
                "summary": "But actually there is a major issue.",
                "issues": [
                    {
                        "category": "tone",
                        "severity": "high",
                        "detail": "Overly aggressive / insulting.",
                        "suggested_fix": "Soften and remove insults.",
                    }
                ],
                "suggested_edits": {"apply_minor_fixes": False, "recommended_tone": "professional"},
                "revision_instructions": "Rewrite without insults; keep professional tone.",
            }
        )
    )

    state = {
        "messages": [HumanMessage(content="Write an email")],
        "draft": "You are an idiot. Replace it now.",
        "tone_params": {"tone_label": "assertive"},
        "intent": "request",
        "constraints": {},
    }

    _, updates = await agent._execute(state)
    report = updates["validation_report"]

    # Your agent enforces FAIL if any high severity issue exists
    assert report["status"] == "FAIL"
    assert updates["is_valid"] is False


@pytest.mark.asyncio
async def test_validator_non_json_output_fails_soft_and_shape_is_stable():
    agent = ReviewValidatorAgent(llm=MOCK_LLM, logger=DummyLogger())

    # Return non-JSON on purpose
    agent.agent = FakeChain("**PASS** Looks fine")  # invalid JSON

    state = {
        "messages": [HumanMessage(content="Write an email")],
        "draft": "Hello Jordan,\n\nThanks.\n\nPeter",
        "tone_params": {"tone_label": "formal"},
        "intent": "info",
        "constraints": {},
    }

    _, updates = await agent._execute(state)
    report = updates["validation_report"]

    assert report["status"] == "FAIL"
    assert updates["is_valid"] is False

    # Ensure stable shape keys you rely on
    assert "issues" in report
    assert "suggested_edits" in report
    assert "revision_instructions" in report


@pytest.mark.asyncio
async def test_validator_reduced_payload_contains_expected_keys():
    agent = ReviewValidatorAgent(llm=MOCK_LLM, logger=DummyLogger())
    agent.agent = FakeChain(
        json.dumps(
            {
                "status": "PASS",
                "summary": "OK",
                "issues": [],
                "suggested_edits": {"apply_minor_fixes": True, "recommended_tone": None},
                "revision_instructions": "",
            }
        )
    )

    state = {
        "messages": [HumanMessage(content="Write an email")],
        "draft": "DRAFT",
        "personalized_draft": "PERSONALIZED",
        "tone_params": {"tone_label": "friendly"},
        "intent": "other",
        "constraints": {"use_bullets": False},
    }

    await agent._execute(state)

    # The validator should see only the reduced payload as state_json
    raw_state_json = agent.agent.last_input["state_json"]
    payload = raw_state_json if isinstance(raw_state_json, dict) else json.loads(raw_state_json)

    assert set(payload.keys()) == {"draft", "tone_params", "intent", "constraints"}
    assert payload["draft"] == "PERSONALIZED"
    assert payload["constraints"]["use_bullets"] is False