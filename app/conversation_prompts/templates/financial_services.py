from app.conversation_prompts.schemas import (
    FlowStep,
    Objection,
    PersonaConfig,
    PromptTemplate,
)


def build_template() -> PromptTemplate:
    return PromptTemplate(
        persona=PersonaConfig(
            name="{agent_name}",
            tone="calm, trustworthy, unhurried",
            pace="measured",
        ),
        objective="Qualify {first_name} for {product_name} and book a callback.",
        flow=[
            FlowStep(
                step=1,
                text="Hi, may I speak with {first_name}?",
                wait_for_ack=True,
            ),
            FlowStep(
                step=2,
                text="This is {agent_name} calling about {product_name}.",
                wait_for_ack=False,
            ),
            FlowStep(
                step=3,
                text="Do you currently have a financial plan in place?",
                wait_for_ack=True,
            ),
            FlowStep(
                step=4,
                text="Umm, many of our clients find it very helpful.",
                wait_for_ack=False,
            ),
            FlowStep(
                step=5,
                text="May I arrange a quick callback from our advisor?",
                wait_for_ack=True,
            ),
            FlowStep(
                step=6,
                text="Got it. I will arrange that callback for you. Thank you.",
                wait_for_ack=False,
            ),
        ],
        objections=[
            Objection(
                trigger="busy",
                response="Of course. Can I call back at a better time?",
            ),
            Objection(
                trigger="not interested",
                response="I understand. Thank you for your time.",
            ),
            Objection(
                trigger="already have coverage",
                response="Got it. Umm, we might offer better terms for you.",
            ),
        ],
        escape="I understand. May I send you the details by email instead?",
    )
