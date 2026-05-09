# Conversation Prompts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-Python prompt library with 3 persona templates, a JSONB serializer, a renderer that injects lead variables, and a constraint validator that enforces PRD §7 TTS rules.

**Architecture:** Python dataclasses (`PromptTemplate`, `FlowStep`, `Objection`, `PersonaConfig`) serialize to/from JSONB dicts for DB storage in `campaigns.prompt_template`. At dial time a `PromptRenderer` hydrates the dict and substitutes lead variables (`{first_name}`, `{company}`, `{product_name}`, `{agent_name}`) to produce a final system prompt string. A `ConstraintValidator` checks the rendered string line-by-line against three TTS rules (≤ 12 words/sentence, no bullets, no special chars).

**Tech Stack:** Python 3.13, stdlib only (`dataclasses`, `re`), pytest.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `app/conversation_prompts/__init__.py` | Package marker (empty) |
| Create | `app/conversation_prompts/schemas.py` | All dataclasses + to_jsonb/from_jsonb |
| Create | `app/conversation_prompts/validator.py` | ConstraintError + ConstraintValidator |
| Create | `app/conversation_prompts/renderer.py` | PromptRenderer.render() |
| Create | `app/conversation_prompts/templates/__init__.py` | Sub-package marker (empty) |
| Create | `app/conversation_prompts/templates/real_estate.py` | build_template() → real estate persona |
| Create | `app/conversation_prompts/templates/recruitment.py` | build_template() → recruitment persona |
| Create | `app/conversation_prompts/templates/financial_services.py` | build_template() → financial services persona |
| Create | `tests/unit/test_prompt_schemas.py` | Round-trip serialization tests |
| Create | `tests/unit/test_prompt_renderer.py` | Variable injection + error tests |
| Create | `tests/unit/test_prompt_validator.py` | Constraint rule tests |
| Create | `tests/unit/test_prompt_templates.py` | All 3 templates validate + render clean |

---

## Task 1: Package scaffold + Schemas

**Files:**
- Create: `app/conversation_prompts/__init__.py`
- Create: `app/conversation_prompts/templates/__init__.py`
- Create: `app/conversation_prompts/schemas.py`
- Create: `tests/unit/test_prompt_schemas.py`

- [ ] **Step 1: Create the two empty package markers**

```python
# app/conversation_prompts/__init__.py
# (empty file — 0 bytes)
```

```python
# app/conversation_prompts/templates/__init__.py
# (empty file — 0 bytes)
```

Run: `python -c "import app.conversation_prompts"`
Expected: no output (import succeeds)

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_prompt_schemas.py`:

```python
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
```

- [ ] **Step 3: Run the test — confirm it fails with ImportError**

```
pytest tests/unit/test_prompt_schemas.py -v
```

Expected: `ImportError: cannot import name 'FlowStep' from 'app.conversation_prompts.schemas'`

- [ ] **Step 4: Implement `schemas.py`**

Create `app/conversation_prompts/schemas.py`:

```python
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
```

- [ ] **Step 5: Run the test — confirm it passes**

```
pytest tests/unit/test_prompt_schemas.py -v
```

Expected:
```
test_prompt_schemas.py::test_round_trip PASSED
test_prompt_schemas.py::test_to_jsonb_shape PASSED
test_prompt_schemas.py::test_from_jsonb_preserves_flow_order PASSED
```

- [ ] **Step 6: Commit**

```
git add app/conversation_prompts/__init__.py app/conversation_prompts/templates/__init__.py app/conversation_prompts/schemas.py tests/unit/test_prompt_schemas.py
git commit -m "feat(conversation-prompts): add PromptTemplate schemas with JSONB serialization"
```

---

## Task 2: Constraint Validator

**Files:**
- Create: `app/conversation_prompts/validator.py`
- Create: `tests/unit/test_prompt_validator.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_prompt_validator.py`:

```python
from app.conversation_prompts.validator import ConstraintError, ConstraintValidator


def test_clean_text_passes():
    validator = ConstraintValidator()
    text = "Hi, this is Priya. I am calling about a great plan. Are you free?"
    errors = validator.check(text)
    assert errors == []


def test_long_sentence_caught():
    validator = ConstraintValidator()
    # 16 words — well over the 12-word limit
    text = "This sentence has sixteen words in it and goes way over the allowed maximum limit right here."
    errors = validator.check(text)
    sentence_errors = [e for e in errors if e.rule == "sentence_length"]
    assert len(sentence_errors) >= 1
    assert errors[0].rule == "sentence_length"


