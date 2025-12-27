from src.agents.base_agent import BaseAgent

SYSTEM_PROMPT = """
You are a review and validation agent.

Review the drafted email for:
- grammar
- clarity
- tone alignment
- overall coherence

For now, output a brief report that includes:
- PASS or FAIL
- a short explanation
""".strip()


class ReviewValidatorAgent(BaseAgent):
    """Reviews and validates the drafted email."""

    def __init__(self, llm, logger):
        super().__init__(
            name="ReviewValidator",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key="validation_report",
        )
