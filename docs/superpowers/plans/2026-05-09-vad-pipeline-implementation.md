# VAD Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Silero VAD wrapper with a 4-state machine (QUIET/STARTING/SPEAKING/STOPPING) behind an async push_audio / events queue interface.

**Architecture:** Three focused layers — `silero_wrapper.py` (torch model + resampler), `state_machine.py` (pure deterministic logic), and `pipeline.py` (async orchestrator) — share types from `schemas.py`. No live audio streams, no Retell integration; this is a testable standalone utility.

**Tech Stack:** Python 3.13, silero-vad>=4.0.0, torchaudio>=2.0.0, torch (transitive dep), asyncio, pytest, pytest-asyncio (asyncio_mode=auto already configured)

---

## File Map

| Action | Path |
|--------|------|
| Modify | `requirements.txt` |
| Create | `app/vad_pipeline/__init__.py` |
| Create | `app/vad_pipeline/schemas.py` |
| Create | `app/vad_pipeline/state_machine.py` |
| Create | `app/vad_pipeline/silero_wrapper.py` |
| Create | `app/vad_pipeline/pipeline.py` |
| Create | `app/vad_pipeline/README.md` |
| Create | `tests/unit/test_vad_schemas.py` |
| Create | `tests/unit/test_vad_state_machine.py` |
| Create | `tests/unit/test_vad_silero_wrapper.py` |
| Create | `tests/unit/test_vad_pipeline.py` |

---

### Task 1: Dependencies + Package Skeleton

**Files:**
- Modify: `requirements.txt`
- Create: `app/vad_pipeline/__init__.py`

- [ ] **Step 1: Add dependencies to `requirements.txt`**

Append two lines after the `anthropic>=0.25.0` line. Final file:

```
sqlalchemy==2.0.48
asyncpg==0.30.0
alembic==1.13.0
psycopg2-binary==2.9.9
fastapi==0.115.0
uvicorn==0.30.0
pytest==8.2.0
pytest-asyncio==0.24.0
pydantic==2.6.0
pydantic-settings==2.1.0
pytz==2024.1
httpx==0.27.0
rq==1.16.1
anthropic>=0.25.0
redis>=4.5.0
silero-vad>=4.0.0
torchaudio>=2.0.0
```

- [ ] **Step 2: Install new dependencies**

```powershell
.venv\Scripts\pip install silero-vad torchaudio
```

Expected: both packages install without error. `torch` installs as a transitive dependency of `silero-vad`.

- [ ] **Step 3: Create empty package init**

Create `app/vad_pipeline/__init__.py` — empty file, just marks the directory as a package.

- [ ] **Step 4: Verify imports work**

```powershell
.venv\Scripts\python -c "import silero_vad; import torchaudio; print('OK')"
```

Expected output: `OK`

- [ ] **Step 5: Commit**

```powershell
git add requirements.txt app/vad_pipeline/__init__.py
git commit -m "feat: add silero-vad dependencies and vad_pipeline package skeleton"
```

---

### Task 2: Shared Types — `schemas.py`

**Files:**
- Create: `app/vad_pipeline/schemas.py`
- Create: `tests/unit/test_vad_schemas.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_vad_schemas.py`:

```python
import pytest
from dataclasses import FrozenInstanceError

from app.vad_pipeline.schemas import VADConfig, VADEvent, VADState


def test_vad_state_values():
    assert VADState.QUIET == "quiet"
    assert VADState.STARTING == "starting"
    assert VADState.SPEAKING == "speaking"
    assert VADState.STOPPING == "stopping"


def test_vad_event_is_frozen():
    event = VADEvent(
        prev_state=VADState.QUIET,
        new_state=VADState.STARTING,
        timestamp_ms=100.0,
    )
    with pytest.raises(FrozenInstanceError):
        event.new_state = VADState.SPEAKING  # type: ignore[misc]


def test_vad_event_interrupted_defaults_false():
    event = VADEvent(
        prev_state=VADState.QUIET,
        new_state=VADState.STARTING,
        timestamp_ms=0.0,
    )
    assert event.interrupted is False


def test_vad_config_defaults():
    config = VADConfig()
    assert config.sample_rate == 16000
    assert config.onset_threshold == 0.5
    assert config.offset_threshold == 0.35
    assert config.onset_duration_ms == 200
    assert config.offset_duration_ms == 800
    assert config.max_queue_size == 100
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
.venv\Scripts\pytest tests/unit/test_vad_schemas.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.vad_pipeline.schemas'`

