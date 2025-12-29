from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Optional


class SQLiteTemplateStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS email_templates (
                    template_id TEXT PRIMARY KEY,
                    intent TEXT NOT NULL,
                    tone_label TEXT NOT NULL,
                    name TEXT NOT NULL,
                    body TEXT NOT NULL,
                    meta_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_email_templates_intent_tone ON email_templates(intent, tone_label);"
            )
            conn.commit()

    def upsert_template(self, tpl: Dict[str, Any]) -> None:
        meta_json = json.dumps(tpl.get("meta") or {})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO email_templates(template_id, intent, tone_label, name, body, meta_json, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(template_id) DO UPDATE SET
                    intent=excluded.intent,
                    tone_label=excluded.tone_label,
                    name=excluded.name,
                    body=excluded.body,
                    meta_json=excluded.meta_json,
                    updated_at=datetime('now');
                """,
                (
                    tpl["template_id"],
                    tpl["intent"],
                    tpl["tone_label"],
                    tpl["name"],
                    tpl["body"],
                    meta_json,
                ),
            )
            conn.commit()

    def get_best_template(
        self,
        *,
        intent: str,
        tone_label: str,
        constraints: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Simple selection strategy (v1):
          1) exact match intent + tone_label
          2) exact match intent + 'neutral'
          3) fallback to 'other' + tone_label
          4) fallback to 'other' + 'neutral'
        """
        candidates = [
            (intent, tone_label),
            (intent, "neutral"),
            ("other", tone_label),
            ("other", "neutral"),
        ]

        with self._connect() as conn:
            for i, t in candidates:
                row = conn.execute(
                    """
                    SELECT template_id, intent, tone_label, name, body, meta_json
                    FROM email_templates
                    WHERE intent = ? AND tone_label = ?
                    LIMIT 1;
                    """,
                    (i, t),
                ).fetchone()
                if row:
                    meta = {}
                    try:
                        meta = json.loads(row["meta_json"] or "{}")
                    except Exception:
                        meta = {}
                    return {
                        "template_id": row["template_id"],
                        "intent": row["intent"],
                        "tone_label": row["tone_label"],
                        "name": row["name"],
                        "body": row["body"],
                        "meta": meta,
                    }

        return None
