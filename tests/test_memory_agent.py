import json
import pytest
from langchain_core.messages import HumanMessage

from src.agents.memory_agent import MemoryAgent
from src.agents.personalization_agent import PersonalizationAgent
from tests.utils.mock_llm import MOCK_LLM
from src.utils.recipient import compute_recipient_key


class DummyLogger:
    def debug(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass


class FakeResp:
    def __init__(self, content: str):
        self.content = content


class FakeChain:
    """Simple fake Runnable/Chain that returns fixed .content and captures input."""
    def __init__(self, content: str):
        self._content = content
        self.last_input = None

    async def ainvoke(self, input_, config=None):
        self.last_input = input_
        return FakeResp(self._content)


class InMemoryStore:
    """Test double matching your sqlite_memory_store interface."""
    def __init__(self):
        self._data = {}

    def get_past_summary(self, user_id: str, recipient_key: str):
        return self._data.get((user_id, recipient_key))

    def upsert_summary(self, user_id: str, recipient_key: str, summary):
        self._data[(user_id, recipient_key)] = summary

class InProfileStore:
    """Test double matching your sqlite_profile_store interface."""
    def __init__(self):
        self._data = {}

    def get_profile(self, user_id: str):
        return self._data.get(user_id, {})

    def upsert_profile(self, user_id: str, profile: dict):
        self._data[user_id] = profile


@pytest.mark.asyncio
async def test_memory_agent_skips_persist_when_not_pass():
    store = InMemoryStore()
    agent = MemoryAgent(llm=MOCK_LLM, logger=DummyLogger(), memory_store=store)

    # even if model would return valid JSON, we should skip on FAIL
    agent.agent = FakeChain(json.dumps({"summary": {"relationship": None, "history": ["x"], "last_intent": "info", "last_tone": "formal"}}))

    state = {
        "messages": [HumanMessage(content="write an email")],
        "validation_report": {"status": "FAIL"},
        "user_id": "u1",
        "parsed_input": {"recipient": {"name": "Alice", "role": None, "relationship": None}},
        "draft": "Hello",
        "personalized_draft": "Hello",
        "intent": "info",
        "tone_params": {"tone_label": "formal"},
        "constraints": {},
    }

    msgs, updates = await agent._execute(state)

    assert store.get_past_summary("u1", "Alice") is None
    assert msgs == []
    assert updates == {}


@pytest.mark.asyncio
async def test_memory_agent_persists_on_pass_and_calls_llm_with_existing_summary():
    store = InMemoryStore()
    recipient_key=compute_recipient_key({"name": "Alice"})
    store.upsert_summary(
        "u1",
        recipient_key,
        {
            "relationship": "Recruiter",
            "history": ["Initial outreach sent."],
            "last_intent": "outreach",
            "last_tone": "friendly",
        },
    )

    agent = MemoryAgent(llm=MOCK_LLM, logger=DummyLogger(), memory_store=store)

    agent.agent = FakeChain(
        json.dumps(
            {
                "summary": {
                    "relationship": "Recruiter",
                    "history": ["Initial outreach sent.", "Follow-up sent."],
                    "last_intent": "follow_up",
                    "last_tone": "professional",
                }
            }
        )
    )

    state = {
        "messages": [HumanMessage(content="follow up with recruiter")],
        "validation_report": {"status": "PASS"},
        "user_id": "u1",
        "parsed_input": {"recipient": {"name": "Alice", "role": None, "relationship": None}},
        "draft": "Hi Alice, just following up...",
        "personalized_draft": "Hi Alice, just following up...",
        "intent": "follow_up",
        "tone_params": {"tone_label": "professional"},
        "constraints": {},
    }

    msgs, updates = await agent._execute(state)

    # upsert happened
    saved = store.get_past_summary("u1", recipient_key)
    assert saved is not None
    assert saved["last_intent"] == "follow_up"
    assert isinstance(saved["history"], list)
    assert "Follow-up sent." in saved["history"]

    # ensure LLM saw existing summary (code path correctness)
    assert agent.agent.last_input is not None
    state_json = agent.agent.last_input.get("state_json", {})
    assert state_json.get("existing_summary") is not None
    assert state_json["existing_summary"]["relationship"] == "Recruiter"


@pytest.mark.asyncio
async def test_personalization_agent_includes_past_summary_in_state_json():
    store = InMemoryStore()
    store.upsert_summary(
        "u1",
        compute_recipient_key({"name": "Alice"}),
        {
            "relationship": "Recruiter",
            "history": ["Initial outreach sent."],
            "last_intent": "outreach",
            "last_tone": "friendly",
        },
    )

    agent = PersonalizationAgent(llm=MOCK_LLM, logger=DummyLogger(), profile_store=InProfileStore(), memory_store=store)

    # We don't care about content here; we care that past_summary is included in state_json
    agent.agent = FakeChain("OK")

    state = {
        "messages": [HumanMessage(content="follow up")],
        "user_id": "u1",
        "parsed_input": {"recipient": {"name": "Alice", "role": None, "relationship": None}},
        "draft": "Hi Alice...",
        "intent": "follow_up",
        "tone_params": {"tone_label": "professional"},
        "constraints": {},
    }

    msgs, updates = await agent._execute(state)

    assert agent.agent.last_input is not None
    sj = agent.agent.last_input.get("state_json", {})
    assert sj.get("past_summary") is not None
    assert sj["past_summary"]["relationship"] == "Recruiter"