- [ ] **Step 3: Implement `schemas.py`**

Create `app/vad_pipeline/schemas.py`:

```python
from dataclasses import dataclass
from enum import Enum


class VADState(str, Enum):
    QUIET    = "quiet"
    STARTING = "starting"
    SPEAKING = "speaking"
    STOPPING = "stopping"


@dataclass(frozen=True)
class VADEvent:
    prev_state:   VADState
    new_state:    VADState
    timestamp_ms: float
    interrupted:  bool = False


@dataclass
class VADConfig:
    sample_rate:        int   = 16000
    onset_threshold:    float = 0.5
    offset_threshold:   float = 0.35
    onset_duration_ms:  int   = 200
    offset_duration_ms: int   = 800
    max_queue_size:     int   = 100
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
.venv\Scripts\pytest tests/unit/test_vad_schemas.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```powershell
git add app/vad_pipeline/schemas.py tests/unit/test_vad_schemas.py
git commit -m "feat: add VAD pipeline shared types (VADState, VADEvent, VADConfig)"
```

---

### Task 3: State Machine — `state_machine.py`

**Files:**
- Create: `app/vad_pipeline/state_machine.py`
- Create: `tests/unit/test_vad_state_machine.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_vad_state_machine.py`:

```python
import pytest

from app.vad_pipeline.schemas import VADConfig, VADState
from app.vad_pipeline.state_machine import VADStateMachine


@pytest.fixture
def machine():
    return VADStateMachine(VADConfig(
        onset_threshold=0.5,
        offset_threshold=0.35,
        onset_duration_ms=200,
        offset_duration_ms=800,
    ))


def _to_speaking(m: VADStateMachine) -> None:
    m.process(0.9, 0.0)    # QUIET → STARTING  (_onset_start_ms = 0)
    m.process(0.9, 200.0)  # STARTING → SPEAKING (elapsed 200ms >= 200ms)
    assert m.state == VADState.SPEAKING


def _to_stopping(m: VADStateMachine) -> None:
    _to_speaking(m)
    m.process(0.1, 300.0)  # SPEAKING → STOPPING (_offset_start_ms = 300)
    assert m.state == VADState.STOPPING


def test_initial_state_is_quiet(machine):
    assert machine.state == VADState.QUIET


def test_no_event_in_quiet_below_threshold(machine):
    event = machine.process(0.3, 0.0)
    assert event is None
    assert machine.state == VADState.QUIET


def test_quiet_to_starting_on_first_speech_frame(machine):
    event = machine.process(0.9, 0.0)
    assert event is not None
    assert event.prev_state == VADState.QUIET
    assert event.new_state == VADState.STARTING
    assert event.timestamp_ms == 0.0


def test_no_event_during_onset_confirmation_window(machine):
    machine.process(0.9, 0.0)             # → STARTING, _onset_start_ms=0
    event = machine.process(0.9, 100.0)   # 100ms elapsed < 200ms → no transition
    assert event is None
    assert machine.state == VADState.STARTING


def test_starting_to_speaking_after_onset_duration(machine):
    machine.process(0.9, 0.0)             # → STARTING
    event = machine.process(0.9, 200.0)   # exactly 200ms → SPEAKING
    assert event is not None
    assert event.prev_state == VADState.STARTING
    assert event.new_state == VADState.SPEAKING


def test_false_start_returns_to_quiet(machine):
    machine.process(0.9, 0.0)            # → STARTING
    event = machine.process(0.1, 50.0)   # silence before 200ms → false start
    assert event is not None
    assert event.prev_state == VADState.STARTING
    assert event.new_state == VADState.QUIET


def test_speaking_to_stopping_on_first_silent_frame(machine):
    _to_speaking(machine)
    event = machine.process(0.1, 300.0)
    assert event is not None
    assert event.prev_state == VADState.SPEAKING
    assert event.new_state == VADState.STOPPING


def test_no_event_during_offset_confirmation_window(machine):
    _to_stopping(machine)                 # _offset_start_ms = 300
    event = machine.process(0.1, 700.0)  # 400ms elapsed < 800ms → no transition
    assert event is None
    assert machine.state == VADState.STOPPING


def test_stopping_to_quiet_after_offset_duration(machine):
    _to_stopping(machine)                  # _offset_start_ms = 300
    event = machine.process(0.1, 1100.0)  # 800ms elapsed → QUIET
    assert event is not None
    assert event.prev_state == VADState.STOPPING
    assert event.new_state == VADState.QUIET


