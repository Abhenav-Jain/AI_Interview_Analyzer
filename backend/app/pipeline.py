"""One interview attempt, end to end. Transport-agnostic: the websocket handler
and the CLI both drive this class."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import Executor

from .audio_features import SAMPLE_RATE, extract_audio_features, pcm16_to_float
from .config import Settings
from .face import FaceSample, aggregate_face, compute_baseline
from .llm import LLMClient
from .schemas import Result
from .scoring import build_result
from .stt import StreamingTranscriber, STTEngine, build_prompt
from .text_metrics import analyze_text

log = logging.getLogger("pipeline")

Send = Callable[[dict], Awaitable[None]]


class LimitExceeded(Exception):
    pass


async def _noop(_: dict) -> None:
    return None


class SessionRun:
    def __init__(
        self,
        *,
        session_id: str,
        topic: str,
        duration: int,
        engine: STTEngine,
        executor: Executor,
        llm: LLMClient,
        settings: Settings,
        send: Send = _noop,
    ):
        self.session_id, self.topic, self.duration = session_id, topic, duration
        self.settings, self.llm, self.send = settings, llm, send
        self.transcriber = StreamingTranscriber(
            engine, executor, build_prompt(topic), settings.stt_chunk_seconds, on_partial=self._on_partial
        )
        self.calibration: list[FaceSample] = []
        self.face: list[FaceSample] = []
        self.max_samples = int((duration + settings.grace_seconds) * SAMPLE_RATE)
        self.max_face = int((duration + settings.grace_seconds) * 30)
        self._tasks: set[asyncio.Task] = set()

    # ------------------------------------------------------------------ inputs
    def add_audio(self, data: bytes) -> None:
        pcm = pcm16_to_float(data)
        if self.transcriber.samples + len(pcm) > self.max_samples:
            raise LimitExceeded("Audio exceeds the session duration limit.")
        self.transcriber.feed(pcm)

    def _parse(self, items: list, into: list[FaceSample], cap: int) -> None:
        for it in items:
            if len(into) >= cap:
                break
            try:
                into.append(FaceSample.model_validate(it))
            except Exception:  # noqa: BLE001 - drop malformed samples, keep the session alive
                continue

    def add_face(self, items: list) -> None:
        self._parse(items[:200], self.face, self.max_face)

    def add_calibration(self, items: list) -> None:
        self._parse(items[:200], self.calibration, 300)

    # ----------------------------------------------------------------- partial
    def _on_partial(self, text: str) -> None:
        t = asyncio.get_running_loop().create_task(self.send({"type": "partial", "text": text}))
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    # ------------------------------------------------------------------ finish
    async def finish(self) -> Result:
        t_start = time.perf_counter()
        loop = asyncio.get_running_loop()
        await self.send({"type": "stage", "stage": "transcribing", "progress": 40})

        audio = self.transcriber.audio()
        duration_s = len(audio) / SAMPLE_RATE
        feat_fut = loop.run_in_executor(None, extract_audio_features, audio)
        tr, feat = await asyncio.gather(self.transcriber.finalize(), feat_fut)
        t_stt = time.perf_counter()

        text = analyze_text(tr.text)
        face = aggregate_face(self.face, compute_baseline(self.calibration))

        await self.send({"type": "stage", "stage": "analyzing", "progress": 70})
        ev = None
        if text.word_count >= 3 and feat.has_speech:
            ev = await self.llm.evaluate(self.topic, tr.text, duration_s, tr.confidence)
        t_llm = time.perf_counter()

        await self.send({"type": "stage", "stage": "scoring", "progress": 92})
        result = build_result(
            weights={
                "audio": self.settings.w_audio,
                "expression": self.settings.w_expression,
                "content": self.settings.w_content,
            },
            duration_s=duration_s,
            transcript=tr.text,
            stt_confidence=tr.confidence,
            audio_feat=feat,
            face=face,
            llm=ev,
            text=text,
            face_calibrated=bool(self.calibration) and len(self.calibration) >= 5,
            timings_ms={
                "transcribe_wait": int((t_stt - t_start) * 1000),
                "stt_compute": tr.stt_ms,
                "llm": int((t_llm - t_stt) * 1000),
                "total": int((time.perf_counter() - t_start) * 1000),
            },
        )
        if tr.failed_jobs:
            result.reliability.notes.append("Part of your audio could not be transcribed; the transcript may be incomplete.")
            result.reliability.level = "low"
        log.info("session finished", extra={"session_id": self.session_id, "ms": result.timings_ms["total"]})
        return result
