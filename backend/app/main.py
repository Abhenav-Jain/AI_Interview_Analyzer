"""FastAPI application.

REST     POST /api/sessions                 create a session -> {session_id, token}
         GET  /api/sessions/{id}            status / result    (X-Session-Token)
         DELETE /api/sessions/{id}          erase all data     (X-Session-Token)
         GET  /api/health | /api/ready | /api/config
WebSocket /api/ws/sessions/{id}?token=...   live audio + face samples in, partial
                                            transcript / stages / result out
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Header, HTTPException, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .config import Settings, load_settings
from .db import Database
from .llm import LLMClient
from .logging_setup import setup_logging
from .pipeline import LimitExceeded, SessionRun
from .schemas import CreateSessionRequest, CreateSessionResponse, PublicConfig, SessionOut
from .security import RateLimiter, client_ip
from .stt import FasterWhisperEngine, NullEngine, STTEngine

log = logging.getLogger("api")


def build_engine(s: Settings) -> STTEngine:
    if s.stt_backend == "none":
        return NullEngine()
    return FasterWhisperEngine(
        s.whisper_model,
        s.whisper_device,
        s.whisper_compute_type,
        s.whisper_beam_size,
        s.whisper_cpu_threads,
        str(s.model_dir) if s.model_dir else None,
    )


class _SPAFiles(StaticFiles):
    """Serve the built React app; unknown paths fall back to index.html."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except (StarletteHTTPException, HTTPException) as ex:
            if ex.status_code == 404 and not path.startswith("api/"):
                return await super().get_response("index.html", scope)
            raise


