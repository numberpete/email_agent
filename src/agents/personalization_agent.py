from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from langchain_core.messages import AIMessage, BaseMessage

from src.agents.base_agent import BaseAgent
from src.agents.state import AgentState
from src.profiles.sqlite_profile_store import SQLiteProfileStore


SYSTEM_PROMPT = """
You are the Personalization Agent for an AI-powered email assistant.

Goal:
Refine the existing draft using user profile/context ONLY if provided in state_json.

Inputs:
- Draft is in state_json.draft (or state_json.personalized_draft).
- User profile is in state_json.user_profile (loaded from DB).
- Parsed recipient hints may exist in state_json.parsed_input.

Output:
Return ONLY valid JSON exactly matching this schema:

{{
  "personalized_draft": string,
  "memory_updates": {{ ... }}
}}

Rules:
- Do NOT invent names, titles, companies, deadlines, or facts.
- Only apply substitutions when values are explicitly present in user_profile/parsed_input.
- Keep edits minimal (greeting/signature/small phrasing tweaks).
- If no personalization is possible, return original draft unchanged.
""".strip()


class PersonalizationAgent(BaseAgent):
    """Loads user profile from SQLite and applies safe minimal personalization."""

    def __init__(self, llm, logger, profile_store: SQLiteProfileStore):
        self.profile_store = profile_store

        super().__init__(
            name="Personalization",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key=None,  # structured updates
        )


    async def _execute(self, state: AgentState) -> Tuple[List[BaseMessage], Dict[str, Any]]:
        draft = (state.get("personalized_draft") or state.get("draft") or "").strip()
        parsed_input = state.get("parsed_input") or {}
        user_id = (state.get("user_id") or "default").strip()

        if not draft:
            self.logger.debug("[Personalization] No draft present; skipping.")
            return [AIMessage(content='{"personalized_draft":"","memory_updates":{}}')], {
                "personalized_draft": "",
                "memory_updates": {},
            }

        # 1) Load profile from DB
        profile = self.profile_store.get_profile(user_id)

        self.logger.debug(
            f"[Personalization] Loaded profile: user_id={user_id!r} keys={list(profile.keys())[:12]}"
        )

        payload = {
            "draft": draft,
            "user_profile": profile,
            "parsed_input": parsed_input,
        }

        self.logger.debug(
            f"[Personalization] Input: draft_len={len(draft)} parsed_keys={list(parsed_input.keys())[:10]}"
        )

        response = await self.agent.ainvoke(
            {
                "messages": state.get("messages", []),
                "state_json": self._safe_state_json(payload),
            }
        )

        self.logger.debug(
            f"[Personalization] Raw model output (first 200 chars): {response.content[:200]!r}"
        )

        # 2) Parse strict JSON
        try:
            data = json.loads(response.content)
        except Exception as e:
            self.logger.debug(f"[Personalization] JSON parse failed: {e}")
            # Fail-soft: keep original draft
            return [AIMessage(content='{"personalized_draft":"","memory_updates":{}}')], {
                "personalized_draft": draft,
                "memory_updates": {},
                "user_context": profile,  # still expose loaded profile to state for debug
            }

        personalized = (data.get("personalized_draft") or "").strip() or draft
        mem_updates = data.get("memory_updates") or {}
        if not isinstance(mem_updates, dict):
            mem_updates = {}

        updates: Dict[str, Any] = {
            "personalized_draft": personalized,
            "memory_updates": mem_updates,
            "user_context": profile,  # resolved context for UI/debug
        }

        self.logger.debug(f"[Personalization] Output: personalized_len={len(personalized)}")
        return [response], updates
