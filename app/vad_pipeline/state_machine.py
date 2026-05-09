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
