import pytest

from src.templates.engine import EmailTemplateEngine


class DummyStore:
    def __init__(self, tpl=None):
        self.tpl = tpl

    def get_best_template(self, *, intent, tone_label, constraints):
        return self.tpl


def test_engine_build_plan_uses_template_and_renders_skeleton():
    tpl = {
        "template_id": "request_formal_v1",
        "intent": "request",
        "tone_label": "formal",
        "name": "Request Formal",
        "body": "Subject: {{subject}}\n\n{{greeting}}\n\n{{ask}}\n\n{{closing}}\n{{signature}}\n",
        "meta": {"version": 1},
    }
    engine = EmailTemplateEngine(DummyStore(tpl))

    plan = engine.build_plan(
        intent="request",
        tone_params={"tone_label": "formal"},
        constraints={"length": "short"},
        parsed_input={"primary_request": "Access request", "ask": "grant access to the repo"},
    )

    assert plan["template_id"] == "request_formal_v1"
    assert "Subject:" in plan["rendered_skeleton"]
    assert "grant access to the repo" in plan["rendered_skeleton"]
    assert plan["length_budget"]["max_words"] <= 200  # short budget
    assert plan["format"]["use_subject"] is True


def test_engine_defaults_when_no_template_found():
    engine = EmailTemplateEngine(DummyStore(None))

    plan = engine.build_plan(
        intent="follow_up",
        tone_params={},  # no tone provided
        constraints={},  # no length constraint
        parsed_input={},
    )

    assert plan["template_id"] is None
    assert "Subject:" in plan["rendered_skeleton"]
    # no tone -> neutral
    assert plan["tone_label"] == "neutral"
    # default length should be medium
    assert plan["length_hint"] in {"medium", "short"}  # per your v1 mapping
