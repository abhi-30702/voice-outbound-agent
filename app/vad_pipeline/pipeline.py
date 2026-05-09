import asyncio
import time

from app.vad_pipeline.schemas import VADConfig, VADEvent
from app.vad_pipeline.silero_wrapper import SileroWrapper
from app.vad_pipeline.state_machine import VADStateMachine


class VADPipeline:
    def __init__(self, config: VADConfig | None = None) -> None:
        config = config if config is not None else VADConfig()
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
        if self._task is not None:
            raise RuntimeError("VADPipeline.start() called while already running")
        self._wrapper.reset()
        self._machine.reset()
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
