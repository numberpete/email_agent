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
        response = await self.agent.ainvoke({
            "messages": state.get("messages", []), 
            "state_json": self._safe_state_json(state)
        })

        # Parse JSON safely; if it fails, fall back to clarification
        try:
            data = json.loads(response.content)
        except Exception:
            questions = [
                "Who is the recipient (name and/or role), and what is your relationship to them?",
                "What is the main goal of the email (request, update, follow-up, apology, etc.)?",
                "Any constraints (length, tone, deadline, bullet points, etc.)?",
            ]
            msg = "I need a bit more information to draft the email:\n" + "\n".join(f"- {q}" for q in questions)

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
            return [AIMessage(content=msg)], updates

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

        updates: Dict[str, Any] = {
            "requires_clarification": requires,
            "parsed_input": parsed_input,
            "constraints": constraints,
            "tone_params": tone_params,
            "validation_report": {"status": "OK"} if not requires else {},  # optional default
        }

        # If clarification required, emit a user-facing message and store detail in validation_report
        if requires:
            # Ensure we have at least one question
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

            return [AIMessage(content=msg)], updates

        # Success path: keep the model output message for debugging, but you can also omit it later
        return [response], updates
