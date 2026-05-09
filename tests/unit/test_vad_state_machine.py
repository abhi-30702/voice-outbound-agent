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


def test_reset_returns_machine_to_quiet(machine):
    _to_speaking(machine)
    machine.reset()
    assert machine.state == VADState.QUIET


def test_reset_clears_agent_speaking_flag(machine):
    machine.set_agent_speaking(True)
    machine.reset()
    event = machine.process(0.9, 0.0)
    assert event.interrupted is False


def test_no_event_in_stopping_hysteresis_zone(machine):
    _to_stopping(machine)          # _offset_start_ms = 300
    event = machine.process(0.4, 500.0)  # between 0.35 and 0.5, timer not expired
    assert event is None
    assert machine.state == VADState.STOPPING
