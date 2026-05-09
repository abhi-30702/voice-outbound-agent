import pytest

from app.conversation_prompts.renderer import PromptRenderer
from app.conversation_prompts.schemas import (
    FlowStep,
    Objection,
    PersonaConfig,
    PromptTemplate,
)

# Minimal template that exercises all 4 injectable variables
_TEMPLATE = PromptTemplate(
    persona=PersonaConfig(name="{agent_name}", tone="warm", pace="measured"),
    objective="Call {first_name} from {company} about {product_name}.",
    flow=[
        FlowStep(step=1, text="Hi {first_name}, this is {agent_name}.", wait_for_ack=True),
        FlowStep(step=2, text="I am calling about {product_name}.", wait_for_ack=False),
    ],
    objections=[Objection(trigger="busy", response="No problem.")],
    escape="May I send details by email?",
)

_VARS = {
    "first_name": "Ravi",
    "company": "TCS",
    "product_name": "Term Plan",
    "agent_name": "Priya",
}


def test_renders_all_vars():
    result = PromptRenderer().render(_TEMPLATE.to_jsonb(), _VARS)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "{first_name}" not in result
    assert "{company}" not in result
    assert "{product_name}" not in result
    assert "{agent_name}" not in result


def test_rendered_values_appear_in_output():
    result = PromptRenderer().render(_TEMPLATE.to_jsonb(), _VARS)
    assert "Ravi" in result
    assert "TCS" in result
    assert "Term Plan" in result
    assert "Priya" in result


def test_wait_for_ack_annotation_present():
    result = PromptRenderer().render(_TEMPLATE.to_jsonb(), _VARS)
    lines = result.splitlines()
    step1_line = next(l for l in lines if l.startswith("Step 1:"))
    assert "(Wait for response.)" in step1_line


def test_no_ack_annotation_absent_for_non_ack_step():
    result = PromptRenderer().render(_TEMPLATE.to_jsonb(), _VARS)
    lines = result.splitlines()
    step2_line = next(l for l in lines if l.startswith("Step 2:"))
    assert "(Wait for response.)" not in step2_line


def test_missing_var_raises_key_error():
    incomplete_vars = {"agent_name": "Priya"}  # missing first_name, company, product_name
    with pytest.raises(KeyError):
        PromptRenderer().render(_TEMPLATE.to_jsonb(), incomplete_vars)


def test_strict_mode_raises_on_violation():
    bad_template = PromptTemplate(
        persona=PersonaConfig(name="{agent_name}", tone="warm", pace="measured"),
        objective="Short objective.",
        flow=[
            FlowStep(
                step=1,
                # 17 words — violates 12-word rule
                text="This is a very long sentence that has way too many words and will fail validation.",
                wait_for_ack=False,
            )
        ],
        objections=[],
        escape="Goodbye.",
    )
    with pytest.raises(ValueError, match="Constraint violations"):
        PromptRenderer().render(
            bad_template.to_jsonb(),
            {"agent_name": "Priya", "first_name": "X", "company": "Y", "product_name": "Z"},
            strict=True,
        )
