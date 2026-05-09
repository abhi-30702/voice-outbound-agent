import asyncio
import pytest
from unittest.mock import MagicMock, patch

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


async def test_machine_reset_called_on_start(vad):
    pipeline, wrapper = vad
    with patch.object(pipeline._machine, "reset") as mock_reset:
        await pipeline.start()
        mock_reset.assert_called_once()
        await pipeline.stop()


async def test_double_start_raises(vad):
    pipeline, _ = vad
    await pipeline.start()
    with pytest.raises(RuntimeError, match="already running"):
        await pipeline.start()
    await pipeline.stop()
