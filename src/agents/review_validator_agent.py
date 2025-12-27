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
        # Use the same invocation contract as other agents (messages + state_json)
        response = await self.agent.ainvoke(
            {
                "messages": state.get("messages", []),
                "state_json": self._safe_state_json(state),
            }
        )

        # Parse JSON
        try:
            data = json.loads(response.content)
        except Exception as e:
            # Fallback: treat as FAIL but don't crash the graph
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
            return (
                [AIMessage(content="Validation encountered an internal formatting issue; proceeding with FAIL.")],
                {"validation_report": report, "is_valid": False},
            )

        # Normalize and enforce minimum shape
        status = (data.get("status") or "FAIL").upper()
        issues = data.get("issues") or []
        if not isinstance(issues, list):
            issues = []

        # If any high severity issue exists, force FAIL
        if any(isinstance(i, dict) and (i.get("severity") == "high") for i in issues):
            status = "FAIL"

        report: Dict[str, Any] = {
            "status": "PASS" if status == "PASS" else "FAIL",
            "summary": data.get("summary") or "",
            "issues": issues,
            "suggested_edits": data.get("suggested_edits") or {},
        }

        is_valid = report["status"] == "PASS"

        return [response], {"validation_report": report, "is_valid": is_valid}
