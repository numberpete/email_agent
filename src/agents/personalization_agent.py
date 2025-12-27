from src.agents.base_agent import BaseAgent

SYSTEM_PROMPT = """
You are a personalization agent for an email assistant.

Personalize the email draft using any available user context.
If context is missing, do NOT invent details; keep the draft generic.

Return ONLY the personalized email draft.
""".strip()


class PersonalizationAgent(BaseAgent):
    """Injects user profile data and prior context into the draft."""

    def __init__(self, llm, logger):
        super().__init__(
            name="Personalization",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key="personalized_draft",
        )
