"""Tiny SQLite persistence layer (WAL mode). Replaces the in-memory dict +
loose JSON files from v1, so sessions survive restarts and are never leaked
through a global listing endpoint. Audio is never written to disk."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    topic TEXT NOT NULL,
                    duration INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT,
                    result_json TEXT,
                    error TEXT
                )"""
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at)")

    def create_session(self, topic: str, duration: int) -> tuple[str, str]:
        sid, token = uuid.uuid4().hex, secrets.token_urlsafe(24)
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions(id, token_hash, created_at, topic, duration, status) VALUES (?,?,?,?,?,?)",
                (sid, _hash(token), time.time(), topic, duration, "created"),
            )
        return sid, token

    def verify_token(self, session_id: str, token: str | None) -> bool:
        if not token:
            return False
        with self._lock:
            row = self._conn.execute("SELECT token_hash FROM sessions WHERE id=?", (session_id,)).fetchone()
        return bool(row) and hmac.compare_digest(row["token_hash"], _hash(token))

    def get(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, created_at, topic, duration, status, stage, result_json, error FROM sessions WHERE id=?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["result"] = json.loads(d.pop("result_json")) if d.get("result_json") else None
        return d

    def update(self, session_id: str, **fields: Any) -> None:
        allowed = {"status", "stage", "error"}
        sets, vals = [], []
        for k, v in fields.items():
            if k == "result":
                sets.append("result_json=?")
                vals.append(json.dumps(v, ensure_ascii=False) if v is not None else None)
            elif k in allowed:
                sets.append(f"{k}=?")
                vals.append(v)
        if not sets:
            return
        vals.append(session_id)
        with self._lock:
            self._conn.execute(f"UPDATE sessions SET {', '.join(sets)} WHERE id=?", vals)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        return cur.rowcount > 0

    def purge_older_than(self, days: int) -> int:
        cutoff = time.time() - days * 86400
        with self._lock:
            cur = self._conn.execute("DELETE FROM sessions WHERE created_at < ?", (cutoff,))
        return cur.rowcount

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()
