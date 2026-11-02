import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import numpy as np

from app.audio_features import SAMPLE_RATE as SR
from app.llm import LLMClient
from app.stt import SegmentOut, StreamingTranscriber

from .conftest import FakeEngine, silence, voiced

OK = {
    "relevance": {"score": 7, "reason": "x"},
    "structure": {"score": 6, "reason": "x"},
    "specificity": {"score": 8, "reason": "x"},
    "depth": {"score": 5, "reason": "x"},
    "clarity": {"score": 7, "reason": "x"},
    "strengths": ["s"],
    "improvements": ["i"],
    "summary": "sum",
    "transcript_quality": "good",
}


def client(handler, **kw):
    return LLMClient("k", "https://llm.test/v1", "m", transport=httpx.MockTransport(handler), **kw)


async def test_llm_parses_fenced_json_and_caches():
    calls = []

    def h(req):
        calls.append(1)
        body = json.loads(req.content)
        assert body["response_format"] == {"type": "json_object"} and "<transcript>" in body["messages"][1]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "```json\n" + json.dumps(OK) + "\n```"}}]})

    c = client(h)
    a = await c.evaluate("t", "some words here", 30, 0.9)
    b = await c.evaluate("t", "some words here", 30, 0.9)
    assert a.weighted_score() == 67 and a is b and len(calls) == 1


async def test_llm_retries_then_succeeds(monkeypatch):
    _real = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda *_: _real(0))
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        if n["i"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(OK)}}]})

    assert await client(h).evaluate("t", "words words words", 10, None) is not None and n["i"] == 3


async def test_llm_failure_degrades_and_circuit_opens(monkeypatch):
    _real = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda *_: _real(0))
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        return httpx.Response(401)

    c = client(h)
    for i in range(3):
        assert await c.evaluate("t", f"words words {i}", 10, None) is None
    before = n["i"]
    assert await c.evaluate("t", "fresh words here", 10, None) is None
    assert n["i"] == before  # circuit open: no network call


async def test_llm_rejects_invalid_schema():
    def h(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"relevance": 3}'}}]})

    assert await client(h, max_attempts=1).evaluate("t", "words words words", 10, None) is None


async def test_rolling_transcriber_cuts_at_pause_and_orders_text():
    class Eng(FakeEngine):
        def transcribe(self, audio, prompt):
            self.calls += 1
            return SegmentOut(f"part{self.calls}", 0.8, len(audio) / SR)

    eng, partials = Eng(), []
    tr = StreamingTranscriber(eng, ThreadPoolExecutor(1), None, chunk_seconds=4, on_partial=partials.append)
    y = np.concatenate([voiced(3.5), silence(0.5), voiced(3.5), silence(0.5), voiced(2)])
    for i in range(0, len(y), SR // 4):
        tr.feed(y[i : i + SR // 4])
        await asyncio.sleep(0)
    assert tr._cut > 0 and len(tr._jobs) >= 1  # dispatched while still "recording"
    res = await tr.finalize()
    assert res.text.startswith("part1") and "part2" in res.text and abs(res.confidence - 0.8) < 1e-6
    assert eng.calls >= 2 and partials


async def test_silence_is_never_sent_to_whisper():
    eng = FakeEngine()
    tr = StreamingTranscriber(eng, ThreadPoolExecutor(1), None, chunk_seconds=2)
    tr.feed(silence(6))
    res = await tr.finalize()
    assert eng.calls == 0 and res.text == ""