def test_bullet_caught():
    validator = ConstraintValidator()
    text = "Some intro.\n- first item\n- second item"
    errors = validator.check(text)
    bullet_errors = [e for e in errors if e.rule == "no_bullets"]
    assert len(bullet_errors) == 2


def test_numbered_list_caught():
    validator = ConstraintValidator()
    text = "Steps:\n1. Do this\n2. Do that"
    errors = validator.check(text)
    bullet_errors = [e for e in errors if e.rule == "no_bullets"]
    assert len(bullet_errors) == 2


def test_special_char_bracket_caught():
    validator = ConstraintValidator()
    text = "This has a [bracket] in it."
    errors = validator.check(text)
    special_errors = [e for e in errors if e.rule == "no_special_chars"]
    assert len(special_errors) >= 1


def test_special_char_hash_caught():
    validator = ConstraintValidator()
    text = "# Heading\nSome text."
    errors = validator.check(text)
    special_errors = [e for e in errors if e.rule == "no_special_chars"]
    assert len(special_errors) >= 1


def test_special_char_double_asterisk_caught():
    validator = ConstraintValidator()
    text = "This is **bold** text."
    errors = validator.check(text)
    special_errors = [e for e in errors if e.rule == "no_special_chars"]
    assert len(special_errors) >= 1


def test_constraint_error_fields():
    validator = ConstraintValidator()
    text = "This is **bold**."
    errors = validator.check(text)
    err = next(e for e in errors if e.rule == "no_special_chars")
    assert isinstance(err.rule, str)
    assert isinstance(err.excerpt, str)
    assert len(err.excerpt) > 0
```

- [ ] **Step 2: Run the test — confirm it fails with ImportError**

```
pytest tests/unit/test_prompt_validator.py -v
```

Expected: `ImportError: cannot import name 'ConstraintError' from 'app.conversation_prompts.validator'`

- [ ] **Step 3: Implement `validator.py`**

Create `app/conversation_prompts/validator.py`:

```python
from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ConstraintError:
    rule: str
    excerpt: str


class ConstraintValidator:
    MAX_WORDS = 12
    _BULLET = re.compile(r'^(?:[-*•]|\d+\.)')
    _SPECIAL = re.compile(r'\[|\]|#|\*\*|__')

    def check(self, rendered: str) -> list[ConstraintError]:
        errors: list[ConstraintError] = []
        errors.extend(self._check_sentence_length(rendered))
        errors.extend(self._check_no_bullets(rendered))
        errors.extend(self._check_no_special_chars(rendered))
        return errors

    def _check_sentence_length(self, text: str) -> list[ConstraintError]:
        errors: list[ConstraintError] = []
        for line in text.splitlines():
            for sentence in re.split(r'[.!?]', line):
                stripped = sentence.strip()
                if not stripped:
                    continue
                if len(stripped.split()) > self.MAX_WORDS:
                    errors.append(ConstraintError(rule="sentence_length", excerpt=stripped[:80]))
        return errors

    def _check_no_bullets(self, text: str) -> list[ConstraintError]:
        errors: list[ConstraintError] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and self._BULLET.match(stripped):
                errors.append(ConstraintError(rule="no_bullets", excerpt=stripped[:80]))
        return errors

    def _check_no_special_chars(self, text: str) -> list[ConstraintError]:
        errors: list[ConstraintError] = []
        for match in self._SPECIAL.finditer(text):
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)
            errors.append(ConstraintError(rule="no_special_chars", excerpt=text[start:end]))
        return errors
```

- [ ] **Step 4: Run the test — confirm it passes**

```
pytest tests/unit/test_prompt_validator.py -v
```

Expected: all 8 tests PASSED.

- [ ] **Step 5: Commit**

```
git add app/conversation_prompts/validator.py tests/unit/test_prompt_validator.py
git commit -m "feat(conversation-prompts): add ConstraintValidator with sentence, bullet, special-char rules"
```

---

## Task 3: Prompt Renderer

**Files:**
- Create: `app/conversation_prompts/renderer.py`
- Create: `tests/unit/test_prompt_renderer.py`

**Rendered output format** (for reference when reading tests):

```
You are {agent_name}, a friendly junior operations assistant.
Tone: {tone}. Pace: {pace}.

Objective: {objective}

Conversation flow:
Step 1: {text} (Wait for response.)
Step 2: {text}
...

Objection handling:
If the person says "{trigger}": {response}
...

