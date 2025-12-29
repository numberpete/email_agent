from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class TemplateStore(Protocol):
    """Storage abstraction for templates."""

    def get_best_template(
        self,
        *,
        intent: str,
        tone_label: str,
        constraints: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Returns a dict like:
          {
            "template_id": str,
            "intent": str,
            "tone_label": str,
            "name": str,
            "body": str,
            "meta": dict
          }
        or None if not found.
        """
        ...