def test_stopping_to_speaking_on_speech_resumption(machine):
    _to_stopping(machine)
    event = machine.process(0.9, 700.0)  # speech resumes before 800ms
    assert event is not None
    assert event.prev_state == VADState.STOPPING
    assert event.new_state == VADState.SPEAKING


def test_interrupted_false_when_agent_not_speaking(machine):
    event = machine.process(0.9, 0.0)
    assert event.interrupted is False


def test_interrupted_true_when_agent_speaking(machine):
    machine.set_agent_speaking(True)
    event = machine.process(0.9, 0.0)
    assert event is not None
    assert event.interrupted is True


def test_interrupted_false_after_agent_stops_speaking(machine):
    machine.set_agent_speaking(True)
    machine.process(0.9, 0.0)    # → STARTING, interrupted=True
    machine.process(0.1, 50.0)   # false start → QUIET
    machine.set_agent_speaking(False)
    event = machine.process(0.9, 100.0)  # new onset
    assert event.interrupted is False
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
.venv\Scripts\pytest tests/unit/test_vad_state_machine.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.vad_pipeline.state_machine'`

- [ ] **Step 3: Implement `state_machine.py`**

Create `app/vad_pipeline/state_machine.py`:

```python
from app.vad_pipeline.schemas import VADConfig, VADEvent, VADState


class VADStateMachine:
    def __init__(self, config: VADConfig) -> None:
        self._config = config
        self._state = VADState.QUIET
        self._onset_start_ms: float = 0.0
        self._offset_start_ms: float = 0.0
        self._agent_speaking: bool = False

    @property
    def state(self) -> VADState:
        return self._state

    def set_agent_speaking(self, speaking: bool) -> None:
        self._agent_speaking = speaking

    def process(self, probability: float, now_ms: float) -> VADEvent | None:
        prev = self._state

        if self._state == VADState.QUIET:
            if probability >= self._config.onset_threshold:
                self._onset_start_ms = now_ms
                self._state = VADState.STARTING
                return VADEvent(
                    prev_state=prev,
                    new_state=VADState.STARTING,
                    timestamp_ms=now_ms,
                    interrupted=self._agent_speaking,
                )

        elif self._state == VADState.STARTING:
            if probability >= self._config.onset_threshold:
                if now_ms - self._onset_start_ms >= self._config.onset_duration_ms:
                    self._state = VADState.SPEAKING
                    return VADEvent(
                        prev_state=prev,
                        new_state=VADState.SPEAKING,
                        timestamp_ms=now_ms,
                    )
            else:
                self._state = VADState.QUIET
                return VADEvent(
                    prev_state=prev,
                    new_state=VADState.QUIET,
                    timestamp_ms=now_ms,
                )

        elif self._state == VADState.SPEAKING:
            if probability < self._config.offset_threshold:
                self._offset_start_ms = now_ms
                self._state = VADState.STOPPING
                return VADEvent(
                    prev_state=prev,
                    new_state=VADState.STOPPING,
                    timestamp_ms=now_ms,
                )

        elif self._state == VADState.STOPPING:
            if probability >= self._config.onset_threshold:
                self._state = VADState.SPEAKING
                return VADEvent(
                    prev_state=prev,
                    new_state=VADState.SPEAKING,
                    timestamp_ms=now_ms,
                )
            if now_ms - self._offset_start_ms >= self._config.offset_duration_ms:
                self._state = VADState.QUIET
                return VADEvent(
                    prev_state=prev,
                    new_state=VADState.QUIET,
                    timestamp_ms=now_ms,
                )

        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
.venv\Scripts\pytest tests/unit/test_vad_state_machine.py -v
```

Expected: `13 passed`

- [ ] **Step 5: Commit**

```powershell
git add app/vad_pipeline/state_machine.py tests/unit/test_vad_state_machine.py
git commit -m "feat: add VAD state machine with 4-state transitions and interrupt detection"
```

---

### Task 4: Silero Wrapper — `silero_wrapper.py`

**Files:**
- Create: `app/vad_pipeline/silero_wrapper.py`
- Create: `tests/unit/test_vad_silero_wrapper.py`

Note: these tests load the real Silero model. They are marked `@pytest.mark.slow` and may take 10–30 seconds on first run while the model downloads. Subsequent runs are fast (model cached locally).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_vad_silero_wrapper.py`:

```python
import math
import pytest
import torch

from app.vad_pipeline.silero_wrapper import SileroWrapper