If you sense anger or confusion: {escape}
```

Note: `(Wait for response.)` is appended (same line) only when `wait_for_ack=True`. This notation uses parentheses — no brackets — so `ConstraintValidator.no_special_chars` passes.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_prompt_renderer.py`:

```python
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
```

- [ ] **Step 2: Run the test — confirm it fails with ImportError**

```
pytest tests/unit/test_prompt_renderer.py -v
```

Expected: `ImportError: cannot import name 'PromptRenderer' from 'app.conversation_prompts.renderer'`

- [ ] **Step 3: Implement `renderer.py`**

Create `app/conversation_prompts/renderer.py`:

```python
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
```

- [ ] **Step 4: Run the test — confirm it passes**

```
pytest tests/unit/test_prompt_renderer.py -v
```

Expected: all 6 tests PASSED.

- [ ] **Step 5: Commit**

```
git add app/conversation_prompts/renderer.py tests/unit/test_prompt_renderer.py
git commit -m "feat(conversation-prompts): add PromptRenderer with variable injection and strict mode"
```

---

## Task 4: Real Estate Template

**Files:**
- Create: `app/conversation_prompts/templates/real_estate.py`
- Create: `tests/unit/test_prompt_templates.py` (first 2 tests only)

**Template spec:**
- Persona: `{agent_name}`, tone "friendly, professional, unhurried", pace "measured"
- Objective: `"Qualify interest in {product_name} and book a site visit."`
- 6 flow steps (steps 1, 3, 4, 5 wait for ack; steps 2, 6 do not)
- 3 objections: "busy", "not interested", "already seen it"
- Escape: `"I understand. May I send you the details by email instead?"`

