from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Optional


class SQLiteProfileStore:
    """
    Minimal profile store.
    - user_profiles: one row per user_id, JSON blob for profile fields.
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
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """
            )
            conn.commit()

    def get_profile(self, user_id: str) -> Dict[str, Any]:
        if not user_id:
            return {}

        with self._connect() as conn:
            row = conn.execute(
                "SELECT profile_json FROM user_profiles WHERE user_id = ? LIMIT 1;",
                (user_id,),
            ).fetchone()

        if not row:
            return {}

        try:
            data = json.loads(row["profile_json"] or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def upsert_profile(self, user_id: str, profile: Dict[str, Any]) -> None:
        profile_json = json.dumps(profile or {})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_profiles(user_id, profile_json, updated_at)
                VALUES(?, ?, datetime('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    profile_json=excluded.profile_json,
                    updated_at=datetime('now');
                """,
                (user_id, profile_json),
            )
            conn.commit()
