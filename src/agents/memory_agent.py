import json
from typing import Any, Dict, List, Tuple
from langchain_core.messages import BaseMessage, AIMessage

from src.agents.base_agent import BaseAgent
from src.agents.state import AgentState
from src.memory.sqlite_memory_store import SQLiteMemoryStore
from src.utils.recipient import compute_recipient_key, normalize_recipient

SYSTEM_PROMPT = """
You are the Memory Agent for an AI-powered email assistant.

Your job is to maintain a concise, durable summary of prior email interactions
between a user and a recipient.

Inputs:
- Existing summary (may be empty or null)
- The latest email draft that was sent
- The detected intent and tone

Task:
- Merge the new information into the existing summary.
- Preserve important facts, decisions, relationship context, and tone patterns.
- Do NOT include verbatim email text.
- Do NOT invent facts.
- Keep the summary concise (max ~120 words).

Output:
Return ONLY valid JSON with this schema:

{{
  "summary": {{
    "relationship": string|null,
    "history": [string],
    "last_intent": string|null,
    "last_tone": string|null
  }}
}}

Rules:
- Append to history only if the new email adds material information.
- Avoid duplication.
- Prefer clarity over completeness.
""".strip()



class MemoryAgent(BaseAgent):
    def __init__(self, llm, logger, memory_store: SQLiteMemoryStore):
        super().__init__(
            name="Memory",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key=None,
        )
        self.memory_store = memory_store

    async def _execute(
        self, state: AgentState
    ) -> Tuple[List[BaseMessage], Dict[str, Any]]:

        # Only persist on PASS
        report = state.get("validation_report") or {}
        if (report.get("status") or "").upper() != "PASS":
            self.logger.debug("[Memory] Skipping persistence (status != PASS)")
            return [], {}

        user_id = state.get("user_id")
        if not user_id:
            self.logger.debug("[Memory] No user_id; skipping persistence")
            return [], {}

        recipient = state.get("parsed_input", {}).get("recipient") or {}
        recipient_key = None
        past_summary = {}
        if recipient:
            metadata = state.get("constraints") or {}
            recipient = normalize_recipient(recipient, metadata)
            self.logger.debug(f"[Memory] Normalized recipient: {recipient!r}")
            recipient_key = compute_recipient_key(recipient)
            self.logger.debug(f"[Memory] Computed recipient_key: {recipient_key!r}")


            # Load existing summary
            past_summary = self.memory_store.get_past_summary(
                user_id, recipient_key
            )

        payload = {
            "existing_summary": past_summary,
            "draft": state.get("personalized_draft") or state.get("draft"),
            "intent": state.get("intent"),
            "tone": state.get("tone_params"),
        }

        self.logger.debug(
            f"[Memory] Merging summary for user={user_id}, recipient={recipient_key}"
        )

        response = await self.agent.ainvoke(
            {
                "messages": [],
                "state_json": payload,
            }
        )

        try:
            data = json.loads(response.content)
            summary = data.get("summary")
            if not isinstance(summary, dict):
                raise ValueError("summary missing or invalid")
        except Exception as e:
            self.logger.warning(
                f"[Memory] Failed to parse summary JSON: {e}"
            )
            return [AIMessage(content="Memory update skipped due to parse error.")], {}

        self.memory_store.upsert_summary(
            user_id=user_id,
            recipient_key=recipient_key,
            summary=summary,
        )

        self.logger.debug("[Memory] Summary upserted successfully")

        return [response], {}