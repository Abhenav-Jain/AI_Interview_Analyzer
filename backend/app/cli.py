"""Analyse an audio file offline:  python -m app.cli answer.wav --topic "Tell me about yourself"
Uses exactly the same pipeline as the live app (no face data)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .audio_features import SAMPLE_RATE
from .config import load_settings
from .llm import LLMClient
from .logging_setup import setup_logging
from .main import build_engine
from .pipeline import SessionRun


def load_audio(path: str) -> np.ndarray:
    import soundfile as sf

    y, sr = sf.read(path, dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    if sr != SAMPLE_RATE:  # linear resample; fine for speech analysis
        n = int(len(y) * SAMPLE_RATE / sr)
        y = np.interp(np.linspace(0, len(y) - 1, n), np.arange(len(y)), y).astype(np.float32)
    return y


async def _run(path: str, topic: str) -> dict:
    s = load_settings()
    setup_logging("WARNING")
    engine = build_engine(s)
    engine.load()
    llm = LLMClient(s.llm_api_key, s.llm_base_url, s.llm_model, s.llm_timeout)
    y = load_audio(path)
    run = SessionRun(
        session_id="cli",
        topic=topic,
        duration=int(len(y) / SAMPLE_RATE) + 1,
        engine=engine,
        executor=ThreadPoolExecutor(1),
        llm=llm,
        settings=s,
    )
    step = SAMPLE_RATE // 4
    for i in range(0, len(y), step):  # feed like a live stream
        run.transcriber.feed(y[i : i + step])
        await asyncio.sleep(0)
    res = await run.finish()
    await llm.aclose()
    return res.model_dump(mode="json")


def main() -> None:
    p = argparse.ArgumentParser(description="Analyse a recorded interview answer.")
    p.add_argument("audio")
    p.add_argument("--topic", default="General interview")
    a = p.parse_args()
    json.dump(asyncio.run(_run(a.audio, a.topic)), sys.stdout, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