@pytest.mark.slow
class TestSileroWrapper:
    def test_invalid_sample_rate_raises(self):
        with pytest.raises(ValueError, match="8000 or 16000"):
            SileroWrapper(target_sample_rate=44100)

    def test_silent_audio_returns_low_probability(self):
        wrapper = SileroWrapper(target_sample_rate=16000)
        silent = bytes(512 * 2)  # 512 int16 zeros
        prob = wrapper.infer(silent, source_sample_rate=16000)
        assert isinstance(prob, float)
        assert 0.0 <= prob < 0.5

    def test_infer_returns_float_in_valid_range(self):
        wrapper = SileroWrapper(target_sample_rate=16000)
        samples = [int(32767 * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(512)]
        frames = bytes(torch.tensor(samples, dtype=torch.int16).numpy().tobytes())
        prob = wrapper.infer(frames, source_sample_rate=16000)
        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0

    def test_8khz_resamples_without_error(self):
        wrapper = SileroWrapper(target_sample_rate=16000)
        silent_8k = bytes(256 * 2)  # 256 int16 zeros at 8kHz
        prob = wrapper.infer(silent_8k, source_sample_rate=8000)
        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0

    def test_short_audio_zero_pads_without_error(self):
        wrapper = SileroWrapper(target_sample_rate=16000)
        short = bytes(100 * 2)  # only 100 samples, below the required 512
        prob = wrapper.infer(short, source_sample_rate=16000)
        assert isinstance(prob, float)

    def test_reset_does_not_raise(self):
        wrapper = SileroWrapper(target_sample_rate=16000)
        wrapper.reset()  # resets LSTM hidden state — must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
.venv\Scripts\pytest tests/unit/test_vad_silero_wrapper.py -v -m slow
```

Expected: `ModuleNotFoundError: No module named 'app.vad_pipeline.silero_wrapper'`

- [ ] **Step 3: Implement `silero_wrapper.py`**

Create `app/vad_pipeline/silero_wrapper.py`:

```python
import torch
import torchaudio.functional as F
from silero_vad import load_silero_vad


class SileroWrapper:
    _FRAME_SIZES: dict[int, int] = {8000: 256, 16000: 512}

    def __init__(self, target_sample_rate: int = 16000) -> None:
        if target_sample_rate not in self._FRAME_SIZES:
            raise ValueError(
                f"sample_rate must be 8000 or 16000, got {target_sample_rate}"
            )
        self._target_rate = target_sample_rate
        self._frame_size = self._FRAME_SIZES[target_sample_rate]
        self._model = load_silero_vad()

    def infer(self, frames: bytes, source_sample_rate: int) -> float:
        audio = torch.frombuffer(bytearray(frames), dtype=torch.int16).float() / 32768.0

        if source_sample_rate != self._target_rate:
            audio = F.resample(audio, source_sample_rate, self._target_rate)

        if len(audio) < self._frame_size:
            audio = torch.nn.functional.pad(audio, (0, self._frame_size - len(audio)))
        else:
            audio = audio[: self._frame_size]

        with torch.no_grad():
            prob = self._model(audio, self._target_rate)

        return float(prob)

    def reset(self) -> None:
        self._model.reset_states()
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
.venv\Scripts\pytest tests/unit/test_vad_silero_wrapper.py -v -m slow
```

Expected: `6 passed` (may take 10–30 s for model load)

- [ ] **Step 5: Commit**

```powershell
git add app/vad_pipeline/silero_wrapper.py tests/unit/test_vad_silero_wrapper.py
git commit -m "feat: add Silero VAD wrapper with 8/16kHz resampling and zero-padding"
```

---

### Task 5: Pipeline — `pipeline.py`

**Files:**
- Create: `app/vad_pipeline/pipeline.py`
- Create: `tests/unit/test_vad_pipeline.py`

Pipeline tests mock `SileroWrapper` at the module level so no real model is loaded. All 6 tests are fast.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_vad_pipeline.py`:

```python
import asyncio
import pytest
from unittest.mock import MagicMock

from app.vad_pipeline.pipeline import VADPipeline
from app.vad_pipeline.schemas import VADConfig, VADState


@pytest.fixture
def fast_config():
    return VADConfig(
        onset_threshold=0.5,
        offset_threshold=0.35,
        onset_duration_ms=0,   # immediate transitions for test speed
        offset_duration_ms=0,
        max_queue_size=5,
    )


@pytest.fixture
def mock_wrapper():
    w = MagicMock()
    w.infer.return_value = 0.0
    return w


@pytest.fixture
def vad(fast_config, mock_wrapper, monkeypatch):
    monkeypatch.setattr(
        "app.vad_pipeline.pipeline.SileroWrapper",
        lambda *_: mock_wrapper,
    )
    return VADPipeline(fast_config), mock_wrapper


async def test_speech_onset_emits_starting_event(vad):
    pipeline, wrapper = vad
    wrapper.infer.return_value = 0.9
    await pipeline.start()
    pipeline.push_audio(bytes(512 * 2), 16000)
    event = await asyncio.wait_for(pipeline.events.get(), timeout=2.0)
    assert event.prev_state == VADState.QUIET
    assert event.new_state == VADState.STARTING
    await pipeline.stop()


async def test_two_speech_frames_emit_starting_then_speaking(vad):
    pipeline, wrapper = vad
    wrapper.infer.return_value = 0.9
    await pipeline.start()
    pipeline.push_audio(bytes(512 * 2), 16000)  # → STARTING
    pipeline.push_audio(bytes(512 * 2), 16000)  # → SPEAKING (onset_duration_ms=0)
    e1 = await asyncio.wait_for(pipeline.events.get(), timeout=2.0)
    e2 = await asyncio.wait_for(pipeline.events.get(), timeout=2.0)
    assert e1.new_state == VADState.STARTING
    assert e2.new_state == VADState.SPEAKING
    await pipeline.stop()


async def test_queue_full_raises(vad):
    pipeline, _ = vad
    # No pipeline.start() — no consumer draining the queue
    for _ in range(5):  # max_queue_size == 5
        pipeline.push_audio(bytes(512 * 2), 16000)
    with pytest.raises(asyncio.QueueFull):
        pipeline.push_audio(bytes(512 * 2), 16000)


async def test_interrupted_flag_when_agent_speaking(vad):
    pipeline, wrapper = vad
    wrapper.infer.return_value = 0.9
    await pipeline.start()
    pipeline.set_agent_speaking(True)
    pipeline.push_audio(bytes(512 * 2), 16000)
    event = await asyncio.wait_for(pipeline.events.get(), timeout=2.0)
    assert event.new_state == VADState.STARTING
    assert event.interrupted is True
    await pipeline.stop()


async def test_stop_after_start_does_not_raise(vad):
    pipeline, _ = vad
    await pipeline.start()
    await pipeline.stop()


async def test_wrapper_reset_called_on_start(vad):
    pipeline, wrapper = vad
    await pipeline.start()
    wrapper.reset.assert_called_once()
    await pipeline.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
.venv\Scripts\pytest tests/unit/test_vad_pipeline.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.vad_pipeline.pipeline'`

- [ ] **Step 3: Implement `pipeline.py`**

Create `app/vad_pipeline/pipeline.py`:

```python
import asyncio
import time

from app.vad_pipeline.schemas import VADConfig, VADEvent
from app.vad_pipeline.silero_wrapper import SileroWrapper
from app.vad_pipeline.state_machine import VADStateMachine


class VADPipeline:
    def __init__(self, config: VADConfig = VADConfig()) -> None:
        self._config = config
        self._wrapper = SileroWrapper(config.sample_rate)
        self._machine = VADStateMachine(config)
        self._audio_q: asyncio.Queue[tuple[bytes, int]] = asyncio.Queue(
            maxsize=config.max_queue_size
        )
        self._events_q: asyncio.Queue[VADEvent] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._start_ms: float = 0.0

    def push_audio(self, frames: bytes, sample_rate: int) -> None:
        self._audio_q.put_nowait((frames, sample_rate))

    @property
    def events(self) -> asyncio.Queue[VADEvent]:
        return self._events_q

    def set_agent_speaking(self, speaking: bool) -> None:
        self._machine.set_agent_speaking(speaking)

    async def start(self) -> None:
        self._wrapper.reset()
        self._start_ms = time.monotonic() * 1000
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _run(self) -> None:
        while True:
            frames, sample_rate = await self._audio_q.get()
            now_ms = time.monotonic() * 1000 - self._start_ms
            prob = self._wrapper.infer(frames, sample_rate)
            event = self._machine.process(prob, now_ms)
            if event is not None:
                await self._events_q.put(event)
```

- [ ] **Step 4: Run the pipeline tests**

```powershell
.venv\Scripts\pytest tests/unit/test_vad_pipeline.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Run the full fast unit suite (no slow tests) to verify no regressions**

```powershell
.venv\Scripts\pytest tests/unit/ -v --ignore=tests/unit/test_vad_silero_wrapper.py
```

Expected: all prior tests still pass plus the new ones. Count should be 119 (prior) + 4 + 13 + 6 = 142 passed.

- [ ] **Step 6: Commit**

```powershell
git add app/vad_pipeline/pipeline.py tests/unit/test_vad_pipeline.py
git commit -m "feat: add VAD pipeline async orchestrator with push_audio/events interface"
```

---

### Task 6: README

**Files:**
- Create: `app/vad_pipeline/README.md`

- [ ] **Step 1: Write README**

Create `app/vad_pipeline/README.md`:

```markdown
# vad_pipeline — Silero VAD Wrapper

Standalone voice activity detection module. Push raw PCM audio frames in; consume `VADEvent` objects from an async queue.

## States

```
QUIET → STARTING → SPEAKING → STOPPING → QUIET
```

| Transition | Condition |
|------------|-----------|
| QUIET → STARTING | First frame above `onset_threshold` (default 0.5) |
| STARTING → SPEAKING | Speech sustained for `onset_duration_ms` (default 200ms) |
| STARTING → QUIET | Silence before onset confirmed (false start) |
| SPEAKING → STOPPING | First frame below `offset_threshold` (default 0.35) |
| STOPPING → QUIET | Silence sustained for `offset_duration_ms` (default 800ms) |
| STOPPING → SPEAKING | Speech resumes before offset confirmed |

## Usage

```python
from app.vad_pipeline.pipeline import VADPipeline
from app.vad_pipeline.schemas import VADConfig

config = VADConfig(sample_rate=16000)
pipeline = VADPipeline(config)

await pipeline.start()

# Push 16-bit PCM frames (8kHz or 16kHz — resampled internally)
pipeline.push_audio(pcm_bytes, sample_rate=16000)

# Consume state-change events
event = await pipeline.events.get()
print(event.new_state, event.interrupted)

# Enable interrupt detection while agent is speaking
pipeline.set_agent_speaking(True)

await pipeline.stop()
```

## Interrupt Detection

When `set_agent_speaking(True)` is active, any QUIET → STARTING transition sets `event.interrupted = True`. The caller is responsible for halting TTS and truncating LLM context.

## File Responsibilities

| File | Responsibility |
|------|----------------|
| `schemas.py` | `VADState`, `VADEvent`, `VADConfig` — shared types, no logic |
| `silero_wrapper.py` | Silero model + resampler → float probability per frame |
| `state_machine.py` | Pure state machine — no torch, no asyncio |
| `pipeline.py` | Async orchestrator — audio queue in, event queue out |

## Running Tests

Fast tests only (no model load, ~1s):
```powershell
.venv\Scripts\pytest tests/unit/test_vad_schemas.py tests/unit/test_vad_state_machine.py tests/unit/test_vad_pipeline.py -v
```

All tests including Silero model tests (~30s first run):
```powershell
.venv\Scripts\pytest tests/unit/ -v
```
```

- [ ] **Step 2: Commit**

```powershell
git add app/vad_pipeline/README.md
git commit -m "docs: add VAD pipeline README with usage and state transition table"
```

---

## Spec Coverage Self-Review

| Spec section | Covered by |
|---|---|
| §3 schemas.py (VADState, VADEvent, VADConfig) | Task 2 |
| §4 silero_wrapper.py (model, resample, zero-pad, reset) | Task 4 |
| §5 state_machine.py (all 6 transitions + false start + interrupt) | Task 3 |
| §6 pipeline.py (push_audio, events, set_agent_speaking, start/stop) | Task 5 |
| §7 interrupt detection (interrupted=True, caller acts on it) | Tasks 3 + 5 |
| §8 dependencies (silero-vad, torchaudio) | Task 1 |
| §9 testing strategy (3 test files, slow marker on Silero tests) | Tasks 2–5 |
| §10 no WebSocket / Retell / STT / LLM code | Verified — none introduced |

**Type consistency:** `VADConfig` / `VADEvent` / `VADState` defined in Task 2 and used consistently across Tasks 3, 4, 5. `SileroWrapper.infer(frames: bytes, source_sample_rate: int) -> float` signature matches definition (Task 4) and mock usage (Task 5). `VADStateMachine.process(probability: float, now_ms: float) -> VADEvent | None` matches definition (Task 3) and pipeline call site (Task 5). `pipeline._wrapper` attribute accessed in Task 5 fixture matches `VADPipeline.__init__` in Task 5 implementation.
