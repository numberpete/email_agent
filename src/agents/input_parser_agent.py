from src.agents.base_agent import BaseAgent

SYSTEM_PROMPT = """
You are an input parsing agent for an AI email assistant.

Normalize the user's request into a concise, clear instruction.
If important details are missing, list the missing items.

Return only the normalized instruction text for now.
""".strip()


class InputParsingAgent(BaseAgent):
    """Validates and normalizes the user's request."""

    def __init__(self, llm, logger):
        super().__init__(
            name="InputParsing",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key="parsed_input",
        )
