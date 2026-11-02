from __future__ import annotations

import numpy as np
import pytest

from app.audio_features import SAMPLE_RATE as SR
from app.config import Settings
from app.stt import SegmentOut

rng = np.random.default_rng(0)


def voiced(dur, f0_lo=110, f0_hi=150, amp=0.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f0 = f0_lo + (f0_hi - f0_lo) * (0.5 + 0.5 * np.sin(2 * np.pi * 1.3 * t))
    ph = 2 * np.pi * np.cumsum(f0) / SR
    sig = sum(np.sin(k * ph) / k for k in range(1, 8))
    env = 0.6 + 0.4 * np.sin(2 * np.pi * 3.5 * t) ** 2
    return (amp * sig * env / 2).astype(np.float32)


def silence(d, noise=0.003):
    return rng.normal(0, noise, int(d * SR)).astype(np.float32)


def speech_clip(parts=((3, "v"), (0.6, "s"), (3, "v"), (1.5, "s"), (2, "v"))):
    segs = [silence(1)]
    for d, k in parts:
        segs.append(voiced(d) if k == "v" else silence(d))
    segs.append(silence(1))
    y = np.concatenate(segs)
    return y + rng.normal(0, 0.003, len(y)).astype(np.float32)


def to_pcm16(y: np.ndarray) -> bytes:
    return (np.clip(y, -1, 1) * 32767).astype("<i2").tobytes()


class FakeEngine:
    name = "fake"
    ready = True

    def __init__(
        self, text="I led a team of five engineers and reduced latency by 40 percent, um, which saved two million dollars."
    ):
        self.text, self.calls = text, 0

    def load(self):
        pass

    def transcribe(self, audio, prompt):
        self.calls += 1
        return SegmentOut(self.text if self.calls == 1 else "", 0.9, len(audio) / SR)


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path, app_env="development", llm_api_key=None, rate_limit_per_min=100, min_duration=5)
