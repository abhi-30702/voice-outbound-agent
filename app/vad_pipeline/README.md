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
