from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Optional


class SQLiteMemoryStore:
    """
    Minimal memory store.
    - recipient_threads: one row per user_id + recipient_key, JSON blob for thread state.
    - conversation_events: one row per event in a conversation thread.
    """

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
CREATE TABLE IF NOT EXISTS email_summaries (
  user_id        TEXT NOT NULL,
  recipient_key  TEXT NOT NULL,
  summary_json   TEXT NOT NULL,
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (user_id, recipient_key)
);
                """
            )
            conn.commit()

    def get_past_summary(self, user_id: str, recipient_key: str) -> Dict[str, Any]:
        if not user_id:
            return {}

        with self._connect() as conn:
            row = conn.execute(
                "SELECT summary_json FROM email_summaries WHERE user_id = ? AND recipient_key = ? ORDER BY updated_at DESC LIMIT 1;",
                (user_id, recipient_key),
            ).fetchone()

        if not row:
            return {}

        try:
            data = json.loads(row["summary_json"] or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def upsert_summary(self, user_id: str, recipient_key: str, summary: Dict[str, Any]) -> None:
        summary_json = json.dumps(summary or {})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO email_summaries(user_id, recipient_key, summary_json)
                VALUES(?, ?, ?)
                ON CONFLICT(user_id, recipient_key) DO UPDATE SET
                    summary_json=excluded.summary_json,
                    updated_at=datetime('now');
                """,
                (user_id, recipient_key, summary_json),
            )
            conn.commit()
