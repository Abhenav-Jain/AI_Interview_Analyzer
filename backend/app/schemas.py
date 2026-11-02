from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    topic: str = Field(default="General interview", min_length=1, max_length=200)
    duration: int = Field(default=60, ge=5, le=600)


class CreateSessionResponse(BaseModel):
    session_id: str
    token: str = Field(description="Secret needed to stream to / read this session.")
    duration: int
    topic: str


class Component(BaseModel):
    """One scored sub-skill, e.g. 'pace' inside the audio module."""

    key: str
    label: str
    score: float
    max: float
    display: str  # human readable measured value, e.g. "148 wpm"
    note: str | None = None  # what the value means
    advice: str | None = None  # present when there is room to improve


class ModuleResult(BaseModel):
    score: int | None = None
    available: bool = True
    components: list[Component] = []
    metrics: dict[str, float | int | bool | None] = {}
    notes: list[str] = []


class RubricItem(BaseModel):
    key: str
    label: str
    score: int  # 0-10
    weight: float
    reason: str = ""


class ContentResult(BaseModel):
    score: int | None = None
    available: bool = True
    llm_used: bool = False
    rubric: list[RubricItem] = []
    strengths: list[str] = []
    improvements: list[str] = []
    summary: str = ""
    local_score: int | None = None
    transcript_quality: Literal["good", "fair", "poor", "unknown"] = "unknown"
    metrics: dict[str, float | int | None] = {}


class Tip(BaseModel):
    area: Literal["audio", "expression", "content"]
    title: str
    text: str
    potential_gain: int  # approx. overall points available


class Reliability(BaseModel):
    level: Literal["high", "medium", "low"]
    notes: list[str] = []


class FillerStat(BaseModel):
    word: str
    count: int


class Result(BaseModel):
    version: int = 2
    status: Literal["ok", "no_speech"] = "ok"
    overall: int | None = None
    label: str = ""
    weights: dict[str, float] = {}
    audio: ModuleResult
    expression: ModuleResult
    content: ContentResult
    tips: list[Tip] = []
    reliability: Reliability
    transcript: str = ""
    transcript_confidence: float | None = None
    filler_spans: list[tuple[int, int]] = []
    fillers: list[FillerStat] = []
    word_count: int = 0
    duration_s: float = 0.0
    timings_ms: dict[str, int] = {}


class SessionOut(BaseModel):
    session_id: str
    status: Literal["created", "recording", "processing", "done", "failed", "aborted"]
    stage: str | None = None
    topic: str
    duration: int
    created_at: float
    result: Result | None = None
    error: str | None = None


class PublicConfig(BaseModel):
    version: str
    min_duration: int
    max_duration: int
    default_duration: int
    stt_model: str
    llm_enabled: bool
    api_key_required: bool
