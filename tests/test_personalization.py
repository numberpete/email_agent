import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.personalization_agent import PersonalizationAgent
from src.profiles.sqlite_profile_store import SQLiteProfileStore
from src.memory.sqlite_memory_store import SQLiteMemoryStore
from tests.utils.mock_llm import MOCK_LLM

class DummyLogger:
    def debug(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass


class FakeChain:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_input = None

    async def ainvoke(self, inp):
        self.last_input = inp
        return AIMessage(content=self.response_text)


@pytest.mark.asyncio
async def test_personalizer_loads_profile_and_updates_user_context(tmp_path):
    db = tmp_path / "test.db"
    store = SQLiteProfileStore(str(db))
    mem_store = SQLiteMemoryStore(str(db))
    store.upsert_profile("default", {"name": "Peter Hanus", "title": "Principal Site Reliability Developer"})

    agent = PersonalizationAgent(llm=MOCK_LLM, logger=DummyLogger(), profile_store=store, memory_store=mem_store)
    agent.agent = FakeChain('{"personalized_draft":"Hi.\\n\\nThanks,\\nPeter Hanus","memory_updates":{}}')

    state = {
        "messages": [HumanMessage(content="draft email")],
        "user_id": "default",
        "draft": "Hi.\n\nThanks,\n[Your Name]",
        "parsed_input": {},
    }

    _, updates = await agent._execute(state)

    assert updates["personalized_draft"]
    assert updates["user_context"]["name"] == "Peter Hanus"
    assert updates["memory_updates"] == {}


@pytest.mark.asyncio
async def test_personalizer_fail_soft_on_non_json(tmp_path):
    db = tmp_path / "test.db"
    store = SQLiteProfileStore(str(db))
    mem_store = SQLiteMemoryStore(str(db))

    store.upsert_profile("default", {"name": "Peter Hanus"})

    agent = PersonalizationAgent(llm=MOCK_LLM, logger=DummyLogger(), profile_store=store, memory_store=mem_store)
    agent.agent = FakeChain("NOT JSON")

    draft = "Hi.\n\nThanks,\n[Your Name]"
    state = {
        "messages": [HumanMessage(content="draft email")],
        "user_id": "default",
        "draft": draft,
        "parsed_input": {},
    }

    _, updates = await agent._execute(state)

    assert updates["personalized_draft"] == draft
    assert updates["user_context"]["name"] == "Peter Hanus"
