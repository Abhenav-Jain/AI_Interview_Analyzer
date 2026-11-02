"""Speech-to-text.

v1: Vosk (small US model, even though the README promised en-in), run only
*after* the recording finished, silently returning "" if the model failed to
load. One saved report shows the result: "derby when my name is up you know
extent..." for an English answer.

v2: faster-whisper (CTranslate2, int8 on CPU) which is far more accurate on
Indian-accented English, plus a **rolling transcriber**: while the candidate is
still talking, finished stretches (cut at a natural pause) are transcribed in
the background, so only the last few seconds remain when they press Stop.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .audio_features import SAMPLE_RATE, has_speech_energy

log = logging.getLogger("stt")

_HALLUCINATIONS = {"thank you", "thanks for watching", "thank you for watching", "you", "bye", "okay", "."}


@dataclass
class SegmentOut:
    text: str
    confidence: float | None  # 0-1, mean exp(avg_logprob) weighted by duration
    audio_s: float


@dataclass
class TranscriptResult:
    text: str
    confidence: float | None
    stt_ms: int
    failed_jobs: int = 0


class STTEngine(Protocol):
    name: str
    ready: bool

    def load(self) -> None: ...
    def transcribe(self, audio: np.ndarray, prompt: str | None) -> SegmentOut: ...


class NullEngine:
    """STT_BACKEND=none: lets the rest of the app run (e.g. UI development, CI)."""

    name = "none"
    ready = True

    def load(self) -> None:
        pass

    def transcribe(self, audio: np.ndarray, prompt: str | None) -> SegmentOut:
        return SegmentOut("", None, len(audio) / SAMPLE_RATE)


class FasterWhisperEngine:
    def __init__(self, model: str, device: str, compute_type: str, beam_size: int, cpu_threads: int, download_root: str | None):
        self.name = f"faster-whisper:{model}"
        self.ready = False
        self._cfg = dict(
            model=model, device=device, compute_type=compute_type, cpu_threads=cpu_threads, download_root=download_root
        )
        self._beam = beam_size
        self._model = None

    def load(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel  # imported lazily: heavy

        t0 = time.time()
        c = self._cfg
        self._model = WhisperModel(
            c["model"],
            device=c["device"],
            compute_type=c["compute_type"],
            cpu_threads=c["cpu_threads"],
            download_root=c["download_root"],
        )
        self.ready = True
        log.info("Whisper model %s loaded in %.1fs", c["model"], time.time() - t0)

    def transcribe(self, audio: np.ndarray, prompt: str | None) -> SegmentOut:
        if self._model is None:
            self.load()
        segments, _info = self._model.transcribe(  # type: ignore[union-attr]
            audio.astype(np.float32),
            language="en",
            beam_size=self._beam,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 200},
            condition_on_previous_text=False,
            initial_prompt=prompt,
            temperature=(0.0, 0.2, 0.4),
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4,
        )
        texts, wsum, csum = [], 0.0, 0.0
        for s in segments:
            if s.no_speech_prob > 0.6 and s.avg_logprob < -1.0:
                continue  # classic Whisper hallucination on noise
            t = s.text.strip()
            if not t:
                continue
            dur = max(s.end - s.start, 0.1)
            texts.append(t)
            wsum += dur
            csum += dur * math.exp(min(0.0, s.avg_logprob))
        text = " ".join(texts).strip()
        audio_s = len(audio) / SAMPLE_RATE
        if text.lower().strip(" .!,") in _HALLUCINATIONS and audio_s < 2.5:
            return SegmentOut("", None, audio_s)
        return SegmentOut(text, (csum / wsum) if wsum else None, audio_s)


def build_prompt(topic: str) -> str:
    # Priming Whisper with disfluencies makes it keep "um/uh/you know" instead of
    # silently cleaning them up, which the fluency score depends on.
    return f"Interview answer about: {topic[:120]}. Umm, uh, so, you know, like, I mean, basically, actually."


def _normalise(seg: np.ndarray) -> np.ndarray:
    """Bring quiet laptop-mic recordings up to a level Whisper handles well (max +20 dB)."""
    peak = float(np.max(np.abs(seg))) if len(seg) else 0.0
    if 0 < peak < 0.5:
        return (seg * min(0.8 / peak, 10.0)).astype(np.float32)
    return seg


class StreamingTranscriber:
    """Feed 16 kHz mono float32 chunks as they arrive; call finalize() at the end."""

    def __init__(
        self,
        engine: STTEngine,
        executor: Executor,
        prompt: str | None,
        chunk_seconds: float = 8.0,
        max_chunk_seconds: float = 18.0,
        on_partial: Callable[[str], None] | None = None,
    ):
        self.engine, self.executor, self.prompt = engine, executor, prompt
        self.chunk = int(chunk_seconds * SAMPLE_RATE)
        self.max_chunk = int(max_chunk_seconds * SAMPLE_RATE)
        self.on_partial = on_partial
        self._parts: list[np.ndarray] = []
        self._n = 0
        self._cut = 0
        self._full: np.ndarray | None = None
        self._jobs: list[asyncio.Future] = []
        self._last_check = 0

    # ------------------------------------------------------------------ audio
    @property
    def samples(self) -> int:
        return self._n

    def audio(self) -> np.ndarray:
        if self._full is None or len(self._full) != self._n:
            self._full = np.concatenate(self._parts) if self._parts else np.zeros(0, np.float32)
            self._parts = [self._full]
        return self._full

    def feed(self, pcm: np.ndarray) -> None:
        if len(pcm) == 0:
            return
        self._parts.append(pcm)
        self._n += len(pcm)
        self._maybe_dispatch()

    # --------------------------------------------------------------- dispatch
    def _quietest_point(self, tail_s: float = 2.5) -> tuple[int, float]:
        """Sample index (absolute) of the quietest 100 ms window in the last tail_s, and its level in dB."""
        y = self.audio()
        start = max(self._cut + SAMPLE_RATE * 2, self._n - int(tail_s * SAMPLE_RATE))
        win = SAMPLE_RATE // 10
        seg = y[start : self._n]
        k = len(seg) // win
        if k < 2:
            return self._n, 0.0
        rms = np.sqrt(np.mean(seg[: k * win].reshape(k, win).astype(np.float64) ** 2, axis=1))
        i = int(np.argmin(rms))
        return start + i * win + win // 2, 20 * math.log10(rms[i] + 1e-10)

    def _maybe_dispatch(self) -> None:
        pending = self._n - self._cut
        if pending < self.chunk or self._n - self._last_check < SAMPLE_RATE // 2:
            return
        self._last_check = self._n
        point, level_db = self._quietest_point()
        if level_db > -42 and pending < self.max_chunk:
            return  # still mid-speech; wait for a pause (but never wait past max_chunk)
        self._dispatch(self._cut, point)
        self._cut = point

    def _dispatch(self, a: int, b: int) -> None:
        seg = self.audio()[a:b].copy()
        if len(seg) < SAMPLE_RATE * 0.4 or not has_speech_energy(seg):
            return  # nothing but silence: do not feed Whisper (it hallucinates)
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(self.executor, self._run, seg)
        fut.add_done_callback(self._on_job_done)
        self._jobs.append(fut)

    def _run(self, seg: np.ndarray) -> tuple[SegmentOut, int]:
        t0 = time.perf_counter()
        out = self.engine.transcribe(_normalise(seg), self.prompt)
        return out, int((time.perf_counter() - t0) * 1000)

    def _on_job_done(self, _fut: asyncio.Future) -> None:
        if not self.on_partial:
            return
        text = []
        for j in self._jobs:  # ordered; stop at first unfinished job
            if not j.done():
                break
            if j.exception() is None:
                text.append(j.result()[0].text)
        joined = " ".join(t for t in text if t).strip()
        if joined:
            try:
                self.on_partial(joined)
            except Exception:  # noqa: BLE001 - never let UI callbacks break STT
                log.exception("on_partial callback failed")

    # --------------------------------------------------------------- finalize
    async def finalize(self) -> TranscriptResult:
        if self._n - self._cut > 0:
            self._dispatch(self._cut, self._n)
            self._cut = self._n
        results = await asyncio.gather(*self._jobs, return_exceptions=True)
        texts, failed, ms, wsum, csum = [], 0, 0, 0.0, 0.0
        for r in results:
            if isinstance(r, BaseException):
                failed += 1
                log.error("STT job failed: %r", r)
                continue
            out, took = r
            ms += took
            if out.text:
                texts.append(out.text)
                if out.confidence is not None:
                    wsum += out.audio_s
                    csum += out.audio_s * out.confidence
        return TranscriptResult(" ".join(texts).strip(), (csum / wsum) if wsum else None, ms, failed)
