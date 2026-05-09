# VAD Pipeline Design

**Date:** 2026-05-09
**Module:** 5 (vad-pipeline)
**Status:** Approved

---

## 1. Goal

Build a standalone, fully testable Silero VAD wrapper with a 4-state machine
(QUIET / STARTING / SPEAKING / STOPPING) that any caller can use by pushing raw
audio frames in and consuming `VADEvent` objects from an async queue.

This module is a pure utility — it has no live connection to Retell AI or Telnyx.
Integration with a real audio stream happens in a later module.

---

## 2. Architecture

**Approach: Layered (3 focused units + shared types)**

```
app/vad_pipeline/
├── __init__.py
├── schemas.py          # VADState, VADEvent, VADConfig — no logic, no side imports
├── silero_wrapper.py   # Silero model + resampler → float probability per frame
├── state_machine.py    # Pure state machine: float prob + timestamp → VADEvent | None
└── pipeline.py         # Orchestrator: audio queue → wrapper → machine → event queue

tests/unit/
├── test_vad_state_machine.py    # pure logic, no torch
├── test_vad_silero_wrapper.py   # real model, slow, minimal assertions
└── test_vad_pipeline.py         # wrapper mocked, event queue asserted end-to-end
```

Each layer has one responsibility and can be understood, tested, and replaced
without touching the others.

---

## 3. Shared Types — `schemas.py`

```python
from enum import Enum
from dataclasses import dataclass, field

class VADState(str, Enum):
    QUIET    = "quiet"
    STARTING = "starting"
    SPEAKING = "speaking"
    STOPPING = "stopping"

@dataclass(frozen=True)
class VADEvent:
    prev_state:   VADState
    new_state:    VADState
    timestamp_ms: float         # monotonic ms since pipeline.start() was called
    interrupted:  bool = False  # True when agent was speaking and user broke in

@dataclass
class VADConfig:
    sample_rate:        int   = 16000  # 8000 or 16000; pipeline resamples internally
    onset_threshold:    float = 0.5    # prob above which speech is detected
    offset_threshold:   float = 0.35   # prob below which silence is confirmed
    onset_duration_ms:  int   = 200    # sustained speech required: STARTING → SPEAKING
    offset_duration_ms: int   = 800    # sustained silence required: STOPPING → QUIET
    max_queue_size:     int   = 100    # audio frame buffer; QueueFull raises on overflow
```

`schemas.py` imports nothing from `app/` — it is the dependency base for all
other modules in this package.

---

## 4. Silero Wrapper — `silero_wrapper.py`

**Responsibility:** Load the Silero VAD PyTorch model once, accept raw PCM bytes
at any supported sample rate, resample internally if needed, and return a speech
probability float in [0.0, 1.0].

```python
class SileroWrapper:
    def __init__(self, target_sample_rate: int = 16000) -> None:
        # torch.hub.load("snakers4/silero-vad", "silero_vad", force_reload=False)
        # torchaudio.transforms.Resample if source_rate != target_sample_rate

    def infer(self, frames: bytes, source_sample_rate: int) -> float:
        # 1. Convert bytes → torch.Tensor (float32, normalised to [-1, 1])
        # 2. Resample if source_sample_rate != self.target_sample_rate
        # 3. Run model forward pass
        # 4. Return float probability
```

