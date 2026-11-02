"""Central configuration. Everything is driven by environment variables so the
same image runs on a laptop, Render, Railway, ECS or a VPS without code edits."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


def _s(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v.strip() if v and v.strip() else default


def _i(name: str, default: int) -> int:
    try:
        return int(_s(name, str(default)))  # type: ignore[arg-type]
    except ValueError:
        return default


def _f(name: str, default: float) -> float:
    try:
        return float(_s(name, str(default)))  # type: ignore[arg-type]
    except ValueError:
        return default


def _b(name: str, default: bool) -> bool:
    v = _s(name)
    return default if v is None else v.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # runtime
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    log_json: bool = False
    log_level: str = "INFO"

    # http
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    api_key: str | None = None  # if set, POST /api/sessions needs X-API-Key
    trust_proxy: bool = False
    rate_limit_per_min: int = 12
    frontend_dist: Path | None = None

    # storage
    data_dir: Path = REPO_ROOT / "data"
    retention_days: int = 30
    store_transcripts: bool = True

    # sessions
    min_duration: int = 15
    max_duration: int = 180
    default_duration: int = 60
    max_active_sessions: int = 3
    grace_seconds: int = 8

    # speech-to-text
    stt_backend: str = "whisper"  # whisper | none
    whisper_model: str = "small.en"
    whisper_device: str = "auto"
    whisper_compute_type: str = "int8"
    whisper_beam_size: int = 3
    whisper_cpu_threads: int = 0
    model_dir: Path | None = None
    stt_chunk_seconds: float = 8.0

    # LLM (any OpenAI-compatible endpoint; Mistral by default)
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.mistral.ai/v1"
    llm_model: str = "mistral-small-latest"
    llm_timeout: float = 25.0

    # scoring weights (re-normalised automatically if a module is unavailable)
    w_audio: float = 0.35
    w_expression: float = 0.20
    w_content: float = 0.45

    @property
    def db_path(self) -> Path:
        return self.data_dir / "analyzer.sqlite3"

    @property
    def is_prod(self) -> bool:
        return self.app_env == "production"


def load_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(REPO_ROOT / "backend" / ".env")

    origins = _s("CORS_ORIGINS")
    dist = _s("FRONTEND_DIST")
    if dist is None and (REPO_ROOT / "frontend" / "dist").exists():
        dist = str(REPO_ROOT / "frontend" / "dist")

    return Settings(
        app_env=_s("APP_ENV", "development") or "development",
        host=_s("HOST", "0.0.0.0") or "0.0.0.0",
        port=_i("PORT", 8000),
        log_json=_b("LOG_JSON", False),
        log_level=(_s("LOG_LEVEL", "INFO") or "INFO").upper(),
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()) if origins else Settings.cors_origins,
        api_key=_s("API_KEY"),
        trust_proxy=_b("TRUST_PROXY", False),
        rate_limit_per_min=_i("RATE_LIMIT_PER_MIN", 12),
        frontend_dist=Path(dist) if dist else None,
        data_dir=Path(_s("DATA_DIR", str(REPO_ROOT / "data")) or ""),
        retention_days=_i("RETENTION_DAYS", 30),
        store_transcripts=_b("STORE_TRANSCRIPTS", True),
        min_duration=_i("MIN_DURATION", 15),
        max_duration=_i("MAX_DURATION", 180),
        default_duration=_i("DEFAULT_DURATION", 60),
        max_active_sessions=_i("MAX_ACTIVE_SESSIONS", 3),
        stt_backend=(_s("STT_BACKEND", "whisper") or "whisper").lower(),
        whisper_model=_s("WHISPER_MODEL", "small.en") or "small.en",
        whisper_device=_s("WHISPER_DEVICE", "auto") or "auto",
        whisper_compute_type=_s("WHISPER_COMPUTE_TYPE", "int8") or "int8",
        whisper_beam_size=_i("WHISPER_BEAM_SIZE", 3),
        whisper_cpu_threads=_i("WHISPER_CPU_THREADS", 0),
        model_dir=Path(_s("MODEL_DIR")) if _s("MODEL_DIR") else None,  # type: ignore[arg-type]
        stt_chunk_seconds=_f("STT_CHUNK_SECONDS", 8.0),
        # MISTRAL_API_KEY kept for backwards compatibility with v1 .env files
        llm_api_key=_s("LLM_API_KEY") or _s("MISTRAL_API_KEY"),
        llm_base_url=(_s("LLM_BASE_URL", "https://api.mistral.ai/v1") or "").rstrip("/"),
        llm_model=_s("LLM_MODEL", "mistral-small-latest") or "mistral-small-latest",
        llm_timeout=_f("LLM_TIMEOUT", 25.0),
        w_audio=_f("W_AUDIO", 0.35),
        w_expression=_f("W_EXPRESSION", 0.20),
        w_content=_f("W_CONTENT", 0.45),
    )
