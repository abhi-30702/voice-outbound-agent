from app.conversation_prompts.schemas import (
    FlowStep,
    Objection,
    PersonaConfig,
    PromptTemplate,
)


def _make_template() -> PromptTemplate:
    return PromptTemplate(
        persona=PersonaConfig(name="{agent_name}", tone="friendly", pace="measured"),
        objective="Qualify interest in {product_name}.",
        flow=[
            FlowStep(step=1, text="Hi, may I speak with {first_name}?", wait_for_ack=True),
            FlowStep(step=2, text="This is {agent_name} calling.", wait_for_ack=False),
        ],
        objections=[
            Objection(trigger="busy", response="Of course. Call you back?"),
        ],
        escape="May I send you an email instead?",
    )


def test_round_trip():
    original = _make_template()
    restored = PromptTemplate.from_jsonb(original.to_jsonb())
    assert restored == original


def test_to_jsonb_shape():
    data = _make_template().to_jsonb()
    assert set(data.keys()) == {"persona", "objective", "flow", "objections", "escape"}
    assert set(data["persona"].keys()) == {"name", "tone", "pace"}
    assert data["flow"][0] == {"step": 1, "text": "Hi, may I speak with {first_name}?", "wait_for_ack": True}
    assert data["objections"][0] == {"trigger": "busy", "response": "Of course. Call you back?"}


def test_from_jsonb_preserves_flow_order():
    original = _make_template()
    restored = PromptTemplate.from_jsonb(original.to_jsonb())
    assert [s.step for s in restored.flow] == [1, 2]
    assert restored.flow[0].wait_for_ack is True
    assert restored.flow[1].wait_for_ack is False
