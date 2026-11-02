"""Aggregates per-frame face samples produced *in the browser* (MediaPipe Face
Landmarker) into interview-relevant metrics.

Why this replaces v1's server-side OpenCV/DeepFace pipeline:
  * v1 read the *server's* webcam, which cannot work once deployed.
  * v1's "eye contact" used a 0.38-0.62 iris ratio, so 17 of 26 saved sessions
    reported exactly 1.0. Here gaze AND head pose are compared against a
    per-user calibration taken while the person looks into the camera.
  * Blinks come from the model's blink blendshapes with hysteresis instead of a
    fixed Eye-Aspect-Ratio threshold (which gave 0 to 91 blinks/min).
  * No video ever reaches the server — only ~10 small numeric samples/second.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator


class FaceSample(BaseModel):
    """One frame. Short keys keep the websocket payload tiny."""

    t: float = Field(ge=0, le=3600)  # seconds since recording start
    v: int = Field(default=1, ge=0, le=1)  # face visible
    sm: float = Field(default=0.0, ge=0, le=1)  # smile blendshape (avg L/R)
    bl: float = Field(default=0.0, ge=0, le=1)  # blink blendshape (avg L/R)
    yw: float = Field(default=0.0, ge=-180, le=180)  # head yaw, degrees
    pt: float = Field(default=0.0, ge=-180, le=180)  # head pitch, degrees
    gx: float = Field(default=0.0, ge=-2, le=2)  # horizontal gaze offset
    gy: float = Field(default=0.0, ge=-2, le=2)  # vertical gaze offset

    @field_validator("t", "sm", "bl", "yw", "pt", "gx", "gy", mode="before")
    @classmethod
    def _finite(cls, v):  # reject NaN/inf coming from a buggy client
        if isinstance(v, (int, float)) and not math.isfinite(v):
            raise ValueError("non-finite")
        return v


# thresholds ---------------------------------------------------------------
YAW_TOL = 15.0
PITCH_TOL = 14.0
GAZE_TOL = 0.30
BLINK_CLOSE, BLINK_OPEN = 0.55, 0.35
LOOK_AWAY_MIN_S = 2.0
SMILE_ON = 0.25
MIN_SAMPLES = 20  # ~2 s of video


@dataclass
class Baseline:
    yw: float = 0.0
    pt: float = 0.0
    gx: float = 0.0
    gy: float = 0.0
    calibrated: bool = False


def compute_baseline(samples: list[FaceSample]) -> Baseline:
    vis = [s for s in samples if s.v]
    if len(vis) < 5:
        return Baseline()
    med = statistics.median
    return Baseline(
        yw=med(s.yw for s in vis),
        pt=med(s.pt for s in vis),
        gx=med(s.gx for s in vis),
        gy=med(s.gy for s in vis),
        calibrated=True,
    )


def _wrap_pitch(p: float) -> float:
    while p > 90:
        p -= 180
    while p < -90:
        p += 180
    return p


def aggregate_face(samples: list[FaceSample], baseline: Baseline | None = None) -> dict | None:
    """Return metric dict, or None when there is too little usable video."""
    if len(samples) < MIN_SAMPLES:
        return None
    base = baseline or Baseline()
    samples = sorted(samples, key=lambda s: s.t)
    vis = [s for s in samples if s.v]
    presence = len(vis) / len(samples)
    if len(vis) < MIN_SAMPLES:
        return {"presence": presence, "usable": False}

    dts = [b.t - a.t for a, b in zip(samples, samples[1:]) if 0 < b.t - a.t < 1.0]
    dt = statistics.median(dts) if dts else 0.1
    visible_time = len(vis) * dt

    # --- eye contact (head pose AND gaze near the calibrated camera direction)
    def looking(s: FaceSample) -> bool:
        return (
            abs(s.yw - base.yw) <= YAW_TOL
            and abs(_wrap_pitch(s.pt - base.pt)) <= PITCH_TOL
            and abs(s.gx - base.gx) <= GAZE_TOL
            and abs(s.gy - base.gy) <= GAZE_TOL
        )

    flags = [looking(s) for s in vis]
    eye_contact = sum(flags) / len(flags)

    away_events, longest_away, run = 0, 0.0, 0.0
    for f in flags + [True]:
        if not f:
            run += dt
        else:
            if run >= LOOK_AWAY_MIN_S:
                away_events += 1
            longest_away = max(longest_away, run)
            run = 0.0

    # --- blinks (rising edge with hysteresis; a blink needs >= 1 closed sample)
    blinks, closed = 0, False
    for s in vis:
        if not closed and s.bl >= BLINK_CLOSE:
            closed = True
            blinks += 1
        elif closed and s.bl <= BLINK_OPEN:
            closed = False
    blink_rate = blinks / (visible_time / 60) if visible_time > 0 else 0.0
    # >60/min or a sampling rate too low to see blinks means the signal is junk
    blink_reliable = dt <= 0.25 and blink_rate <= 60

    # --- head motion (deg/s between consecutive visible samples) + spread
    speeds = []
    for a, b in zip(vis, vis[1:]):
        gap = b.t - a.t
        if 0 < gap <= 0.5:
            speeds.append((abs(b.yw - a.yw) + abs(_wrap_pitch(b.pt - a.pt))) / gap)
    head_speed = statistics.fmean(speeds) if speeds else 0.0
    head_spread = statistics.pstdev([s.yw for s in vis]) + statistics.pstdev([_wrap_pitch(s.pt) for s in vis])

    # --- warmth
    smile_mean = statistics.fmean(s.sm for s in vis)
    smile_ratio = sum(1 for s in vis if s.sm >= SMILE_ON) / len(vis)

    return {
        "usable": True,
        "presence": presence,
        "eye_contact": eye_contact,
        "look_away_events": away_events,
        "longest_look_away_s": longest_away,
        "blink_rate": blink_rate,
        "blink_reliable": blink_reliable,
        "head_speed_dps": head_speed,
        "head_spread_deg": head_spread,
        "smile_mean": smile_mean,
        "smile_ratio": smile_ratio,
        "calibrated": base.calibrated,
        "sample_rate_hz": 1 / dt if dt > 0 else 0.0,
        "visible_s": visible_time,
    }
