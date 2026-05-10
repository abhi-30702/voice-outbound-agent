import math
import pytest
import torch

try:
    import numpy
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from app.vad_pipeline.silero_wrapper import SileroWrapper


def test_invalid_sample_rate_raises():
    with pytest.raises(ValueError, match="8000 or 16000"):
        SileroWrapper(target_sample_rate=44100)


@pytest.mark.slow
class TestSileroWrapper:
    def test_silent_audio_returns_low_probability(self):
        wrapper = SileroWrapper(target_sample_rate=16000)
        silent = bytes(512 * 2)  # 512 int16 zeros
        prob = wrapper.infer(silent, source_sample_rate=16000)
        assert isinstance(prob, float)
        assert 0.0 <= prob < 0.5

    @pytest.mark.skipif(not HAS_NUMPY, reason="NumPy not installed")
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
