from src.agents.base_agent import BaseAgent

SYSTEM_PROMPT = """
You are a professional email assistant.

Write a complete email draft based on the user's request.
Keep it clear, structured, and appropriate for business communication.

Return ONLY the email draft.
""".strip()


class DraftWriterAgent(BaseAgent):
    """Generates the core email draft."""

    def __init__(self, llm, logger):
        super().__init__(
            name="DraftWriter",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key="draft",
        )
