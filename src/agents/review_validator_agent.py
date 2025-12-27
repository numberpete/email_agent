import json
from typing import Any, Dict, List, Tuple

from langchain_core.messages import AIMessage, BaseMessage

from src.agents.base_agent import BaseAgent
from src.agents.state import AgentState


SYSTEM_PROMPT = """
You are the Review & Validator Agent for an AI-powered email assistant.

Review the drafted email for:
- grammar and spelling
- clarity and concision
- tone alignment with the requested tone (if any)
- overall coherence and professionalism

Inputs:
- The email draft will be present in state (e.g., personalized_draft or draft).
- Tone hints may be in state_json (tone_params) and/or system messages.

Output:
Return ONLY valid JSON matching this schema:

{{
  "status": "PASS" | "FAIL",
  "summary": string,
  "issues": [
    {{
      "category": "grammar" | "clarity" | "tone" | "coherence" | "policy" | "other",
      "severity": "low" | "medium" | "high",
      "detail": string,
      "suggested_fix": string|null
    }}
  ],
  "suggested_edits": {{
    "apply_minor_fixes": boolean,
    "recommended_tone": string|null
  }}
}}

Rules:
- Keep "summary" short (1-2 sentences).
- If there are any high-severity issues, status MUST be "FAIL".
- Do not rewrite the full email; only review and suggest fixes.
""".strip()


class ReviewValidatorAgent(BaseAgent):
    """Reviews and validates the drafted email. Produces structured validation_report + is_valid."""

    def __init__(self, llm, logger):
        super().__init__(
            name="ReviewValidator",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key=None,  # structured updates
        )

    async def _execute(self, state: AgentState) -> Tuple[List[BaseMessage], Dict[str, Any]]:
        messages = state.get("messages", [])
        state_json = self._safe_state_json(state)

        # ----------------------------
        # DEBUG: inputs
        # ----------------------------
        self.logger.debug(
            f"[{self.name}] ReviewValidator _execute() | "
            f"messages={len(messages)} | "
            f"state_keys={list(state.keys())}"
        )

        if messages:
            last_msg = messages[-1]
            last_content = getattr(last_msg, "content", "")
            self.logger.debug(
                f"[{self.name}] last_message_preview={last_content[:200]!r}"
            )

        if state_json:
            self.logger.debug(
                f"[{self.name}] state_json_preview={state_json[:500]!r}"
            )

        # ----------------------------
        # LLM invocation
        # ----------------------------
        response = await self.agent.ainvoke(
            {
                "messages": messages,
                "state_json": state_json,
            }
        )

        content = getattr(response, "content", "")
        self.logger.debug(
            f"[{self.name}] LLM response received | content_length={len(content)}"
        )

        if content:
            self.logger.debug(
                f"[{self.name}] response_preview={content[:400]!r}"
            )

        # ----------------------------
        # JSON parsing
        # ----------------------------
        try:
            data = json.loads(content)
            self.logger.debug(
                f"[{self.name}] JSON parse SUCCESS | keys={list(data.keys())}"
            )
        except Exception as e:
            self.logger.debug(
                f"[{self.name}] JSON parse FAILED | error={e}"
            )

            report = {
                "status": "FAIL",
                "summary": "Validator returned non-JSON output.",
                "issues": [
                    {
                        "category": "other",
                        "severity": "high",
                        "detail": f"Json Parse Error: {str(e)}",
                        "suggested_fix": "Adjust validator prompt to return strict JSON.",
                    }
                ],
                "suggested_edits": {
                    "apply_minor_fixes": False,
                    "recommended_tone": None,
                },
            }

            self.logger.debug(
                f"[{self.name}] validation FAIL | reason=json_parse_error"
            )

            return (
                [AIMessage(content="Validation encountered an internal formatting issue; proceeding with FAIL.")],
                {"validation_report": report, "is_valid": False},
            )

        # ----------------------------
        # Normalize + evaluate result
        # ----------------------------
        status = (data.get("status") or "FAIL").upper()
        issues = data.get("issues") or []

        if not isinstance(issues, list):
            self.logger.debug(
                f"[{self.name}] issues malformed; expected list, got {type(issues).__name__}"
            )
            issues = []

        # Check for high-severity issues
        high_severity = [
            i for i in issues
            if isinstance(i, dict) and i.get("severity") == "high"
        ]

        if high_severity:
            self.logger.debug(
                f"[{self.name}] high_severity_issues_detected | count={len(high_severity)}"
            )
            status = "FAIL"

        report: Dict[str, Any] = {
            "status": "PASS" if status == "PASS" else "FAIL",
            "summary": data.get("summary") or "",
            "issues": issues,
            "suggested_edits": data.get("suggested_edits") or {},
        }

        is_valid = report["status"] == "PASS"

        # ----------------------------
        # DEBUG: outputs
        # ----------------------------
        self.logger.debug(
            f"[{self.name}] validation_result={report['status']} | "
            f"issues_count={len(report['issues'])} | "
            f"is_valid={is_valid}"
        )

        return [response], {"validation_report": report, "is_valid": is_valid}

