import json
from typing import Any, Dict, List, Tuple

from langchain_core.messages import AIMessage, BaseMessage

from src.agents.base_agent import BaseAgent
from src.agents.state import AgentState


SYSTEM_PROMPT = """
You are the Intent Detection Agent for an AI-powered email assistant.

Goal:
Classify the user's email-writing request into a single intent label with confidence.

Valid intents (choose exactly one):
- outreach        (cold/warm intro, networking, requesting meeting from someone you don't regularly email)
- follow_up       (checking in, nudging, replying after delay, continuing a prior thread)
- apology         (saying sorry, acknowledging mistake, repair)
- info            (sharing information, update, status, explanation, announcement)
- request         (asking for something: approval, action, access, decision, help)
- thank_you       (expressing gratitude)
- scheduling      (meeting setup, availability, reschedule)
- other           (none of the above)

Inputs:
- Latest user request is in messages (most recent HumanMessage).
- Parsed hints may exist in state_json (parsed_input, constraints, tone_params).

Output:
Return ONLY valid JSON exactly matching this schema:

{{
  "intent": "<one of the valid intents>",
  "confidence": 0.0-1.0,
  "reason": "<short explanation, 1 sentence>"
}}

Rules:
- Do NOT write an email draft.
- Keep "reason" under 25 words.
- Confidence guidance:
  - 0.90-1.00: explicit intent words (e.g., "follow up", "apologize", "thank you", "schedule")
  - 0.70-0.89: strongly implied
  - 0.40-0.69: ambiguous
  - 0.00-0.39: unclear (use "other")
""".strip()


class IntentDetectionAgent(BaseAgent):
    """Classifies intent into a controlled taxonomy with confidence."""

    def __init__(self, llm, logger):
        super().__init__(
            name="IntentDetection",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key=None,  # structured updates
        )

    async def _execute(self, state: AgentState) -> Tuple[List[BaseMessage], Dict[str, Any]]:
        # 0) UI override path (authoritative), if provided
        INTENT_ALIASES = {
            "follow up": "follow_up",
            "follow-up": "follow_up",
            "followup": "follow_up",
            "requesting": "request",
            "asking": "request",
        }

        override = (state.get("user_intent_override") or "").strip()
        if override and override.lower() not in {"auto", "(auto)", "none"}:
            chosen = override.strip()
            self.logger.debug(
                f"[IntentDetection] Using UI intent override: {chosen}"
            )
            updates: Dict[str, Any] = {
                "intent": chosen,
                "intent_confidence": 1.0,
                "intent_source": "ui",
            }
            return [AIMessage(content=f'{{"intent":"{chosen}","confidence":1.0,"reason":"UI override"}}')], updates

        # 1) Model inference path
        messages = state.get("messages", [])
        state_json = self._safe_state_json(state)

        self.logger.debug(
            f"[IntentDetection] Input: messages={len(messages)} state_json_len={len(state_json)}"
        )

        response = await self.agent.ainvoke(
            {
                "messages": messages,
                "state_json": state_json,
            }
        )

        self.logger.debug(
            f"[IntentDetection] Raw model output (first 200 chars): {response.content[:200]!r}"
        )

        # 2) Parse strict JSON
        try:
            data = json.loads(response.content)
        except Exception as e:
            self.logger.debug(f"[IntentDetection] JSON parse failed: {e}")
            # Fail soft: do not crash graph; choose "other"
            updates = {
                "intent": "other",
                "intent_confidence": 0.0,
                "intent_source": "default",
            }
            msg = AIMessage(
                content='{"intent":"other","confidence":0.0,"reason":"Non-JSON output from intent classifier"}'
            )
            self.logger.debug(f"[IntentDetection] updates={updates}")
            return [msg], updates

        raw_intent = (data.get("intent") or "other").strip().lower()
        intent = INTENT_ALIASES.get(raw_intent, raw_intent)

        conf = data.get("confidence")
        reason = (data.get("reason") or "").strip()

        # Normalize confidence
        try:
            conf_f = float(conf)
        except Exception:
            conf_f = 0.0
        conf_f = max(0.0, min(1.0, conf_f))

        # Basic normalization of intent
        valid = {
            "outreach",
            "follow_up",
            "apology",
            "info",
            "request",
            "thank_you",
            "scheduling",
            "other",
        }
        if intent not in valid:
            self.logger.debug(f"[IntentDetection] Invalid intent '{intent}', coercing to 'other'")
            intent = "other"
            conf_f = min(conf_f, 0.4)

        updates: Dict[str, Any] = {
            "intent": intent,
            "intent_confidence": conf_f,
            "intent_source": "model",
        }

        self.logger.debug(
            f"[IntentDetection] Parsed: intent={intent} confidence={conf_f} reason={reason!r}"
        )
        
        self.logger.debug(f"[IntentDetection] updates={updates}")

        return [response], updates
