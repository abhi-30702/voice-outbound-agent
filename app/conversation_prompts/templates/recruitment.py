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
            tone="warm, encouraging, professional",
            pace="measured",
        ),
        objective="Screen {first_name} for {product_name} and schedule an interview.",
        flow=[
            FlowStep(
                step=1,
                text="Hi, is this {first_name}?",
                wait_for_ack=True,
            ),
            FlowStep(
                step=2,
                text="I am {agent_name}. I am calling about a great opportunity.",
                wait_for_ack=False,
            ),
            FlowStep(
                step=3,
                text="Are you currently open to new career opportunities?",
                wait_for_ack=True,
            ),
            FlowStep(
                step=4,
                text="Great. This role needs strong communication and teamwork skills.",
                wait_for_ack=True,
            ),
            FlowStep(
                step=5,
                text="Could we schedule a quick interview call this week?",
                wait_for_ack=True,
            ),
            FlowStep(
                step=6,
                text="Perfect. I will share the details shortly. Thank you, {first_name}.",
                wait_for_ack=False,
            ),
        ],
        objections=[
            Objection(
                trigger="busy",
                response="No problem at all. When is a better time?",
            ),
            Objection(
                trigger="not looking",
                response="I understand completely. All the best to you.",
            ),
            Objection(
                trigger="salary",
                response="That is a fair question. The team can discuss that.",
            ),
        ],
        escape="I understand. May I send you the details by email instead?",
    )
