import json
from typing import Any, Dict, List, Tuple

from langchain_core.messages import AIMessage, BaseMessage

from src.agents.base_agent import BaseAgent
from src.agents.state import AgentState


SYSTEM_PROMPT = """
You are the Input Parsing Agent for an AI-powered email assistant.

Role: Structural normalization and safety gate.

Responsibilities:
1) Validate whether the user provided enough information to draft an email.
2) Extract:
   - primary_request: what email to write / what outcome is desired
   - recipient: who the email is to (name/role/relationship if provided; otherwise null)
   - context: background info that should be included (if provided; otherwise null)
   - constraints: explicit constraints such as length, audience, format, deadline, must_include, must_avoid
   - tone_params: explicit tone instructions (formal, friendly, assertive, apologetic, etc.)

Failure behavior:
- If input is unusable or too ambiguous, set requires_clarification=true and provide 1-4 clarification questions.

Return ONLY valid JSON matching this schema:

{{
  "requires_clarification": boolean,
  "clarification_questions": [string],
  "parsed_input": {{
    "primary_request": string,
    "recipient": {{
      "name": string|null,
      "role": string|null,
      "relationship": string|null
    }},
    "context": string|null
  }},
  "constraints": {{
    "length": string|null,
    "format": string|null,
    "audience": string|null,
    "deadline": string|null,
    "must_include": [string],
    "must_avoid": [string]
  }},
  "tone_params": {{
    "tone": string|null
  }}
}}

Rules:
- If METADATA is provided, treat it as authoritative and do not ask the user for those details again.
- Do not invent recipient details; use null if unknown.
- Keep strings concise.
- If requires_clarification is true, parsed_input.primary_request may be empty.
""".strip()


class InputParsingAgent(BaseAgent):
    """
    Produces structured updates for:
    - requires_clarification (bool)
    - parsed_input (dict)
    - constraints (dict)
    - tone_params (dict)
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
                "tone_params": {},
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
        tone_params = data.get("tone_params") or {}

        if not isinstance(parsed_input, dict):
            parsed_input = {}
        if not isinstance(constraints, dict):
            constraints = {}
        if not isinstance(tone_params, dict):
            tone_params = {}

        self.logger.debug(
            f"[{self.name}] requires_clarification={requires} | "
            f"parsed_input_keys={list(parsed_input.keys())} | "
            f"constraints_keys={list(constraints.keys())} | "
            f"tone_params={tone_params}"
        )

        updates: Dict[str, Any] = {
            "requires_clarification": requires,
            "parsed_input": parsed_input,
            "constraints": constraints,
            "tone_params": tone_params,
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

