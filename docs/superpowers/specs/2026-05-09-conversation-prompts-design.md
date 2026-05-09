# Conversation Prompts Design

**Date:** 2026-05-09
**Module:** 6 (conversation-prompts)
**Status:** Approved

---

## 1. Goal

Build a prompt library for the outbound voice AI agent that:
- Defines reusable, type-safe `PromptTemplate` objects in Python
- Serializes templates to JSONB for storage in `campaigns.prompt_template`
- Renders a final system prompt string at dial time by injecting lead variables
- Validates all rendered text against PRD §7 TTS constraints before use
- Provides 3 ready-to-use persona templates covering real estate, recruitment, and financial services

The module is a pure library — no FastAPI routes, no DB connections, no Retell AI calls. Integration with the dialing worker happens in a later session.

---

## 2. Architecture

**Approach: Python dataclasses + JSON serialization**

Templates are Python dataclasses (`PromptTemplate`, `FlowStep`, `Objection`, `PersonaConfig`). Each template exposes `to_jsonb()` for DB storage and `from_jsonb()` for hydration at runtime. A `PromptRenderer` converts a JSONB dict + lead variables into a system prompt string. A `ConstraintValidator` checks the rendered string against TTS rules.

```
app/conversation_prompts/
├── __init__.py
├── schemas.py          # PromptTemplate, FlowStep, Objection, PersonaConfig dataclasses
├── renderer.py         # PromptRenderer: JSONB dict + lead_vars → system prompt string
├── validator.py        # ConstraintValidator: rendered string → list[ConstraintError]
└── templates/
    ├── __init__.py
    ├── real_estate.py          # RealEstateLeadQualifier
    ├── recruitment.py          # RecruitmentScreener
    └── financial_services.py  # FinancialServicesQualifier

tests/unit/
├── test_prompt_schemas.py
├── test_prompt_renderer.py
├── test_prompt_validator.py
└── test_prompt_templates.py
```

**Data flow:**

```
templates/*.py
    └─ build_template() → PromptTemplate
            └─ .to_jsonb() → dict ──────────────────────────► campaigns.prompt_template (DB)
                                                                      │
                                              (dialing worker loads) ◄┘
                                                                      │
                                          PromptRenderer.render(dict, lead_vars)
                                                                      │
                                                                      ▼
                                                          system prompt string
                                                                      │
                                                    ConstraintValidator.check(str)
                                                                      │
                                                          POST to Retell AI agent
```

---

## 3. Shared Types — `schemas.py`

```python
from dataclasses import dataclass, field

@dataclass
class PersonaConfig:
    name: str   # typically "{agent_name}" — substituted at render time
    tone: str
    pace: str

@dataclass
class FlowStep:
    step: int
    text: str           # TTS-safe; ≤ 12 words per sentence; vars allowed
    wait_for_ack: bool  # True = must not advance until user responds

@dataclass
class Objection:
    trigger: str    # keyword/phrase the user says
    response: str   # TTS-safe reply; ≤ 12 words per sentence

@dataclass
class PromptTemplate:
    persona:    PersonaConfig
    objective:  str             # single sentence ≤ 12 words; vars allowed
    flow:       list[FlowStep]
    objections: list[Objection]
    escape:     str             # fallback for anger/confusion

    def to_jsonb(self) -> dict: ...
    @classmethod
    def from_jsonb(cls, data: dict) -> "PromptTemplate": ...
```

Injectable variables (substituted by the renderer):
- `{first_name}` — lead's first name
- `{company}` — lead's company
- `{product_name}` — property / role / financial product
- `{agent_name}` — the AI persona's name (set per campaign)

---

## 4. Renderer — `renderer.py`

**Interface:**

```python
class PromptRenderer:
    def render(self, template_dict: dict, lead_vars: dict[str, str]) -> str:
        ...
```

**Steps:**
1. Hydrate `PromptTemplate.from_jsonb(template_dict)`
2. Substitute `{first_name}`, `{company}`, `{product_name}`, `{agent_name}` across all text fields using `str.format_map(lead_vars)`
3. Raise `KeyError` if any required variable is missing from `lead_vars`
4. Assemble and return the final string in this structure:

```
You are {agent_name}, a friendly junior operations assistant.
Tone: {tone}. Pace: {pace}.

Objective: {objective}

Conversation flow:
Step 1: {text}  [wait for acknowledgement]
Step 2: {text}
...

Objection handling:
If the person says "{trigger}": {response}
...

If you sense anger or confusion: {escape}
```

The renderer does not call `ConstraintValidator` by default. Pass `strict=True` to raise on the first constraint violation.

---

## 5. Validator — `validator.py`

**Interface:**

```python
@dataclass(frozen=True)
class ConstraintError:
    rule:    str   # "sentence_length" | "no_bullets" | "no_special_chars"
    excerpt: str   # the offending text

class ConstraintValidator:
    def check(self, rendered: str) -> list[ConstraintError]:
        ...
```

**Rules (applied to the rendered string after variable substitution):**

