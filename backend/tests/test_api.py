import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

from .conftest import FakeEngine, speech_clip, to_pcm16


@pytest.fixture
def client(settings):
    app = create_app(settings, engine=FakeEngine())
    with TestClient(app) as c:
        yield c


def new(client, **kw):
    r = client.post("/api/sessions", json={"topic": "Tell me about yourself", "duration": kw.get("duration", 20)})
    assert r.status_code == 201, r.text
    return r.json()


def test_health_ready_config(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/ready").json()["ready"] is True
    cfg = client.get("/api/config").json()
    assert cfg["llm_enabled"] is False and cfg["max_duration"] >= cfg["min_duration"]


def test_validation_and_auth(client):
    assert client.post("/api/sessions", json={"topic": "", "duration": 20}).status_code == 422
    assert client.post("/api/sessions", json={"topic": "x", "duration": 9999}).status_code == 422
    s = new(client)
    assert client.get(f"/api/sessions/{s['session_id']}").status_code == 404  # no token
    assert client.get(f"/api/sessions/{s['session_id']}", headers={"X-Session-Token": "bad"}).status_code == 404
    ok = client.get(f"/api/sessions/{s['session_id']}", headers={"X-Session-Token": s["token"]})
    assert ok.status_code == 200 and ok.json()["status"] == "created"


def test_api_key_and_rate_limit(settings):
    from dataclasses import replace

    app = create_app(replace(settings, api_key="secret", rate_limit_per_min=2), engine=FakeEngine())
    with TestClient(app) as c:
        body = {"topic": "x", "duration": 20}
        assert c.post("/api/sessions", json=body).status_code == 401
        h = {"X-API-Key": "secret"}
        assert c.post("/api/sessions", json=body, headers=h).status_code == 201
        assert c.post("/api/sessions", json=body, headers=h).status_code == 201
        assert c.post("/api/sessions", json=body, headers=h).status_code == 429


def test_full_websocket_flow(client):
    s = new(client)
    y = speech_clip()
    pcm = to_pcm16(y)
    face = [{"t": i * 0.1, "v": 1, "sm": 0.3, "bl": 0.0, "yw": 1, "pt": 1, "gx": 0, "gy": 0} for i in range(150)]
    cal = [{"t": i * 0.1, "v": 1, "yw": 1, "pt": 1} for i in range(30)]
    msgs = []
    with client.websocket_connect(f"/api/ws/sessions/{s['session_id']}?token={s['token']}") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_text(json.dumps({"type": "calibration", "samples": cal}))
        ws.send_text(json.dumps({"type": "start"}))
        step = 8000
        for i in range(0, len(pcm), step):
            ws.send_bytes(pcm[i : i + step])
        ws.send_text(json.dumps({"type": "face", "samples": face[:100]}))
        ws.send_text(json.dumps({"type": "face", "samples": face[100:] + [{"t": "NaN-bad"}, {"t": 1e9}]}))  # junk is dropped
        ws.send_text(json.dumps({"type": "end"}))
        while True:
            m = ws.receive_json()
            msgs.append(m)
            if m["type"] in ("result", "error"):
                break
    assert msgs[-1]["type"] == "result", msgs[-1]
    r = msgs[-1]["data"]
    assert r["status"] == "ok" and 0 <= r["overall"] <= 100
    assert r["expression"]["available"] and r["audio"]["available"] and r["content"]["available"]
    assert r["content"]["llm_used"] is False and r["transcript"].startswith("I led a team")
    assert any(f["word"] == "um" for f in r["fillers"])
    assert {m["type"] for m in msgs} >= {"stage", "result"}

    # persisted + retrievable over REST, then deletable
    got = client.get(f"/api/sessions/{s['session_id']}", headers={"X-Session-Token": s["token"]}).json()
    assert got["status"] == "done" and got["result"]["overall"] == r["overall"]
    assert client.delete(f"/api/sessions/{s['session_id']}", headers={"X-Session-Token": s["token"]}).status_code == 204
    assert client.get(f"/api/sessions/{s['session_id']}", headers={"X-Session-Token": s["token"]}).status_code == 404


def test_ws_rejects_bad_token_and_reuse(client):
    s = new(client)
    with client.websocket_connect(f"/api/ws/sessions/{s['session_id']}?token=nope") as ws:
        assert ws.receive_json()["type"] == "error"
    with client.websocket_connect(f"/api/ws/sessions/{s['session_id']}?token={s['token']}") as ws:
        ws.receive_json()
        ws.send_text(json.dumps({"type": "start"}))
        ws.send_text(json.dumps({"type": "end"}))
        while ws.receive_json()["type"] not in ("result", "error"):
            pass
    with client.websocket_connect(f"/api/ws/sessions/{s['session_id']}?token={s['token']}") as ws:
        assert "already been used" in ws.receive_json()["message"]


def test_silent_recording_returns_no_speech(client):
    s = new(client)
    with client.websocket_connect(f"/api/ws/sessions/{s['session_id']}?token={s['token']}") as ws:
        ws.receive_json()
        ws.send_text(json.dumps({"type": "start"}))
        ws.send_bytes(b"\x00\x00" * 16000 * 3)
        ws.send_text(json.dumps({"type": "end"}))
        m = ws.receive_json()
        while m["type"] not in ("result", "error"):
            m = ws.receive_json()
    assert m["data"]["status"] == "no_speech" and m["data"]["overall"] is None


def test_audio_over_limit_is_cut_off_not_crashed(client):
    s = new(client, duration=5)
    with client.websocket_connect(f"/api/ws/sessions/{s['session_id']}?token={s['token']}") as ws:
        ws.receive_json()
        ws.send_text(json.dumps({"type": "start"}))
        for _ in range(40):  # 40 s of audio into a 5 s session
            ws.send_bytes(b"\x01\x00" * 16000)
        m = ws.receive_json()
        while m["type"] not in ("result", "error"):
            m = ws.receive_json()
    assert m["type"] == "result"


def test_unknown_api_path_is_json_404_even_with_spa(settings, tmp_path):
    from dataclasses import replace

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>app</html>")
    app = create_app(replace(settings, frontend_dist=dist), engine=FakeEngine())
    with TestClient(app) as c:
        assert c.get("/some/deep/link").text == "<html>app</html>"
        r = c.get("/api/nope")
        assert r.status_code == 404 and "html" not in r.headers["content-type"]