def create_app(settings: Settings | None = None, *, engine: STTEngine | None = None, llm: LLMClient | None = None) -> FastAPI:
    s = settings or load_settings()
    setup_logging(s.log_level, s.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = s
        app.state.db = Database(s.db_path)
        app.state.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stt")
        app.state.engine = engine or build_engine(s)
        app.state.llm = llm or LLMClient(s.llm_api_key, s.llm_base_url, s.llm_model, s.llm_timeout)
        app.state.limiter = RateLimiter(s.rate_limit_per_min)
        app.state.active = 0
        app.state.stt_error = None
        if not app.state.llm.enabled:
            log.warning("No LLM_API_KEY set: content will be scored with local rules only.")

        async def _warm():
            try:
                await asyncio.get_running_loop().run_in_executor(app.state.executor, app.state.engine.load)
            except Exception as e:  # noqa: BLE001
                app.state.stt_error = str(e)
                log.exception("Speech model failed to load")

        async def _janitor():
            while True:
                n = app.state.db.purge_older_than(s.retention_days)
                if n:
                    log.info("Purged %d expired sessions", n)
                await asyncio.sleep(6 * 3600)

        tasks = [asyncio.create_task(_warm()), asyncio.create_task(_janitor())]
        try:
            yield
        finally:
            for t in tasks:
                t.cancel()
            app.state.executor.shutdown(wait=False, cancel_futures=True)
            await app.state.llm.aclose()
            app.state.db.close()

    app = FastAPI(title="AI Interview Analyzer", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(s.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Session-Token", "X-API-Key"],
    )

    @app.middleware("http")
    async def _request_ctx(request: Request, call_next):
        rid, t0 = uuid.uuid4().hex[:8], time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled error", extra={"request_id": rid, "path": request.url.path})
            return JSONResponse({"detail": "Internal server error"}, status_code=500)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(self), geolocation=()"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            log.info(
                "%s %s",
                request.method,
                request.url.path,
                extra={"request_id": rid, "status": response.status_code, "ms": int((time.perf_counter() - t0) * 1000)},
            )
        return response

    api = APIRouter(prefix="/api")

    # ------------------------------------------------------------ helpers
    def _auth_session(request: Request, session_id: str, header_token: str | None, query_token: str | None) -> None:
        if not request.app.state.db.verify_token(session_id, header_token or query_token):
            raise HTTPException(404, "Session not found")  # same answer for "missing" and "wrong token"

    # ------------------------------------------------------------ routes
    @api.get("/health")
    async def health(request: Request):
        st = request.app.state
        return {
            "status": "ok",
            "version": __version__,
            "stt_ready": st.engine.ready,
            "stt_engine": st.engine.name,
            "llm_configured": st.llm.enabled,
            "active_sessions": st.active,
        }

    @api.get("/ready")
    async def ready(request: Request):
        st = request.app.state
        if st.stt_error:
            return JSONResponse({"ready": False, "error": st.stt_error}, status_code=503)
        if not st.engine.ready:
            return JSONResponse({"ready": False, "error": "speech model is still loading"}, status_code=503)
        return {"ready": True}

    @api.get("/config", response_model=PublicConfig)
    async def public_config(request: Request):
        st = request.app.state
        return PublicConfig(
            version=__version__,
            min_duration=s.min_duration,
            max_duration=s.max_duration,
            default_duration=s.default_duration,
            stt_model=st.engine.name,
            llm_enabled=st.llm.enabled,
            api_key_required=bool(s.api_key),
        )

    @api.post("/sessions", response_model=CreateSessionResponse, status_code=201)
    async def create_session(body: CreateSessionRequest, request: Request, x_api_key: str | None = Header(default=None)):
        st = request.app.state
        if s.api_key and x_api_key != s.api_key:
            raise HTTPException(401, "Invalid or missing API key")
        if not st.limiter.allow(client_ip(request, s.trust_proxy)):
            raise HTTPException(429, "Too many sessions. Please wait a minute and try again.")
        if not (s.min_duration <= body.duration <= s.max_duration):
            raise HTTPException(422, f"duration must be between {s.min_duration} and {s.max_duration} seconds")
        if st.stt_error or not st.engine.ready:
            raise HTTPException(503, "The speech model is still loading. Try again in a few seconds.")
        topic = " ".join(body.topic.split())
        sid, token = st.db.create_session(topic, body.duration)
        return CreateSessionResponse(session_id=sid, token=token, duration=body.duration, topic=topic)

    @api.get("/sessions/{session_id}", response_model=SessionOut)
    async def get_session(
        session_id: str,
        request: Request,
        x_session_token: str | None = Header(default=None),
        token: str | None = Query(default=None),
    ):
        _auth_session(request, session_id, x_session_token, token)
        row = request.app.state.db.get(session_id)
        if not row:
            raise HTTPException(404, "Session not found")
        return SessionOut(
            session_id=row["id"],
            status=row["status"],
            stage=row["stage"],
            topic=row["topic"],
            duration=row["duration"],
            created_at=row["created_at"],
            result=row["result"],
            error=row["error"],
        )

    @api.delete("/sessions/{session_id}", status_code=204)
    async def delete_session(session_id: str, request: Request, x_session_token: str | None = Header(default=None)):
        _auth_session(request, session_id, x_session_token, None)
        request.app.state.db.delete(session_id)

    # ---------------------------------------------------------- websocket
    def _origin_ok(ws: WebSocket) -> bool:
        origin = ws.headers.get("origin")
        if not origin or not s.is_prod:
            return True
        host = ws.headers.get("host", "")
        return origin in s.cors_origins or origin.split("://", 1)[-1] == host

    @api.websocket("/ws/sessions/{session_id}")
    async def ws_session(ws: WebSocket, session_id: str, token: str | None = Query(default=None)):
        st = ws.app.state
        db: Database = st.db
        await ws.accept()

        async def send(payload: dict) -> None:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:  # noqa: BLE001 - client already gone
                pass

        async def reject(code: int, msg: str) -> None:
            await send({"type": "error", "message": msg})
            await ws.close(code=code)

        if not _origin_ok(ws):
            return await reject(4403, "Origin not allowed")
        if not db.verify_token(session_id, token):
            return await reject(4401, "Invalid session")
        row = db.get(session_id)
        if not row or row["status"] != "created":
            return await reject(4409, "This session has already been used. Start a new one.")
        if st.stt_error or not st.engine.ready:
            return await reject(4503, "The speech model is still loading.")
        if st.active >= s.max_active_sessions:
            return await reject(4503, "The server is busy with other interviews. Try again shortly.")

        st.active += 1
        run = SessionRun(
            session_id=session_id,
            topic=row["topic"],
            duration=row["duration"],
            engine=st.engine,
            executor=st.executor,
            llm=st.llm,
            settings=s,
            send=send,
        )
        try:
            db.update(session_id, status="recording")
            await send({"type": "ready", "duration": row["duration"]})
            started, deadline = False, None
            while True:
                timeout = max(0.1, deadline - time.monotonic()) if deadline else 120.0
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=timeout)
                except TimeoutError:
                    if started:
                        break  # time is up: analyse what we have
                    db.update(session_id, status="aborted", error="Timed out before recording started")
                    return await reject(4408, "Timed out waiting for the recording to start.")
                if msg["type"] == "websocket.disconnect":
                    db.update(session_id, status="aborted")
                    return
                if msg.get("bytes") is not None:
                    if started:
                        try:
                            run.add_audio(msg["bytes"])
                        except LimitExceeded:
                            break
                    continue
                text = msg.get("text")
                if not text:
                    continue
                try:
                    m = json.loads(text)
                except json.JSONDecodeError:
                    continue
                kind = m.get("type")
                if kind == "start" and not started:
                    started = True
                    deadline = time.monotonic() + row["duration"] + s.grace_seconds
                elif kind == "calibration":
                    run.add_calibration(m.get("samples") or [])
                elif kind == "face" and started:
                    run.add_face(m.get("samples") or [])
                elif kind == "ping":
                    await send({"type": "pong"})
                elif kind == "end":
                    break

            db.update(session_id, status="processing", stage="transcribing")
            try:
                result = await asyncio.wait_for(run.finish(), timeout=120)
            except Exception:  # noqa: BLE001
                log.exception("analysis failed", extra={"session_id": session_id})
                db.update(session_id, status="failed", error="Analysis failed. Please try again.")
                await send({"type": "error", "message": "Analysis failed. Please try again."})
                return
            payload = result.model_dump(mode="json")
            stored = dict(payload)
            if not s.store_transcripts:
                stored.update(transcript="", filler_spans=[])
            db.update(session_id, status="done", stage="done", result=stored)
            await send({"type": "result", "data": payload})
            await ws.close(code=1000)
        except Exception:  # noqa: BLE001
            log.exception("websocket error", extra={"session_id": session_id})
            db.update(session_id, status="failed", error="Connection error")
        finally:
            st.active -= 1

    app.include_router(api)

    # ------------------------------------------------- built frontend (prod)
    dist: Path | None = s.frontend_dist
    if dist and (dist / "index.html").exists():
        app.mount("/", _SPAFiles(directory=str(dist), html=True), name="web")
    else:

        @app.get("/")
        async def root():
            return {"name": "AI Interview Analyzer", "version": __version__, "docs": "/docs"}

    return app


def get_app() -> FastAPI:  # `uvicorn app.main:get_app --factory`
    return create_app()
