import pytest

from src.templates.sqlite_store import SQLiteTemplateStore


def test_sqlite_template_store_selects_exact_match(tmp_path):
    db = tmp_path / "test.db"
    store = SQLiteTemplateStore(str(db))

    store.upsert_template(
        {
            "template_id": "follow_up_friendly_v1",
            "intent": "follow_up",
            "tone_label": "friendly",
            "name": "Follow-up Friendly",
            "body": "Subject: {{subject}}\n\n{{greeting}}\n\n{{ask}}\n\n{{closing}}\n{{signature}}\n",
            "meta": {"version": 1},
        }
    )

    tpl = store.get_best_template(intent="follow_up", tone_label="friendly", constraints={})
    assert tpl is not None
    assert tpl["template_id"] == "follow_up_friendly_v1"
    assert tpl["intent"] == "follow_up"
    assert tpl["tone_label"] == "friendly"


def test_sqlite_template_store_fallbacks_to_neutral(tmp_path):
    db = tmp_path / "test.db"
    store = SQLiteTemplateStore(str(db))

    store.upsert_template(
        {
            "template_id": "follow_up_neutral_v1",
            "intent": "follow_up",
            "tone_label": "neutral",
            "name": "Follow-up Neutral",
            "body": "Subject: {{subject}}\n\n{{greeting}}\n\n{{ask}}\n\n{{closing}}\n{{signature}}\n",
            "meta": {"version": 1},
        }
    )

    # ask for a tone that doesn't exist; should fall back to intent + neutral
    tpl = store.get_best_template(intent="follow_up", tone_label="assertive", constraints={})
    assert tpl is not None
    assert tpl["template_id"] == "follow_up_neutral_v1"
    assert tpl["tone_label"] == "neutral"


def test_sqlite_template_store_fallbacks_to_other(tmp_path):
    db = tmp_path / "test.db"
    store = SQLiteTemplateStore(str(db))

    store.upsert_template(
        {
            "template_id": "other_neutral_v1",
            "intent": "other",
            "tone_label": "neutral",
            "name": "Generic Neutral",
            "body": "Subject: {{subject}}\n\n{{greeting}}\n\n{{context}}\n\n{{ask}}\n\n{{closing}}\n{{signature}}\n",
            "meta": {"version": 1},
        }
    )

    tpl = store.get_best_template(intent="nonexistent_intent", tone_label="formal", constraints={})
    assert tpl is not None
    assert tpl["template_id"] == "other_neutral_v1"
    assert tpl["intent"] == "other"
    assert tpl["tone_label"] == "neutral"
