"""
AI Interview Analyzer — FastAPI Backend
----------------------------------------
Exposes REST endpoints that wrap your three analysis modules.
Run with:  uvicorn main_api:app --reload --port 8000
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import threading
import time
import uuid
import json
import os
import sys

# ── Path setup ────────────────────────────────────────────────────────────────
# Adjust this to point at your src/ folder
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC_DIR)

from audio_module      import run_audio_analysis
from expression_module import run_expression_analysis
from nlp_analysis      import run_nlp_analysis

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="AI Interview Analyzer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory session store ───────────────────────────────────────────────────
# Replace with a DB (SQLite / Postgres) for persistence across restarts
sessions: dict[str, dict] = {}

# ── Weights (mirrors your main.py) ───────────────────────────────────────────
W_AUDIO      = 0.4
W_EXPRESSION = 0.4
W_NLP        = 0.2
DURATION     = 25          # seconds — frontend can override via query param


# ═════════════════════════════════════════════════════════════════════════════
# Schemas
# ═════════════════════════════════════════════════════════════════════════════

class StartRequest(BaseModel):
    duration: Optional[int] = DURATION


class SessionStatus(BaseModel):
    session_id: str
    status: str          # "running" | "done" | "error"
    progress: int        # 0-100
    final_score: Optional[int] = None
    audio_score: Optional[int] = None
    expression_score: Optional[int] = None
    nlp_score: Optional[int] = None
    audio_metrics: Optional[dict] = None
    expression_metrics: Optional[dict] = None
    nlp_metrics: Optional[dict] = None
    transcript: Optional[str] = None
    feedback: Optional[str] = None
    error: Optional[str] = None


# ═════════════════════════════════════════════════════════════════════════════
# Background worker
# ═════════════════════════════════════════════════════════════════════════════

def _run_session(session_id: str, duration: int):
    sess = sessions[session_id]
    sess["status"]   = "running"
    sess["progress"] = 0

    audio_score      = 0
    expression_score = 0
    nlp_score        = 0
    audio_metrics    = {}
    expression_metrics = {}
    nlp_metrics      = {}
    transcript       = ""

    # ── Phase 1: Audio + Expression in parallel ───────────────────────────
    def _audio():
        nonlocal audio_score, audio_metrics, transcript
        try:
            audio_score, audio_metrics, transcript = run_audio_analysis(duration)
        except Exception as e:
            sess["error"] = f"Audio error: {e}"

    def _expression():
        nonlocal expression_score, expression_metrics
        try:
            expression_score, expression_metrics = run_expression_analysis(duration)
        except Exception as e:
            sess["error"] = f"Expression error: {e}"

    t1 = threading.Thread(target=_audio,      daemon=True)
    t2 = threading.Thread(target=_expression, daemon=True)
    t1.start(); t2.start()

    # Poll progress while threads run
    start = time.time()
    while t1.is_alive() or t2.is_alive():
        elapsed = time.time() - start
        sess["progress"] = min(85, int((elapsed / duration) * 85))
        time.sleep(0.5)

    t1.join(); t2.join()
    sess["progress"] = 90

    # ── Phase 2: NLP (needs transcript) ───────────────────────────────────
    try:
        nlp_score, nlp_metrics = run_nlp_analysis(transcript)
    except Exception as e:
        sess["error"] = f"NLP error: {e}"

    sess["progress"] = 98

    # ── Phase 3: Final score ───────────────────────────────────────────────
    final_score = int(
        W_AUDIO      * audio_score +
        W_EXPRESSION * expression_score +
        W_NLP        * nlp_score
    )

    feedback = _feedback(final_score)

    # Commit to session store
    sess.update({
        "status":             "done",
        "progress":           100,
        "final_score":        final_score,
        "audio_score":        audio_score,
        "expression_score":   expression_score,
        "nlp_score":          nlp_score,
        "audio_metrics":      audio_metrics,
        "expression_metrics": expression_metrics,
        "nlp_metrics":        nlp_metrics,
        "transcript":         transcript,
        "feedback":           feedback,
    })

    # Persist to reports/
    _save_report(session_id, sess)


def _feedback(score: int) -> str:
    if score >= 85:
        return "Outstanding performance! Excellent communication, strong presence, and high-quality responses."
    elif score >= 70:
        return "Strong performance with minor improvements needed. Work on reducing filler words and improving expressiveness."
    elif score >= 55:
        return "Decent performance. Focus on clarity, reducing hesitations, and maintaining better eye contact."
    else:
        return "Significant improvement required. Practice structured responses, vocal confidence, and facial engagement."


def _save_report(session_id: str, data: dict):
    reports_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "reports"
    )
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, f"{session_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ═════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/", tags=["Health"])
def root():
    return {"message": "AI Interview Analyzer API is running."}


@app.post("/session/start", tags=["Session"])
def start_session(body: StartRequest, background_tasks: BackgroundTasks):
    """
    Start a new interview analysis session.
    Returns a session_id that the frontend polls with GET /session/{id}.
    """
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "status":   "running",
        "progress": 0,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    background_tasks.add_task(_run_session, session_id, body.duration)
    return {"session_id": session_id, "duration": body.duration}


@app.get("/session/{session_id}", response_model=SessionStatus, tags=["Session"])
def get_session(session_id: str):
    """Poll this endpoint to get live progress + final results."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    s = sessions[session_id]
    return SessionStatus(session_id=session_id, **s)


@app.get("/sessions", tags=["History"])
def list_sessions():
    """Return all completed sessions for the history panel."""
    history = []
    for sid, data in sessions.items():
        if data.get("status") == "done":
            history.append({
                "session_id":    sid,
                "started_at":    data.get("started_at", ""),
                "final_score":   data.get("final_score"),
                "audio_score":   data.get("audio_score"),
                "expression_score": data.get("expression_score"),
                "nlp_score":     data.get("nlp_score"),
                "feedback":      data.get("feedback"),
            })
    return sorted(history, key=lambda x: x["started_at"], reverse=True)


@app.delete("/session/{session_id}", tags=["Session"])
def delete_session(session_id: str):
    """Remove a session from memory (and its saved report)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del sessions[session_id]
    # Also remove report file if present
    reports_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "reports"
    )
    report_path = os.path.join(reports_dir, f"{session_id}.json")
    if os.path.exists(report_path):
        os.remove(report_path)
    return {"message": "Session deleted"}


@app.get("/health", tags=["Health"])
def health():
    return {
        "status":        "ok",
        "active_sessions": sum(1 for s in sessions.values() if s.get("status") == "running"),
        "total_sessions":  len(sessions),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_api:app", host="127.0.0.1", port=8000, reload=True)