from __future__ import annotations

from typing import Any, Dict, List, Tuple

from langchain_core.messages import BaseMessage

from src.agents.base_agent import BaseAgent
from src.agents.state import AgentState


SYSTEM_PROMPT = """
You are the Draft Writer Agent for an AI-powered email assistant.

You will receive:
- A rendered email skeleton (with subject/greeting/closing etc.)
- A template plan including length budget and formatting guidance
- Parsed user intent/context/ask and constraints

Instructions:
- Produce the final email draft in plain text.
- Respect the length budget (max_words, max_paragraphs).
- Preserve the overall structure from the rendered skeleton.
- Do not output JSON. Do not output analysis. Output only the email.
""".strip()


class DraftWriterAgent(BaseAgent):
    def __init__(self, llm, logger, template_engine):
        self.template_engine = template_engine

        # Allow llm=None for unit tests
        if llm is None:
            self.name = "DraftWriter"
            self.logger = logger
            self.agent = None
            self.state_key = None
            return

        super().__init__(
            name="DraftWriter",
            llm=llm,
            logger=logger,
            system_prompt=SYSTEM_PROMPT,
            state_key=None,  # structured updates
        )

    async def _execute(self, state: AgentState) -> Tuple[List[BaseMessage], Dict[str, Any]]:
        intent = (state.get("intent") or "other").strip()
        tone_params = state.get("tone_params") or {}
        constraints = state.get("constraints") or {}
        parsed_input = state.get("parsed_input") or {}

        plan = self.template_engine.build_plan(
            intent=intent,
            tone_params=tone_params,
            constraints=constraints,
            parsed_input=parsed_input,
        )

        self.logger.debug(
            f"[DraftWriter] plan: template_id={plan.get('template_id')!r} "
            f"tone_label={plan.get('tone_label')!r} length_hint={plan.get('length_hint')!r} "
            f"max_words={plan.get('length_budget', {}).get('max_words')!r}"
        )

        # Provide a compact state_json to the model.
        payload = {
            "intent": intent,
            "tone_params": tone_params,
            "constraints": constraints,
            "parsed_input": parsed_input,
            "template_plan": {
                "template_id": plan.get("template_id"),
                "tone_label": plan.get("tone_label"),
                "length_hint": plan.get("length_hint"),
                "length_budget": plan.get("length_budget"),
                "format": plan.get("format"),
            },
            "rendered_skeleton": plan.get("rendered_skeleton", ""),
        }

        response = await self.agent.ainvoke(
            {
                "messages": state.get("messages", []),
                "state_json": self._safe_state_json(payload),
            }
        )

        draft = (response.content or "").strip()

        updates: Dict[str, Any] = {
            "draft": draft,
            # useful for UI debug panels
            "template_id": plan.get("template_id") or "",
            "template_plan": plan,
        }

        self.logger.debug(f"[DraftWriter] draft_len={len(draft)}")
        return [response], updates
