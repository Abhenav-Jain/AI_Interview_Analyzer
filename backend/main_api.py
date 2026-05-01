"""
AI Interview Analyzer — FastAPI Backend
----------------------------------------
Run with: uvicorn main_api:app --reload --port 8000
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
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC_DIR)

from audio_module import run_audio_analysis
from expression_module import run_expression_analysis
from nlp_analysis import run_nlp_analysis

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="AI Interview Analyzer API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Session Store ─────────────────────────────────────────────────────────────
sessions: dict[str, dict] = {}

# ── Weights ───────────────────────────────────────────────────────────────────
W_AUDIO = 0.35
W_EXPRESSION = 0.35
W_NLP = 0.30
DURATION = 25


# ═════════════════════════════════════════════════════════════════════════════
# Schemas
# ═════════════════════════════════════════════════════════════════════════════

class StartRequest(BaseModel):
    duration: Optional[int] = DURATION
    topic: Optional[str] = "General Interview"


class SessionStatus(BaseModel):
    session_id: str
    status: str
    progress: int
    final_score: Optional[int] = None
    audio_score: Optional[int] = None
    expression_score: Optional[int] = None
    nlp_score: Optional[int] = None
    audio_metrics: Optional[dict] = None
    expression_metrics: Optional[dict] = None
    nlp_metrics: Optional[dict] = None
    transcript: Optional[str] = None
    feedback: Optional[str] = None
    nlp_feedback: Optional[str] = None
    error: Optional[str] = None


# ═════════════════════════════════════════════════════════════════════════════
# Background Worker
# ═════════════════════════════════════════════════════════════════════════════

def _run_session(session_id: str, duration: int, topic: str):
    sess = sessions[session_id]
    sess["status"] = "running"
    sess["progress"] = 0

    audio_score = 0
    expression_score = 0
    nlp_score = 0
    audio_metrics = {}
    expression_metrics = {}
    nlp_metrics = {}
    transcript = ""
    nlp_feedback = ""

    # ── Audio Thread ─────────────────────────────────────────
    def _audio():
        nonlocal audio_score, audio_metrics, transcript
        try:
            audio_score, audio_metrics, transcript = run_audio_analysis(duration)
        except Exception as e:
            sess["error"] = f"Audio error: {e}"

    # ── Expression Thread ────────────────────────────────────
    def _expression():
        nonlocal expression_score, expression_metrics
        try:
            expression_score, expression_metrics = run_expression_analysis(duration)
        except Exception as e:
            sess["error"] = f"Expression error: {e}"

    t1 = threading.Thread(target=_audio, daemon=True)
    t2 = threading.Thread(target=_expression, daemon=True)

    t1.start()
    t2.start()

    # ── Progress Tracking ────────────────────────────────────
    start = time.time()
    while t1.is_alive() or t2.is_alive():
        elapsed = time.time() - start
        sess["progress"] = min(85, int((elapsed / duration) * 85))
        time.sleep(0.5)

    t1.join()
    t2.join()

    sess["progress"] = 90

    # ── NLP Phase (Mistral integrated) ───────────────────────
    try:
        nlp_score, nlp_metrics, nlp_feedback = run_nlp_analysis(transcript)
    except Exception as e:
        sess["error"] = f"NLP error: {e}"

    sess["progress"] = 98

    # ── Final Score ──────────────────────────────────────────
    final_score = int(
        W_AUDIO * audio_score +
        W_EXPRESSION * expression_score +
        W_NLP * nlp_score
    )

    # ── Smart Feedback ───────────────────────────────────────
    feedback = nlp_feedback if nlp_feedback else _fallback_feedback(final_score)

    # ── Save Session ─────────────────────────────────────────
    sess.update({
        "status": "done",
        "progress": 100,
        "final_score": final_score,
        "audio_score": audio_score,
        "expression_score": expression_score,
        "nlp_score": nlp_score,
        "audio_metrics": audio_metrics,
        "expression_metrics": expression_metrics,
        "nlp_metrics": nlp_metrics,
        "transcript": transcript,
        "feedback": feedback,
        "nlp_feedback": nlp_feedback
    })

    sessions[session_id] = sess
    print("✅ SESSION COMPLETED:", sessions[session_id]["status"])

    _save_report(session_id, sess)


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def _fallback_feedback(score: int) -> str:
    if score >= 85:
        return "Outstanding performance!"
    elif score >= 70:
        return "Strong performance with minor improvements."
    elif score >= 55:
        return "Decent performance, needs clarity improvement."
    else:
        return "Significant improvement required."


def _save_report(session_id: str, data: dict):
    reports_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "reports"
    )
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, f"{session_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ═════════════════════════════════════════════════════════════════════════════
# API Endpoints
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {"message": "AI Interview Analyzer API running 🚀"}


@app.post("/session/start")
def start_session(body: StartRequest, background_tasks: BackgroundTasks):
    session_id = str(uuid.uuid4())

    sessions[session_id] = {
        "status": "running",
        "progress": 0,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "topic": body.topic
    }

    background_tasks.add_task(
        _run_session,
        session_id,
        body.duration,
        body.topic
    )

    return {"session_id": session_id}


@app.get("/session/{session_id}", response_model=SessionStatus)
def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionStatus(session_id=session_id, **sessions[session_id])


@app.get("/sessions")
def list_sessions():
    return [
        {
            "session_id": sid,
            "started_at": data.get("started_at"),
            "final_score": data.get("final_score"),
            "audio_score": data.get("audio_score"),
            "expression_score": data.get("expression_score"),
            "nlp_score": data.get("nlp_score"),
            "feedback": data.get("feedback"),
        }
        for sid, data in sessions.items()
        if data.get("status") == "done"
    ]


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    del sessions[session_id]

    reports_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "reports"
    )
    report_path = os.path.join(reports_dir, f"{session_id}.json")

    if os.path.exists(report_path):
        os.remove(report_path)

    return {"message": "Session deleted"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "total_sessions": len(sessions)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_api:app", host="127.0.0.1", port=8000, reload=True)