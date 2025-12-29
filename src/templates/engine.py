from __future__ import annotations

from typing import Any, Dict, Optional


class EmailTemplateEngine:
    """
    Controls tone, length, and formatting deterministically.
    Produces a template_plan that DraftWriter must follow.
    """

    def __init__(self, template_store):
        self.store = template_store

    def build_plan(
        self,
        *,
        intent: str,
        tone_params: Dict[str, Any],
        constraints: Dict[str, Any],
        parsed_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        tone_label = (tone_params.get("tone_label") or "neutral").strip() or "neutral"

        # ---- length policy (v1) ----
        # If constraints contains explicit length, that wins.
        length_hint = (constraints.get("length") or "").strip().lower()
        if not length_hint:
            # map tone_label to a default length shape
            length_hint = "short" if tone_label == "concise" else "medium"

        length_budget = self._length_budget(length_hint)

        # ---- formatting policy (v1) ----
        fmt = {
            "use_subject": True,
            "use_bullets": bool(constraints.get("use_bullets", False)),
            "max_bullets": length_budget["max_bullets"],
            "section_order": ["subject", "greeting", "context", "ask", "closing", "signature"],
        }

        # ---- template selection ----
        tpl = None
        if self.store is not None:
            tpl = self.store.get_best_template(intent=intent, tone_label=tone_label, constraints=constraints)

        body = (tpl or {}).get("body") or self._default_body()

        # ---- placeholder defaults (v1) ----
        placeholders = {
            "subject": self._suggest_subject(intent, parsed_input),
            "greeting": self._suggest_greeting(tone_label, parsed_input),
            "context": self._suggest_context(parsed_input),
            "ask": self._suggest_ask(intent, parsed_input),
            "closing": self._suggest_closing(tone_label),
            "signature": self._suggest_signature(),
        }

        rendered_skeleton = self._render(body, placeholders)

        return {
            "template_id": (tpl or {}).get("template_id"),
            "tone_label": tone_label,
            "length_hint": length_hint,
            "length_budget": length_budget,
            "format": fmt,
            "placeholders": placeholders,
            "template_body": body,
            "rendered_skeleton": rendered_skeleton,
        }

    def _length_budget(self, length_hint: str) -> Dict[str, int]:
        # v1: conservative budgets
        if length_hint in {"very_short", "tiny"}:
            return {"target_words": 70, "max_words": 100, "max_paragraphs": 3, "max_bullets": 3}
        if length_hint in {"short", "concise"}:
            return {"target_words": 110, "max_words": 160, "max_paragraphs": 4, "max_bullets": 4}
        if length_hint in {"long", "detailed"}:
            return {"target_words": 220, "max_words": 320, "max_paragraphs": 6, "max_bullets": 6}
        return {"target_words": 160, "max_words": 240, "max_paragraphs": 5, "max_bullets": 5}

    def _default_body(self) -> str:
        return (
            "Subject: {{subject}}\n\n"
            "{{greeting}}\n\n"
            "{{context}}\n\n"
            "{{ask}}\n\n"
            "{{closing}}\n"
            "{{signature}}\n"
        )

    def _render(self, template: str, values: Dict[str, str]) -> str:
        out = template
        for k, v in values.items():
            out = out.replace("{{" + k + "}}", v or "")
        return out

    def _suggest_subject(self, intent: str, parsed_input: Dict[str, Any]) -> str:
        primary = (parsed_input.get("primary_request") or "").strip()
        if primary:
            return primary[:70]
        return {
            "follow_up": "Following up",
            "request": "Request",
            "apology": "Apology",
            "outreach": "Introduction",
            "info": "Update",
        }.get(intent, "Message")

    def _suggest_greeting(self, tone_label: str, parsed_input: Dict[str, Any]) -> str:
        rec = (parsed_input.get("recipient") or {})
        name = (rec.get("name") or "").strip()
        if name:
            return f"Hi {name},"
        return "Hello," if tone_label == "formal" else "Hi,"

    def _suggest_context(self, parsed_input: Dict[str, Any]) -> str:
        return (parsed_input.get("context") or "I’m reaching out regarding the following.").strip()

    def _suggest_ask(self, intent: str, parsed_input: Dict[str, Any]) -> str:
        ask = (parsed_input.get("ask") or "").strip()
        if ask:
            return ask
        if intent == "follow_up":
            return "Could you share an update when you have a moment?"
        if intent == "request":
            return "Could you please help with this?"
        if intent == "apology":
            return "I’ll make sure this is resolved promptly."
        if intent == "outreach":
            return "Would you be open to a brief chat?"
        return "Please let me know your thoughts."

    def _suggest_closing(self, tone_label: str) -> str:
        if tone_label == "formal":
            return "Thank you for your time."
        if tone_label == "friendly":
            return "Thanks so much!"
        if tone_label == "apologetic":
            return "Thank you for your understanding."
        if tone_label == "assertive":
            return "Thanks in advance for your help."
        return "Thanks,"

    def _suggest_signature(self) -> str:
        # Personalizer will replace this later.
        return "[Your Name]"
