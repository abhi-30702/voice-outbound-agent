import pytest

from app.conversation_prompts.renderer import PromptRenderer
from app.conversation_prompts.validator import ConstraintValidator
from app.conversation_prompts.templates.real_estate import build_template as build_real_estate

_RENDERER = PromptRenderer()
_VALIDATOR = ConstraintValidator()

_SAMPLE_VARS = {
    "first_name": "Ravi",
    "company": "TCS",
    "product_name": "Prestige Park",
    "agent_name": "Priya",
}


# ── Real Estate ────────────────────────────────────────────────────────────────

def test_real_estate_template_has_six_steps():
    template = build_real_estate()
    assert len(template.flow) == 6


def test_real_estate_template_has_three_objections():
    template = build_real_estate()
    assert len(template.objections) == 3


def test_real_estate_validates():
    template = build_real_estate()
    rendered = _RENDERER.render(template.to_jsonb(), _SAMPLE_VARS)
    errors = _VALIDATOR.check(rendered)
    assert errors == [], f"Constraint violations: {errors}"


def test_real_estate_renders():
    template = build_real_estate()
    rendered = _RENDERER.render(template.to_jsonb(), _SAMPLE_VARS)
    assert isinstance(rendered, str)
    assert len(rendered) > 0
    assert "Ravi" in rendered
    assert "Prestige Park" in rendered
    assert "Priya" in rendered


from app.conversation_prompts.templates.recruitment import build_template as build_recruitment


# ── Recruitment ────────────────────────────────────────────────────────────────

def test_recruitment_template_has_six_steps():
    template = build_recruitment()
    assert len(template.flow) == 6


def test_recruitment_template_has_three_objections():
    template = build_recruitment()
    assert len(template.objections) == 3


def test_recruitment_validates():
    template = build_recruitment()
    rendered = _RENDERER.render(template.to_jsonb(), _SAMPLE_VARS)
    errors = _VALIDATOR.check(rendered)
    assert errors == [], f"Constraint violations: {errors}"


def test_recruitment_renders():
    template = build_recruitment()
    rendered = _RENDERER.render(template.to_jsonb(), _SAMPLE_VARS)
    assert isinstance(rendered, str)
    assert len(rendered) > 0
    assert "Ravi" in rendered
    assert "Priya" in rendered


from app.conversation_prompts.templates.financial_services import build_template as build_financial_services


# ── Financial Services ─────────────────────────────────────────────────────────

def test_financial_services_template_has_six_steps():
    template = build_financial_services()
    assert len(template.flow) == 6


def test_financial_services_template_has_three_objections():
    template = build_financial_services()
    assert len(template.objections) == 3


def test_financial_services_validates():
    template = build_financial_services()
    rendered = _RENDERER.render(template.to_jsonb(), _SAMPLE_VARS)
    errors = _VALIDATOR.check(rendered)
    assert errors == [], f"Constraint violations: {errors}"


def test_financial_services_renders():
    template = build_financial_services()
    rendered = _RENDERER.render(template.to_jsonb(), _SAMPLE_VARS)
    assert isinstance(rendered, str)
    assert len(rendered) > 0
    assert "Ravi" in rendered
    assert "Priya" in rendered
