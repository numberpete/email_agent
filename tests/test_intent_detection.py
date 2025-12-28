import pytest
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.agents.intent_detection_agent import IntentDetectionAgent


@pytest.mark.asyncio
async def test_intent_follow_up_auto():
    logger = logging.getLogger("IntentTest")
    logger.setLevel(logging.DEBUG)

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    agent = IntentDetectionAgent(llm, logger)

    state = {
        "messages": [
            HumanMessage(content="Please follow up with my recruiter about the timeline.")
        ],
        "parsed_input": {},
        "constraints": {},
        "tone_params": {},
    }

    result = await agent.run(state)

    updates = result.updates

    assert updates["intent"] == "follow_up"
    assert 0.0 <= updates["intent_confidence"] <= 1.0
    assert updates["intent_source"] == "model"

@pytest.mark.asyncio
async def test_intent_ui_override():
    logger = logging.getLogger("IntentTest")

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    agent = IntentDetectionAgent(llm, logger)

    state = {
        "messages": [
            HumanMessage(content="This text should be ignored.")
        ],
        "user_intent_override": "apology",
    }

    result = await agent.run(state)
    updates = result.updates

    assert updates["intent"] == "apology"
    assert updates["intent_confidence"] == 1.0
    assert updates["intent_source"] == "ui"

@pytest.mark.asyncio
async def test_intent_alias_follow_up():
    logger = logging.getLogger("IntentTest")

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    agent = IntentDetectionAgent(llm, logger)

    # This phrasing often yields "follow up"
    state = {
        "messages": [
            HumanMessage(content="Write a follow up email to my manager.")
        ],
    }

    result = await agent.run(state)
    updates = result.updates

    assert updates["intent"] == "follow_up"
