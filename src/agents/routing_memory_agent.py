from src.agents.base_agent import BaseAgent

SYSTEM_PROMPT = """
You are a memory and logging agent for an AI email assistant.

Propose safe-to-store user preference updates based on this interaction.
Do NOT include sensitive data.
Keep suggestions minimal and high-signal.

For now, return a short text summary of suggested memory updates.
""".strip()


class RoutingMemoryAgent(BaseAgent):
    """Proposes memory updates and logging information."""

    def __init__(self, llm, logger):
        super().__init__(
            name="RoutingMemory",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key="memory_updates",
        )