| Rule | Check |
|---|---|
| `sentence_length` | Split on `.`, `!`, `?`; each segment (stripped) must be ≤ 12 words |
| `no_bullets` | No line starting with `-`, `*`, `•`, or a digit followed by `.` |
| `no_special_chars` | No `[`, `]`, `#`, `**`, `__` anywhere in TTS text sections |

Returns an empty list for a fully valid prompt. Used in tests; optionally enforced at render time via `strict=True`.

---

## 6. The 3 Templates

All text authored to PRD §7 rules: ≤ 12 words per sentence, no bullets, no special chars, acronyms spelled phonetically, natural fillers included. Agent role: junior operations assistant, not a sales closer.

### 6.1 Real Estate Lead Qualifier (`real_estate.py`)

| Field | Value |
|---|---|
| Persona name | `{agent_name}` |
| Tone | friendly, professional, unhurried |
| Objective | Qualify interest in `{product_name}` and book a site visit |
| Flow steps | 6 |
| Objections | busy, not interested, already seen it |

**Flow:**
1. Greeting + identity check (wait for ack)
2. Purpose statement — one sentence (no ack required)
3. Interest check: ask if they are still looking (wait for ack)
4. Site visit offer (wait for ack)
5. Availability question (wait for ack)
6. Confirm booking + close

**Sample objection (authored to rules):**
- "busy" → `"Of course. Can I call you back at a better time?"`
- "not interested" → `"Absolutely, I understand. Have a great day."`
- "already seen it" → `"Got it. We have other options you might like."`

### 6.2 Recruitment Screener (`recruitment.py`)

| Field | Value |
|---|---|
| Persona name | `{agent_name}` |
| Tone | warm, encouraging, professional |
| Objective | Screen `{first_name}` for `{product_name}` role and schedule an interview |
| Flow steps | 6 |
| Objections | busy, not looking, salary concern |

**Flow:**
1. Greeting + confirm name (wait for ack)
2. Brief role intro — one sentence (no ack required)
3. Confirm active interest (wait for ack)
4. One eligibility question (wait for ack)
5. Interview scheduling offer (wait for ack)
6. Confirm slot + close

**Sample objections:**
- "busy" → `"No problem at all. When is a better time?"`
- "not looking" → `"I understand completely. All the best to you."`
- "salary" → `"That is a fair question. The team can discuss that with you."`

### 6.3 Financial Services Qualifier (`financial_services.py`)

| Field | Value |
|---|---|
| Persona name | `{agent_name}` |
| Tone | calm, trustworthy, unhurried |
| Objective | Qualify `{first_name}` from `{company}` for `{product_name}` and book a callback |
| Flow steps | 6 |
| Objections | busy, not interested, already have coverage |

**Flow:**
1. Greeting + identity check (wait for ack)
2. Purpose statement — one sentence (no ack required)
3. Eligibility question (wait for ack)
4. Brief product benefit — one sentence (no ack required)
5. Callback offer (wait for ack)
6. Confirm callback time + close

**Sample objections:**
- "busy" → `"Of course. Can I call back at a better time?"`
- "not interested" → `"I understand. Thank you for your time."`
- "already have coverage" → `"Got it. Umm, just checking if we can offer better terms."`

**Escape (all templates):**
`"I understand. May I send you the details by email instead?"`

---

## 7. Testing

```
tests/unit/
├── test_prompt_schemas.py
│   └── test_round_trip: to_jsonb() → from_jsonb() → assert all fields equal original
│
├── test_prompt_renderer.py
│   ├── test_renders_all_vars: 4 vars injected; none appear as raw placeholders in output
│   ├── test_missing_var_raises: KeyError when lead_vars omits a required key
│   └── test_output_is_nonempty_str: rendered result is str with len > 0
│
├── test_prompt_validator.py
│   ├── test_long_sentence_caught: sentence > 12 words → ConstraintError(rule="sentence_length")
│   ├── test_bullet_caught: line starting with "-" → ConstraintError(rule="no_bullets")
│   ├── test_special_char_caught: "#" in text → ConstraintError(rule="no_special_chars")
│   └── test_clean_text_passes: valid TTS text → empty list
│
└── test_prompt_templates.py
    ├── test_real_estate_validates: build_template() passes ConstraintValidator with empty error list
    ├── test_real_estate_renders: renders without error using sample lead_vars
    ├── test_recruitment_validates / test_recruitment_renders
    └── test_financial_services_validates / test_financial_services_renders
```

No live Retell AI calls in this module. All tests run offline.

---

## 8. PRD Compliance Checklist

| Rule (PRD §7) | Enforced by |
|---|---|
| Max 12 words per sentence | `ConstraintValidator.sentence_length` + template authoring |
| No bullets / lists | `ConstraintValidator.no_bullets` |
| No special chars in TTS | `ConstraintValidator.no_special_chars` |
| Spell acronyms phonetically | Template authoring (e.g. "Gee See See" not "GCC") |
| Natural fillers | Template authoring ("umm", "got it", "let me check") |
| Wait for ack before advancing | `FlowStep.wait_for_ack = True` on each blocking step |
| Agent role: operations assistant, not sales closer | Persona objective wording + escape phrasing |

---

*Owner: Srinivas / Fidelitus Corp + SherpaVector*
