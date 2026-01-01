import json
from typing import Any, Dict, List, Tuple

from langchain_core.messages import AIMessage, BaseMessage

from src.agents.base_agent import BaseAgent
from src.agents.state import AgentState


SYSTEM_PROMPT = """
You are the Input Parsing Agent for an AI-powered email assistant.

Role: Structural normalization and gating.

DEFAULT BEHAVIOR:
- requires_clarification MUST default to false.
- Only set requires_clarification=true in the STRICT failure cases listed below.

STRICT failure cases (the ONLY reasons to set requires_clarification=true):
A) The user input is empty/garbled.
B) There is no identifiable email goal/topic/purpose even with safe defaults.
C) The user provides contradictory instructions that make drafting impossible.

NON-failure cases (MUST NOT trigger clarification):
- Recipient missing or unknown → set recipient fields to null.
- Relationship missing → null.
- Context missing → context=null.
- Tone missing → ignore here (handled by ToneStylist).
- Constraints missing → leave null/empty lists.
- The user did not provide names/dates → use placeholders, do NOT ask.

Actionable definition:
If you can infer ANY plausible email goal (follow up / request / update / apology / thank you / scheduling / outreach),
then requires_clarification MUST be false and parsed_input.primary_request MUST be non-empty.

Examples:
- "Follow up with the recruiter" -> requires_clarification=false
- "Ask IT to restore VPN access" -> requires_clarification=false
- "Write an email about the thing" -> requires_clarification=true
- "asdf qwer" -> requires_clarification=true

Return ONLY valid JSON matching this schema:

{{
  "requires_clarification": boolean,
  "clarification_questions": [string],
  "parsed_input": {{
    "primary_request": string,
    "recipient": {{
      "name": string|null,
      "role": string|null,
      "relationship": string|null,
      "org": string|null,
      "email": string|null
    }},
    "context": string|null
  }},
  "constraints": {{
    "length": string|null,
    "format": string|null,
    "audience": string|null,
    "deadline": string|null,
    "must_include": [string],
    "must_avoid": [string],
    "use_bullets": boolean|null,
    "bullet_count": integer|null
  }}
}}

Rules:
- If METADATA is provided, treat it as authoritative and do not ask the user for those details again.
- Do not invent recipient details; use null if unknown.
- Keep strings concise.
- If actionable, parsed_input.primary_request MUST be non-empty.
- If requires_clarification=true, parsed_input.primary_request may be empty.
- If user requests bullets/bullet points/numbered list → constraints.use_bullets = true
- Optionally include constraints.bullet_count if specified.
""".strip()


class InputParsingAgent(BaseAgent):
    """
    Produces structured updates for:
    - requires_clarification (bool)
    - parsed_input (dict)
    - constraints (dict)
    Optionally sets validation_report (dict) when clarification is required.
    """

    def __init__(self, llm, logger):
        super().__init__(
            name="InputParsing",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key=None,  # structured updates, not a single field
        )

    async def _execute(self, state: AgentState) -> Tuple[List[BaseMessage], Dict[str, Any]]:
        messages = state.get("messages", [])
        state_json = self._safe_state_json(state)

        # ----------------------------
        # DEBUG: inputs
        # ----------------------------
        self.logger.debug(
            f"[{self.name}] InputParser _execute() | "
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
            f"[{self.name}] LLM response received | length={len(content)}"
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

            questions = [
                "Who is the recipient (name and/or role), and what is your relationship to them?",
                "What is the main goal of the email (request, update, follow-up, apology, etc.)?",
                "Any constraints (length, tone, deadline, bullet points, etc.)?",
            ]

            msg = "I need a bit more information to draft the email:\n" + "\n".join(
                f"- {q}" for q in questions
            )

            updates: Dict[str, Any] = {
                "requires_clarification": True,
                "parsed_input": {},
                "constraints": {},
                "validation_report": {
                    "status": "NEEDS_CLARIFICATION",
                    "reason": "Input parser could not produce structured parse output.",
                    "questions": questions,
                },
            }

            self.logger.debug(
                f"[{self.name}] clarification REQUIRED | reason=json_parse_failure"
            )

            return [AIMessage(content=msg)], updates

        # ----------------------------
        # Normalize parsed values
        # ----------------------------
        requires = bool(data.get("requires_clarification", False))
        questions = data.get("clarification_questions") or []
        parsed_input = data.get("parsed_input") or {}
        constraints = data.get("constraints") or {}

        if not isinstance(parsed_input, dict):
            parsed_input = {}
        if not isinstance(constraints, dict):
            constraints = {}

        self.logger.debug(
            f"[{self.name}] requires_clarification={requires} | "
            f"parsed_input_keys={list(parsed_input.keys())} | "
            f"constraints_keys={list(constraints.keys())} "
        )

        updates: Dict[str, Any] = {
            "requires_clarification": requires,
            "parsed_input": parsed_input,
            "constraints": constraints,
            "validation_report": {"status": "OK"} if not requires else {},
        }

        # ----------------------------
        # Clarification path
        # ----------------------------
        if requires:
            if not questions:
                questions = [
                    "Who is the recipient (name and/or role), and what is your relationship to them?",
                    "What is the main goal of the email?",
                ]

            msg = "I need a bit more information to draft the email:\n" + "\n".join(
                f"- {q}" for q in questions[:4]
            )

            updates["validation_report"] = {
                "status": "NEEDS_CLARIFICATION",
                "questions": questions[:4],
            }

            self.logger.debug(
                f"[{self.name}] clarification QUESTIONS={questions[:4]}"
            )

            return [AIMessage(content=msg)], updates

        # ----------------------------
        # Success path
        # ----------------------------
        self.logger.debug(
            f"[{self.name}] parse SUCCESS | proceeding without clarification"
        )

        return [response], updates

