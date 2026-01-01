import json
from typing import Any, Dict, List, Tuple

from langchain_core.messages import BaseMessage, AIMessage, HumanMessage 
from src.agents.base_agent import BaseAgent
from src.agents.state import AgentState


SYSTEM_PROMPT = """
You are the Review & Validator Agent for an AI-powered email assistant.

Review the drafted email for:
- grammar and spelling
- clarity and concision
- tone alignment with the requested tone (if any)
- overall coherence and professionalism
- takes into consideration, or doesn't contradict, any past_summary of conversation history (if provided)
Also review the requested constraints for internal consistency, professional appropriateness, and feasibility.

If constraints themselves are inappropriate, contradictory, or cannot be satisfied professionally, mark 
status as BLOCKED and explain why in issues and revision_instructions.

Inputs:
- The email draft will be present in state (e.g., personalized_draft or draft).
- Tone hints may be in state_json (tone_params) and/or system messages.
- Summary of past interactions may be in state_json (past_summary).

Output:
Return ONLY valid JSON matching this schema:

{{
  "status": "PASS" | "FAIL" | "BLOCKED",
  "summary": string,
  "issues": [
        {{
        "category": "grammar" | "clarity" | "tone" | "coherence" | "policy" | "constraints" | "other",
        "severity": "low" | "medium" | "high",
        "detail": string,
        "suggested_fix": string|null
        }}
    ],
    "suggested_edits": {{
        "apply_minor_fixes": boolean,
        "recommended_tone": string|null
    }},
    "revision_instructions": string,
    "user_message": string,
    "conflicting_constraints": [string],
        "constraint_resolution": {{
        "drop_must_include": [string],
        "add_must_avoid": [string],
        "override_tone_label": string|null
    }}
}}

Rules:
- Validate BOTH:
  (1) the draft email text, AND
  (2) the constraints/tone directives provided in state_json (e.g., must_include/must_avoid).
- If the constraints require abusive/profane/harassing content or other disallowed content for a professional email assistant,
  status MUST be "BLOCKED".
- If the constraints/tone directives are internally contradictory (e.g., must_include expletives AND requested professional tone),
  status MUST be "FAIL" or "BLOCKED" depending on severity.
- If status is FAIL, revision_instructions MUST be non-empty and actionable (1-3 sentences).
- If status is PASS, revision_instructions SHOULD be empty.
- If status is BLOCKED:
  - user_message MUST be non-empty (1-3 sentences) explaining what must change.
  - revision_instructions SHOULD propose a compliant alternative direction.
  - conflicting_constraints SHOULD list the specific conflicting/disallowed items.
  - constraint_resolution SHOULD suggest how to resolve (drop/avoid/override) so the system can retry deterministically.
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

        payload = {
            "draft": state.get("personalized_draft") or state.get("draft") or "",
            "tone_params": state.get("tone_params") or {},
            "intent": state.get("intent") or "",
            "constraints": state.get("constraints") or {},
        }
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


        if payload:
            payload_str = str(payload) if not isinstance(payload, str) else payload
            self.logger.debug(
                f"[{self.name}] state_json_preview={payload_str!r}"
            )

        # ----------------------------
        # LLM invocation
        # ----------------------------
            draft_text = payload["draft"]
            validator_messages = [
                AIMessage(content="Validate the email draft AND the requested constraints. Ignore prior conversation text."),
                HumanMessage(content=draft_text),
            ]

        response = await self.agent.ainvoke(
            {
                "messages": validator_messages,
                "state_json": payload,
            }
        )

        content = getattr(response, "content", "")
        self.logger.debug(
            f"[{self.name}] LLM response received | content_length={len(content)}"
        )

        if content:
            self.logger.debug(
                f"[{self.name}] response_preview={content!r}"
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
                "revision_instructions": "",
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
            if isinstance(i, dict) and (str(i.get("severity") or "").lower() == "high")
        ]

        if status != "BLOCKED" and high_severity:
            self.logger.debug(
                f"[{self.name}] high_severity_issues_detected | count={len(high_severity)}"
            )
            status = "FAIL"

        revision_instructions = (data.get("revision_instructions") or "").strip()
        if status != "PASS" and not revision_instructions:
            revision_instructions = (
                "Revise the email to address the issues (clarity, tone alignment, and professionalism). "
                "Apply only necessary edits; keep structure intact."
            )

        report: Dict[str, Any] = {
            "status": status,
            "summary": data.get("summary") or "",
            "issues": issues,
            "suggested_edits": data.get("suggested_edits") or {},
            "revision_instructions": revision_instructions,
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

