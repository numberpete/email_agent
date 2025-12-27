from src.agents.base_agent import BaseAgent

SYSTEM_PROMPT = """
You are a tone stylist for an AI email assistant.

Given the conversation, propose tone settings for the email.

For now, return a short tone description string,
for example: "formal, concise, confident".
""".strip()


class ToneStylistAgent(BaseAgent):
    """Determines tone parameters for the email."""

    def __init__(self, llm, logger):
        super().__init__(
            name="ToneStylist",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key="tone_params",
        )
