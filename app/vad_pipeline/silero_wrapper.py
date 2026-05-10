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
