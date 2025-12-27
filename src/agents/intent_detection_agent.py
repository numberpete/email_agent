from src.agents.base_agent import BaseAgent

SYSTEM_PROMPT = """
You are an intent detection agent for email drafting.

Classify the user's request into exactly ONE label from:
- outreach
- follow_up
- apology
- info
- internal_update
- request
- other

Return ONLY the label.
""".strip()


class IntentDetectionAgent(BaseAgent):
    """Classifies the user's intent."""

    def __init__(self, llm, logger):
        super().__init__(
            name="IntentDetection",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key="intent",
        )
