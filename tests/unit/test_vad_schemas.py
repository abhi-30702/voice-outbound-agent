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
