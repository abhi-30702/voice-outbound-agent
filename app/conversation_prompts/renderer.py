from __future__ import annotations

from app.conversation_prompts.schemas import PromptTemplate
from app.conversation_prompts.validator import ConstraintValidator


class PromptRenderer:
    def render(
        self,
        template_dict: dict,
        lead_vars: dict[str, str],
        strict: bool = False,
    ) -> str:
        template = PromptTemplate.from_jsonb(template_dict)

        def sub(text: str) -> str:
            return text.format_map(lead_vars)

        lines: list[str] = [
            f"You are {sub(template.persona.name)}, a friendly junior operations assistant.",
            f"Tone: {template.persona.tone}. Pace: {template.persona.pace}.",
            "",
            f"Objective: {sub(template.objective)}",
            "",
            "Conversation flow:",
        ]

        for step in template.flow:
            ack = " (Wait for response.)" if step.wait_for_ack else ""
            lines.append(f"Step {step.step}: {sub(step.text)}{ack}")

        if template.objections:
            lines.append("")
            lines.append("Objection handling:")
            for obj in template.objections:
                lines.append(
                    f'If the person says "{sub(obj.trigger)}": {sub(obj.response)}'
                )

        lines.append("")
        lines.append(f"If you sense anger or confusion: {sub(template.escape)}")

        rendered = "\n".join(lines)

        if strict:
            errors = ConstraintValidator().check(rendered)
            if errors:
                raise ValueError(f"Constraint violations: {errors}")

        return rendered
