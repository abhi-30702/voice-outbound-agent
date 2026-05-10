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
            tone="friendly, professional, unhurried",
            pace="measured",
        ),
        objective="Qualify interest in {product_name} and book a site visit.",
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
                text="Are you still looking for a property in this area?",
                wait_for_ack=True,
            ),
            FlowStep(
                step=4,
                text="We would love to arrange a site visit for you.",
                wait_for_ack=True,
            ),
            FlowStep(
                step=5,
                text="Umm, when would be a good time for you?",
                wait_for_ack=True,
            ),
            FlowStep(
                step=6,
                text="Got it. I will confirm your visit. Thank you, {first_name}.",
                wait_for_ack=False,
            ),
        ],
        objections=[
            Objection(
                trigger="busy",
                response="Of course. Can I call you back at a better time?",
            ),
            Objection(
                trigger="not interested",
                response="Absolutely, I understand. Have a great day.",
            ),
            Objection(
                trigger="already seen it",
                response="Got it. We have other options you might like.",
            ),
        ],
        escape="I understand. May I send you the details by email instead?",
    )
