import pytest

from langchain_core.messages import AIMessage, HumanMessage

from src.agents.draft_writer_agent import DraftWriterAgent
from src.templates.engine import EmailTemplateEngine


class DummyLogger:
    def debug(self, *args, **kwargs):  # pragma: no cover
        pass

    def info(self, *args, **kwargs):  # pragma: no cover
        pass


class FakeChain:
    """Captures payload passed to .ainvoke and returns a fixed AIMessage."""

    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_input = None

    async def ainvoke(self, inp):
        self.last_input = inp
        return AIMessage(content=self.response_text)


class DummyStore:
    def __init__(self, tpl=None):
        self.tpl = tpl

    def get_best_template(self, *, intent, tone_label, constraints):
        return self.tpl


@pytest.mark.asyncio
async def test_draft_writer_sets_draft_template_id_and_plan():
    tpl = {
        "template_id": "follow_up_neutral_v1",
        "intent": "follow_up",
        "tone_label": "neutral",
        "name": "Follow-up Neutral",
        "body": "Subject: {{subject}}\n\n{{greeting}}\n\n{{ask}}\n\n{{closing}}\n{{signature}}\n",
        "meta": {"version": 1},
    }
    engine = EmailTemplateEngine(DummyStore(tpl))

    writer = DraftWriterAgent(llm=None, logger=DummyLogger(), template_engine=engine)
    fake = FakeChain("Subject: Following up\n\nHi,\n\nJust checking in.\n\nThanks,\nPeter")
    writer.agent = fake  # override the LC runnable

    state = {
        "messages": [HumanMessage(content="Follow up with the recruiter about my application.")],
        "intent": "follow_up",
        "tone_params": {"tone_label": "neutral"},
        "constraints": {"length": "short"},
        "parsed_input": {"primary_request": "Following up", "ask": "Could you share an update?"},
    }

    msgs, updates = await writer._execute(state)

    # Draft is present
    assert isinstance(updates["draft"], str)
    assert updates["draft"].startswith("Subject:")

    # Template id is set from plan (or empty string if missing)
    assert updates["template_id"] == "follow_up_neutral_v1"

    # Plan is included for debug panels
    assert isinstance(updates["template_plan"], dict)
    assert updates["template_plan"].get("template_id") == "follow_up_neutral_v1"

    # Chain invocation contract
    assert fake.last_input is not None
    assert "messages" in fake.last_input
    assert "state_json" in fake.last_input
    assert isinstance(fake.last_input["messages"], list)
    assert len(fake.last_input["messages"]) == 1

    # Return includes the response message
    assert msgs and isinstance(msgs[0], AIMessage)


@pytest.mark.asyncio
async def test_draft_writer_empty_template_id_when_no_template_found():
    engine = EmailTemplateEngine(DummyStore(None))

    writer = DraftWriterAgent(llm=None, logger=DummyLogger(), template_engine=engine)
    writer.agent = FakeChain("Subject: Message\n\nHello,\n\nHere is the email.\n\nThanks,\n[Your Name]")

    state = {
        "messages": [HumanMessage(content="Write an email asking for help.")],
        "intent": "request",
        "tone_params": {},
        "constraints": {},
        "parsed_input": {},
    }

    _, updates = await writer._execute(state)

    assert updates["draft"]
    assert updates["template_id"] == ""  # per your code
    assert isinstance(updates["template_plan"], dict)
    assert updates["template_plan"].get("template_id") in {None, ""}


@pytest.mark.asyncio
async def test_draft_writer_provides_non_empty_state_json_to_model():
    tpl = {
        "template_id": "request_formal_v1",
        "intent": "request",
        "tone_label": "formal",
        "name": "Request Formal",
        "body": "Subject: {{subject}}\n\n{{greeting}}\n\n{{ask}}\n\n{{closing}}\n{{signature}}\n",
        "meta": {"version": 1},
    }
    engine = EmailTemplateEngine(DummyStore(tpl))

    writer = DraftWriterAgent(llm=None, logger=DummyLogger(), template_engine=engine)
    fake = FakeChain("Subject: Request\n\nHello,\n\nCould you approve this?\n\nThank you,\n[Your Name]")
    writer.agent = fake

    state = {
        "messages": [HumanMessage(content="Ask my manager to approve my access request.")],
        "intent": "request",
        "tone_params": {"tone_label": "formal"},
        "constraints": {"length": "short"},
        "parsed_input": {"ask": "approve my access request"},
    }

    await writer._execute(state)

    sj = fake.last_input.get("state_json")
    assert isinstance(sj, str)
    assert sj.strip()  # non-empty