All text ≤ 12 words per sentence, no bullets, no special chars (verified by the test).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_prompt_templates.py` with just the real estate tests:

```python
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
```

- [ ] **Step 2: Run the tests — confirm they fail**

```
pytest tests/unit/test_prompt_templates.py -v
```

Expected: `ImportError: cannot import name 'build_template' from 'app.conversation_prompts.templates.real_estate'`

- [ ] **Step 3: Implement `templates/real_estate.py`**

Create `app/conversation_prompts/templates/real_estate.py`:

```python
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
```

- [ ] **Step 4: Run the tests — confirm they pass**

```
pytest tests/unit/test_prompt_templates.py -v
```

Expected: all 4 real estate tests PASSED.

- [ ] **Step 5: Commit**

```
git add app/conversation_prompts/templates/real_estate.py tests/unit/test_prompt_templates.py
git commit -m "feat(conversation-prompts): add real estate lead qualifier template"
```

---

## Task 5: Recruitment Template

**Files:**
- Modify: `tests/unit/test_prompt_templates.py` (add recruitment tests)
- Create: `app/conversation_prompts/templates/recruitment.py`

**Template spec:**
- Persona: `{agent_name}`, tone "warm, encouraging, professional", pace "measured"
- Objective: `"Screen {first_name} for {product_name} and schedule an interview."`
- 6 flow steps (steps 1, 3, 4, 5 wait for ack; steps 2, 6 do not)
- 3 objections: "busy", "not looking", "salary"
- Escape: `"I understand. May I send you the details by email instead?"`

- [ ] **Step 1: Add the failing recruitment tests**

Append to `tests/unit/test_prompt_templates.py`:

```python
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
```

- [ ] **Step 2: Run the tests — confirm the new ones fail**

```
pytest tests/unit/test_prompt_templates.py -v
```

Expected: 4 real estate tests PASSED, 4 recruitment tests FAILED with ImportError.

- [ ] **Step 3: Implement `templates/recruitment.py`**

Create `app/conversation_prompts/templates/recruitment.py`:

```python
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
```

- [ ] **Step 4: Run the tests — confirm all pass**

```
pytest tests/unit/test_prompt_templates.py -v
```

Expected: all 8 tests PASSED (4 real estate + 4 recruitment).

- [ ] **Step 5: Commit**

```
git add app/conversation_prompts/templates/recruitment.py tests/unit/test_prompt_templates.py
git commit -m "feat(conversation-prompts): add recruitment screener template"
```

---

## Task 6: Financial Services Template

**Files:**
- Modify: `tests/unit/test_prompt_templates.py` (add financial services tests)
- Create: `app/conversation_prompts/templates/financial_services.py`

**Template spec:**
- Persona: `{agent_name}`, tone "calm, trustworthy, unhurried", pace "measured"
- Objective: `"Qualify {first_name} for {product_name} and book a callback."`
- 6 flow steps (steps 1, 3, 5 wait for ack; steps 2, 4, 6 do not)
- 3 objections: "busy", "not interested", "already have coverage"
- Escape: `"I understand. May I send you the details by email instead?"`

- [ ] **Step 1: Add the failing financial services tests**

Append to `tests/unit/test_prompt_templates.py`:

```python
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
```

Sample vars used: `{"first_name": "Ravi", "company": "TCS", "product_name": "Prestige Park", "agent_name": "Priya"}` — already defined as `_SAMPLE_VARS` at the top of the test file.

- [ ] **Step 2: Run the tests — confirm the new ones fail**

```
pytest tests/unit/test_prompt_templates.py -v
```

Expected: 8 earlier tests PASSED, 4 financial services tests FAILED with ImportError.

- [ ] **Step 3: Implement `templates/financial_services.py`**

Create `app/conversation_prompts/templates/financial_services.py`:

```python
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
```

- [ ] **Step 4: Run the tests — confirm all pass**

```
pytest tests/unit/test_prompt_templates.py -v
```

Expected: all 12 tests PASSED (4 real estate + 4 recruitment + 4 financial services).

- [ ] **Step 5: Commit**

```
git add app/conversation_prompts/templates/financial_services.py tests/unit/test_prompt_templates.py
git commit -m "feat(conversation-prompts): add financial services qualifier template"
```

---

## Task 7: Full Suite Verification

**Files:** No new files — just verification.

- [ ] **Step 1: Run the complete unit test suite**

```
pytest tests/unit/ -v
```

Expected: all tests pass. Count should include all pre-existing VAD, webhook, dialing-worker, post-call-analysis tests plus the new 3 + 6 + 8 + 12 = 29 conversation-prompts tests.

- [ ] **Step 2: Verify module imports cleanly**

```
python -c "
from app.conversation_prompts.schemas import PromptTemplate
from app.conversation_prompts.renderer import PromptRenderer
from app.conversation_prompts.validator import ConstraintValidator
from app.conversation_prompts.templates.real_estate import build_template as re_t
from app.conversation_prompts.templates.recruitment import build_template as rr_t
from app.conversation_prompts.templates.financial_services import build_template as fs_t
print('All imports OK')
print('Real estate steps:', len(re_t().flow))
print('Recruitment steps:', len(rr_t().flow))
print('Financial services steps:', len(fs_t().flow))
"
```

Expected:
```
All imports OK
Real estate steps: 6
Recruitment steps: 6
Financial services steps: 6
```

- [ ] **Step 3: Final commit**

```
git add .
git commit -m "feat(conversation-prompts): complete Module 6 — 3 persona templates, renderer, validator, 29 tests"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| PromptTemplate, FlowStep, Objection, PersonaConfig dataclasses | Task 1 |
| to_jsonb() / from_jsonb() | Task 1 |
| PromptRenderer.render(dict, lead_vars) | Task 3 |
| KeyError on missing var | Task 3, test_missing_var_raises_key_error |
| strict=True raises ValueError | Task 3, test_strict_mode_raises_on_violation |
| ConstraintValidator.check() → list[ConstraintError] | Task 2 |
| sentence_length rule (≤ 12 words) | Task 2 |
| no_bullets rule | Task 2 |
| no_special_chars rule (`[`, `]`, `#`, `**`, `__`) | Task 2 |
| Real estate template (6 steps, 3 objections) | Task 4 |
| Recruitment template (6 steps, 3 objections) | Task 5 |
| Financial services template (6 steps, 3 objections) | Task 6 |
| All templates pass ConstraintValidator | Tasks 4–6 |
| All templates render with sample vars | Tasks 4–6 |
| `{first_name}`, `{company}`, `{product_name}`, `{agent_name}` injected | Task 3 |
| wait_for_ack annotation in renderer output | Task 3 |
| No DB, no HTTP, no Retell calls | No external deps imported anywhere |

**Placeholder scan:** No TBDs, no "implement later", no "similar to Task N". All steps contain full code.

**Type consistency:**
- `PromptTemplate.from_jsonb` defined in Task 1, called in Task 3 (`renderer.py`) and Tasks 4–6 (via `render()`) — consistent.
- `ConstraintValidator().check()` defined in Task 2, called in Task 3 (`strict=True`) and Tasks 4–6 test assertions — consistent.
- `build_template()` used identically in Tasks 4, 5, 6 test imports — consistent.
- `_SAMPLE_VARS` defined once at top of `test_prompt_templates.py` in Task 4, reused in Tasks 5–6 — consistent.
