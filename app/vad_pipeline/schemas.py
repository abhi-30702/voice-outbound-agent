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
