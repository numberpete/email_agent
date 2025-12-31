import json
from typing import Any, Dict, List, Tuple

from langchain_core.messages import AIMessage, BaseMessage

from src.agents.base_agent import BaseAgent
from src.agents.state import AgentState


SYSTEM_PROMPT = """
You are the Tone Stylist Agent for an AI-powered email assistant.

Goal:
Produce a compact, structured "tone_params" specification that downstream agents
(Draft Writer, Personalization) can use to consistently shape the email tone.

Inputs:
- Latest user request is in messages (most recent HumanMessage).
- Parsed hints may exist in state_json (parsed_input, constraints).
- The UI may provide a tone selection (e.g., "formal", "friendly", "assertive", etc.).
  If the UI provided a tone, it should be respected.

Output:
Return ONLY valid JSON exactly matching this schema:

{{
  "tone_params": {{
    "tone_label": "<string>",                 // e.g., formal, friendly, assertive, neutral
    "formality": 0-100,                       // higher = more formal
    "warmth": 0-100,                          // higher = friendlier / more personable
    "directness": 0-100,                      // higher = more direct / concise
    "confidence": 0.0-1.0,                    // confidence in tone selection
  }},
  "reason": "<short explanation, 1 sentence>"
}}

Rules:
- Do NOT draft the email.
- If tone is not specified, infer a reasonable default from context (usually neutral-professional).
- "tone_label" should be stable, lowercase, and underscore-free (e.g., "follow_up" is NOT a tone).
""".strip()


class ToneStylistAgent(BaseAgent):
    """Derives tone_params for downstream drafting/personalization."""

    def __init__(self, llm, logger):
        super().__init__(
            name="ToneStylist",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key=None,  # structured updates
        )

    async def _execute(self, state: AgentState) -> Tuple[List[BaseMessage], Dict[str, Any]]:
        # 0) UI override path: if UI already provided tone_params, treat as authoritative.
        # We consider a UI override present if tone_params has a non-empty "tone_label" or a non-empty dict.
        self.logger.debug(
            f"[ToneStylist] State tone_params keys={list((state.get('tone_params') or {}).keys())} "
            f"raw_input_len={len((state.get('raw_input') or ''))}"
        )

        ui_tone_params = state.get("tone_params") or {}
        ui_label = ""
        if isinstance(ui_tone_params, dict):
            ui_label = str(ui_tone_params.get("tone_label") or "").strip()

        if ui_label:
            # If user picked "(auto)" in UI, you should pass {} from UI, not a placeholder.
            # So any non-empty dict here is considered an override.
            self.logger.debug(f"[ToneStylist] Using UI tone override tone_label={ui_label!r}")

            updates: Dict[str, Any] = {
                "tone_params": ui_tone_params,
                "tone_source": "ui",
            }
            return [AIMessage(content=json.dumps({"tone_params": ui_tone_params, "reason": "UI override"}))], updates

        # 1) Model inference path
        messages = state.get("messages", [])
        state_json = self._safe_state_json(state)

        self.logger.debug(f"[ToneStylist] Input: messages={len(messages)} state_json_len={len(state_json)}")

        response = await self.agent.ainvoke(
            {
                "messages": messages,
                "state_json": state_json,
            }
        )

        self.logger.debug(f"[ToneStylist] Raw model output (first 200 chars): {response.content[:200]!r}")

        # 2) Parse strict JSON
        try:
            data = json.loads(response.content)
        except Exception as e:
            self.logger.debug(f"[ToneStylist] JSON parse failed: {e}")

            # Fail soft: provide a safe default (neutral-professional)
            default_tone = {
                "tone_label": "neutral",
                "formality": 70,
                "warmth": 45,
                "directness": 65,
                "confidence": 0.3,
            }

            updates = {
                "tone_params": default_tone,
                "tone_source": "default",
                "validation_report": {
                    "status": "WARN",
                    "reason": "ToneStylist returned non-JSON output; applied default tone.",
                },
            }
            return [AIMessage(content=json.dumps({"tone_params": default_tone, "reason": "Default due to parse error"}))], updates

        tone_params = (data.get("tone_params") or {})
        reason = (data.get("reason") or "").strip()

        if not isinstance(tone_params, dict):
            tone_params = {}

        if not tone_params:
            self.logger.debug("[ToneStylist] Model returned empty tone_params; applying default tone.")
            tone_params = {
                "tone_label": "neutral",
                "formality": 70,
                "warmth": 45,
                "directness": 65,
                "confidence": 0.3,
            }
            reason = reason or "Applied default tone due to empty model output."
            updates: Dict[str, Any] = {"tone_params": tone_params, "tone_source": "default"}
            return [response], updates

        # 3) Minimal normalization / defaults
        tone_label = (tone_params.get("tone_label") or "neutral").strip().lower()
        tone_params["tone_label"] = tone_label

        # Ensure numeric ranges
        def clamp_int(v: Any, lo: int, hi: int, default: int) -> int:
            try:
                x = int(v)
            except Exception:
                return default
            return max(lo, min(hi, x))

        def clamp_float(v: Any, lo: float, hi: float, default: float) -> float:
            try:
                x = float(v)
            except Exception:
                return default
            return max(lo, min(hi, x))

        tone_params["formality"] = clamp_int(tone_params.get("formality"), 0, 100, 70)
        tone_params["warmth"] = clamp_int(tone_params.get("warmth"), 0, 100, 45)
        tone_params["directness"] = clamp_int(tone_params.get("directness"), 0, 100, 65)
        tone_params["confidence"] = clamp_float(tone_params.get("confidence"), 0.0, 1.0, 0.6)


        updates: Dict[str, Any] = {
            "tone_params": tone_params,
            "tone_source": "model",
        }

        self.logger.debug(
            f"[ToneStylist] Final tone: label={tone_params['tone_label']!r} "
            f"formality={tone_params['formality']} warmth={tone_params['warmth']} "
            f"directness={tone_params['directness']} confidence={tone_params['confidence']}"
        )

        return [response], updates