**Supported sample rates:** 8000 Hz and 16000 Hz (Silero's native rates).
Resampling uses `torchaudio.transforms.Resample`; the transform is cached on
`__init__` per source/target pair.

**Frame size:** Silero expects exactly 512 samples at 16 kHz (32 ms) or
256 samples at 8 kHz (32 ms). `infer()` zero-pads short chunks to the required
frame size; callers should aim for ~30 ms chunks to minimise padding.

---

## 5. State Machine — `state_machine.py`

**Responsibility:** Accept `(probability: float, now_ms: float)` pairs and emit
`VADEvent | None` based on the transition rules below. No torch, no asyncio, no
I/O — pure deterministic logic.

### State Transition Table

| From      | Condition                                           | To        | Side effect                        |
|-----------|-----------------------------------------------------|-----------|------------------------------------|
| QUIET     | `prob >= onset_threshold` (first frame above)       | STARTING  | record `_onset_start_ms = now_ms`  |
| STARTING  | sustained above threshold for `onset_duration_ms`   | SPEAKING  | emit SPEAKING event                |
| STARTING  | `prob < onset_threshold` before `onset_duration_ms` | QUIET     | false start — emit QUIET event     |
| SPEAKING  | `prob < offset_threshold` (first frame below)       | STOPPING  | record `_offset_start_ms = now_ms` |
| STOPPING  | sustained below threshold for `offset_duration_ms`  | QUIET     | emit QUIET event (→ signal LLM)    |
| STOPPING  | `prob >= onset_threshold` before `offset_duration_ms` | SPEAKING | speech resumed — emit SPEAKING     |

```python
class VADStateMachine:
    def __init__(self, config: VADConfig) -> None: ...

    def process(self, probability: float, now_ms: float) -> VADEvent | None:
        # Returns a VADEvent on state change, None otherwise.
        # Sets interrupted=True on any QUIET/STOPPING → STARTING transition
        # when self._agent_speaking is True.

    def set_agent_speaking(self, speaking: bool) -> None:
        self._agent_speaking = speaking

    @property
    def state(self) -> VADState: ...
```

---

## 6. Pipeline — `pipeline.py`

**Responsibility:** Own the async `push_audio` / `events` interface. Runs a
background asyncio task that drains the audio input queue, calls `SileroWrapper`,
feeds `VADStateMachine`, and puts resulting `VADEvent` objects onto the output
queue.

```python
class VADPipeline:
    def __init__(self, config: VADConfig = VADConfig()) -> None:
        self._wrapper  = SileroWrapper(config.sample_rate)
        self._machine  = VADStateMachine(config)
        self._audio_q  = asyncio.Queue(maxsize=config.max_queue_size)
        self._events_q: asyncio.Queue[VADEvent] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._start_ms: float = 0.0

    def push_audio(self, frames: bytes, sample_rate: int) -> None:
        # Non-blocking. Raises asyncio.QueueFull if buffer is full.
        self._audio_q.put_nowait((frames, sample_rate))

    @property
    def events(self) -> asyncio.Queue[VADEvent]:
        return self._events_q

    def set_agent_speaking(self, speaking: bool) -> None:
        self._machine.set_agent_speaking(speaking)

    async def start(self) -> None:
        self._start_ms = time.monotonic() * 1000
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _run(self) -> None:
        while True:
            frames, sample_rate = await self._audio_q.get()
            now_ms = time.monotonic() * 1000 - self._start_ms
            prob   = self._wrapper.infer(frames, sample_rate)
            event  = self._machine.process(prob, now_ms)
            if event is not None:
                await self._events_q.put(event)
```

---

## 7. Interrupt Detection

When `pipeline.set_agent_speaking(True)` is active, any QUIET → STARTING or
STOPPING → STARTING transition emits a `VADEvent` with `interrupted=True`.

The pipeline's responsibility stops there. The caller (a future streaming module)
reads `event.interrupted` and decides how to halt the TTS stream and truncate
the LLM context. This keeps the VAD pipeline dependency-free.

---

## 8. Dependencies

Add to `requirements.txt`:

```
silero-vad>=4.0.0
torchaudio>=2.0.0
```

`torch` is a transitive dependency of `silero-vad`. No version pin needed —
`silero-vad` specifies its own torch floor.

---

## 9. Testing Strategy

### `test_vad_state_machine.py` (no torch — fast)

Feed deterministic probability sequences and verify:
- QUIET → STARTING on first frame above onset threshold
- STARTING → QUIET on false start (silence before 200ms)
- STARTING → SPEAKING after 200ms sustained
- SPEAKING → STOPPING on first silent frame
- STOPPING → SPEAKING on speech resumption before 800ms
- STOPPING → QUIET after 800ms silence
- `interrupted=True` set when `set_agent_speaking(True)` and speech detected

### `test_vad_silero_wrapper.py` (torch required — slow, minimal)

- Load model (real `torch.hub.load`)
- Feed 512 samples of zeros at 16kHz → `prob < 0.1`
- Feed 512 samples of a 440 Hz sine at 16kHz → `prob` is a valid float in [0, 1]
- Feed 256 samples at 8kHz → assert no exception (resampling path)

### `test_vad_pipeline.py` (wrapper mocked — fast)

- Patch `SileroWrapper.infer` with a controlled sequence of floats
- `await pipeline.start()`
- Push audio frames via `push_audio()`
- `await events.get()` and assert `VADEvent` fields
- Assert `QueueFull` raised when `max_queue_size` exceeded
- Assert `interrupted=True` when `set_agent_speaking(True)` active

---

## 10. What This Module Does NOT Do

- No WebSocket or network I/O
- No Retell AI integration
- No STT — it signals readiness to stream, but does not stream
- No LLM context truncation — emits `interrupted=True`; caller acts on it
- No persistence or logging
