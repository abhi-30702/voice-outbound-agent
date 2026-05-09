from __future__ import annotations
from dataclasses import dataclass


@dataclass
class PersonaConfig:
    name: str
    tone: str
    pace: str


@dataclass
class FlowStep:
    step: int
    text: str
    wait_for_ack: bool


@dataclass
class Objection:
    trigger: str
    response: str


@dataclass
class PromptTemplate:
    persona: PersonaConfig
    objective: str
    flow: list[FlowStep]
    objections: list[Objection]
    escape: str

    def to_jsonb(self) -> dict:
        return {
            "persona": {
                "name": self.persona.name,
                "tone": self.persona.tone,
                "pace": self.persona.pace,
            },
            "objective": self.objective,
            "flow": [
                {"step": s.step, "text": s.text, "wait_for_ack": s.wait_for_ack}
                for s in self.flow
            ],
            "objections": [
                {"trigger": o.trigger, "response": o.response}
                for o in self.objections
            ],
            "escape": self.escape,
        }

    @classmethod
    def from_jsonb(cls, data: dict) -> PromptTemplate:
        return cls(
            persona=PersonaConfig(
                name=data["persona"]["name"],
                tone=data["persona"]["tone"],
                pace=data["persona"]["pace"],
            ),
            objective=data["objective"],
            flow=[
                FlowStep(
                    step=s["step"],
                    text=s["text"],
                    wait_for_ack=s["wait_for_ack"],
                )
                for s in data["flow"]
            ],
            objections=[
                Objection(trigger=o["trigger"], response=o["response"])
                for o in data["objections"]
            ],
            escape=data["escape"],
        )
