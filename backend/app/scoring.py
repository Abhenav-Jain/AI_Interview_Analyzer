"""Scoring. Every sub-score is a *named component* with the measured value, what
it means, and (when there is room to improve) a concrete piece of advice. That
is what the UI shows, so the user always sees *why* they got a number.

Design rules that fix v1's weaknesses:
  * Smooth "band" functions instead of cliffs (v1: 110 wpm = 25 pts, 109 = 15).
  * Pace uses *speaking time*, not wall-clock, so pauses do not fake a slow pace.
  * A missing modality (camera denied, no LLM) is excluded and the remaining
    weights are re-normalised - v1 silently scored it 0 and dragged the total down.
  * No reward for buzzwords; content is judged by the rubric + evidence.
  * An answer with no detectable speech yields status "no_speech", not a fake score.
"""

from __future__ import annotations

from .audio_features import AudioFeatures
from .llm import RUBRIC, LLMEvaluation
from .schemas import (
    Component,
    ContentResult,
    FillerStat,
    ModuleResult,
    Reliability,
    Result,
    RubricItem,
    Tip,
)
from .text_metrics import TextMetrics


# ------------------------------------------------------------------ helpers
def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def band(x: float, lo: float, ilo: float, ihi: float, hi: float) -> float:
    """1.0 inside [ilo, ihi]; linear fall-off to 0 at lo / hi."""
    if ilo <= x <= ihi:
        return 1.0
    if x < ilo:
        return clamp01((x - lo) / (ilo - lo)) if ilo > lo else 0.0
    return clamp01((hi - x) / (hi - ihi)) if hi > ihi else 0.0


def _comp(key, label, frac, max_pts, display, note=None, advice_if_low=None, threshold=0.8) -> Component:
    score = round(clamp01(frac) * max_pts, 1)
    return Component(
        key=key,
        label=label,
        score=score,
        max=max_pts,
        display=display,
        note=note,
        advice=advice_if_low if (advice_if_low and frac < threshold) else None,
    )


def _total(components: list[Component]) -> int:
    mx = sum(c.max for c in components)
    return int(round(sum(c.score for c in components) / mx * 100)) if mx else 0


def label_for(score: int | None) -> str:
    if score is None:
        return "Not scored"
    if score >= 85:
        return "Outstanding"
    if score >= 70:
        return "Strong"
    if score >= 55:
        return "Decent"
    return "Needs work"


# -------------------------------------------------------------------- audio
def score_audio(feat: AudioFeatures | None, text: TextMetrics) -> ModuleResult:
    if feat is None or not feat.has_speech or text.word_count == 0:
        return ModuleResult(available=False, notes=["No speech was detected."])

    speaking_min = max(feat.speaking_time_s, 1.0) / 60
    wpm = text.word_count / speaking_min
    comps: list[Component] = []

    # pace -----------------------------------------------------------------
    pace_note = "Comfortable range is about 120-165 words per minute."
    pace_adv = (
        f"You spoke at about {wpm:.0f} wpm - too fast to absorb. Pause for a beat after each key point."
        if wpm > 165
        else f"At about {wpm:.0f} wpm you sound hesitant. Rehearse the answer once aloud to build momentum."
    )
    comps.append(_comp("pace", "Speaking pace", band(wpm, 80, 120, 165, 210), 25, f"{wpm:.0f} wpm", pace_note, pace_adv))

    # fluency --------------------------------------------------------------
    f_fill = clamp01(1 - max(0.0, text.filler_per_100 - 2) / 8)
    lp_rate = feat.long_pause_count / max(feat.speech_span_s / 60, 0.5)
    f_pause = clamp01(1 - max(0.0, lp_rate - 1) / 4)
    top = text.fillers[0] if text.fillers else None
    fl_adv = None
    if f_fill < 0.8 and top:
        fl_adv = f'Your most frequent filler is "{top[0]}" ({top[1]}x). Swap it for a silent half-second pause.'
    elif f_pause < 0.8:
        fl_adv = f"{feat.long_pause_count} pauses longer than {1.2:.1f}s broke your flow. Outline your first sentence before you start."
    comps.append(
        _comp(
            "fluency",
            "Fluency",
            0.65 * f_fill + 0.35 * f_pause,
            30,
            f"{text.filler_count} fillers, {feat.long_pause_count} long pauses",
            "Fillers per 100 words and pauses over 1.2 s.",
            fl_adv,
            threshold=0.85,
        )
    )

    # vocal variety ----------------------------------------------------------
    if feat.pitch_coverage < 0.3:
        comps.append(
            _comp("variety", "Vocal variety", 0.6, 15, "not measurable", "Pitch could not be tracked reliably on this recording.")
        )
    else:
        comps.append(
            _comp(
                "variety",
                "Vocal variety",
                band(feat.pitch_std_st, 0.8, 2.2, 5.5, 9.0),
                15,
                f"{feat.pitch_std_st:.1f} semitones",
                "Pitch variation; 2-5 semitones sounds engaged, under 1 sounds monotone.",
                "Your pitch is quite flat. Lift your voice on the key result and slow down on the main point."
                if feat.pitch_std_st < 2.2
                else "Your pitch swings a lot, which can sound nervous. Anchor each sentence on a steady tone.",
            )
        )

    # volume & recording quality ---------------------------------------------
    lvl = band(feat.loudness_dbfs, -48, -30, -15, -6)
    snr = band(feat.snr_db, 6, 18, 80, 100)
    clip = 1 - min(1.0, feat.clipping_ratio / 0.02)
    vol_adv = None
    if lvl < 0.8:
        vol_adv = "Your voice is too quiet or too hot on the mic. Sit about an arm's length away and speak from the chest."
    elif snr < 0.8:
        vol_adv = "Background noise is high compared with your voice. Use a quieter room or a headset mic."
    elif clip < 0.8:
        vol_adv = "Your audio is clipping (too loud). Lower the input gain or move back from the mic."
    comps.append(
        _comp(
            "volume",
            "Volume & clarity",
            0.5 * lvl + 0.35 * snr + 0.15 * clip,
            15,
            f"{feat.loudness_dbfs:.0f} dBFS, SNR {feat.snr_db:.0f} dB",
            "Loudness and background noise.",
            vol_adv,
        )
    )

    # rhythm -----------------------------------------------------------------
    r_adv = None
    if feat.voiced_ratio < 0.72:
        r_adv = 'A lot of silence sits between your phrases. Link your ideas with short bridges such as "the result was...".'
    elif feat.voiced_ratio > 0.95:
        r_adv = "You barely pause. Short pauses after key points make you sound more confident."
    comps.append(
        _comp(
            "rhythm",
            "Rhythm",
            band(feat.voiced_ratio, 0.45, 0.72, 0.95, 1.0),
            15,
            f"{feat.voiced_ratio * 100:.0f}% continuous",
            "Share of your speaking span that is actual speech.",
            r_adv,
        )
    )

    metrics = {
        "wpm": round(wpm, 1),
        "word_count": text.word_count,
        "filler_count": text.filler_count,
        "filler_per_100": round(text.filler_per_100, 1),
        "pause_count": feat.pause_count,
        "long_pause_count": feat.long_pause_count,
        "longest_pause_s": round(feat.longest_pause_s, 1),
        "speaking_time_s": round(feat.speaking_time_s, 1),
        "pitch_std_semitones": round(feat.pitch_std_st, 2),
        "loudness_dbfs": round(feat.loudness_dbfs, 1),
        "snr_db": round(feat.snr_db, 1),
        "clipping_ratio": round(feat.clipping_ratio, 4),
    }
    return ModuleResult(score=_total(comps), components=comps, metrics=metrics)


# --------------------------------------------------------------- expression
def score_expression(face: dict | None) -> ModuleResult:
    if not face:
        return ModuleResult(available=False, notes=["Camera data was not available, so expression is not scored."])
    if not face.get("usable"):
        return ModuleResult(
            available=False,
            notes=[f"Your face was visible in only {face.get('presence', 0) * 100:.0f}% of frames, so expression is not scored."],
        )

    ec, pres = face["eye_contact"], face["presence"]
    comps: list[Component] = []
    ec_adv = (
        f"You looked away from the camera often ({face['look_away_events']} stretches over 2 s). "
        "Glance at notes briefly, then return to the lens."
    )
    comps.append(
        _comp(
            "eye_contact",
            "Eye contact",
            band(ec, 0.2, 0.6, 1.0, 1.01),
            40,
            f"{ec * 100:.0f}% of the time",
            "Face and gaze pointed at the camera, compared with your own calibration.",
            ec_adv,
        )
    )
    comps.append(
        _comp(
            "presence",
            "On-camera presence",
            band(pres, 0.5, 0.9, 1.0, 1.01),
            15,
            f"{pres * 100:.0f}% in frame",
            "Share of frames where your face was visible.",
            "You drifted out of frame. Centre your face and keep the camera at eye level.",
        )
    )
    hs = face["head_speed_dps"]
    head_adv = (
        "Your head barely moved, which can read as stiff. Natural nods and small gestures help."
        if hs < 3
        else "You moved your head a lot. Plant your posture and let your hands do the gesturing."
    )
    comps.append(
        _comp(
            "head",
            "Head movement",
            band(hs, 0.8, 3, 30, 70),
            20,
            f"{hs:.0f} deg/s",
            "Natural nodding is good; stiffness or fidgeting is not.",
            head_adv,
        )
    )
    if face.get("blink_reliable"):
        br = face["blink_rate"]
        comps.append(
            _comp(
                "blinks",
                "Composure (blink rate)",
                band(br, 4, 9, 26, 45),
                15,
                f"{br:.0f}/min",
                "Typical relaxed blink rate is 12-20 per minute; a very high rate suggests tension.",
                "Your blink rate suggests tension. Take a slow breath before you answer.",
            )
        )
    sr = face["smile_ratio"]
    comps.append(
        _comp(
            "warmth",
            "Warmth",
            band(sr, 0.0, 0.10, 0.65, 1.0),
            10,
            f"smiling {sr * 100:.0f}% of the time",
            "A genuine smile now and then builds rapport.",
            "You rarely smiled. A brief smile at your opening and closing lines makes you more approachable."
            if sr < 0.10
            else "A constant smile can look nervous. Match your expression to what you are saying.",
        )
    )

    metrics = {
        "eye_contact": round(ec, 3),
        "presence": round(pres, 3),
        "look_away_events": face["look_away_events"],
        "longest_look_away_s": round(face["longest_look_away_s"], 1),
        "blink_rate_per_min": round(face["blink_rate"], 1) if face.get("blink_reliable") else None,
        "head_speed_dps": round(hs, 1),
        "smile_ratio": round(sr, 3),
        "calibrated": bool(face.get("calibrated")),
        "sample_rate_hz": round(face.get("sample_rate_hz", 0), 1),
    }
    return ModuleResult(score=_total(comps), components=comps, metrics=metrics)


# ------------------------------------------------------------------ content
def _local_content(text: TextMetrics, duration_s: float) -> tuple[int, list[str], list[str]]:
    """Heuristic estimate used when the LLM is unavailable. Capped at 70: rules
    cannot judge meaning, so they must never award a top score."""
    n = text.word_count
    per_min = n / max(duration_s / 60, 0.25)
    adequacy = band(per_min, 30, 90, 190, 260)
    structure = (min(text.context_count, 1) + min(text.action_count, 1) + min(text.impact_count, 1)) / 3
    specificity = clamp01((text.number_count + text.action_count) / 4)
    fluency = clamp01(1 - text.filler_per_100 / 12)
    diversity = band(text.unique_ratio, 0.3, 0.5, 0.95, 1.0) if n >= 30 else 0.6
    penalty = min(0.12, text.hedge_count * 0.03 + text.repeat_count * 0.02)
    raw = 0.30 * adequacy + 0.25 * structure + 0.20 * specificity + 0.15 * fluency + 0.10 * diversity - penalty
    score = int(round(clamp01(raw) * 70))

    strengths, improvements = [], []
    if text.action_count:
        strengths.append('You described your own actions with ownership ("I built/led...").')
    if text.number_count:
        strengths.append("You backed claims with numbers.")
    if text.impact_count:
        strengths.append("You mentioned outcomes, which is what interviewers remember.")
    if not text.number_count:
        improvements.append("Add one measurable result (a number, percentage or time saved).")
    if not text.impact_count:
        improvements.append("End with the outcome: what changed because of your work?")
    if not text.context_count:
        improvements.append("Open with one line of context (situation or goal) before the details.")
    return score, strengths[:3], improvements[:3]


def score_content(llm: LLMEvaluation | None, text: TextMetrics, duration_s: float) -> ContentResult:
    if text.word_count == 0:
        return ContentResult(available=False)

    local, l_str, l_imp = _local_content(text, duration_s)
    metrics = {
        "word_count": text.word_count,
        "unique_word_ratio": round(text.unique_ratio, 3),
        "numbers_cited": text.number_count,
        "outcome_phrases": text.impact_count,
        "ownership_phrases": text.action_count,
        "hedges": text.hedge_count,
        "repeated_words": text.repeat_count,
        "first_person_ratio": round(text.first_person_ratio, 2) if text.first_person_ratio is not None else None,
    }

    # hard caps for answers too short to be judged generously
    cap = 100 if text.word_count >= 50 else 60 if text.word_count >= 25 else 35

    if llm is None:
        return ContentResult(
            score=min(local, cap),
            llm_used=False,
            local_score=local,
            strengths=l_str,
            improvements=l_imp,
            summary="AI feedback was unavailable, so this is a rule-based estimate (maximum 70). Add an API key for a full evaluation.",
            transcript_quality="unknown",
            metrics=metrics,
        )

    rubric = [
        RubricItem(key=k, label=lbl, weight=w, score=getattr(llm, k).score, reason=getattr(llm, k).reason) for k, lbl, w in RUBRIC
    ]
    return ContentResult(
        score=min(llm.weighted_score(), cap),
        llm_used=True,
        rubric=rubric,
        strengths=llm.strengths or l_str,
        improvements=llm.improvements or l_imp,
        summary=llm.summary,
        local_score=local,
        transcript_quality=llm.transcript_quality,
        metrics=metrics,
    )


# ------------------------------------------------------------------ overall
def build_result(
    *,
    weights: dict[str, float],
    duration_s: float,
    transcript: str,
    stt_confidence: float | None,
    audio_feat: AudioFeatures | None,
    face: dict | None,
    llm: LLMEvaluation | None,
    text: TextMetrics,
    face_calibrated: bool,
    timings_ms: dict[str, int],
) -> Result:
    audio = score_audio(audio_feat, text)
    expression = score_expression(face)
    content = score_content(llm, text, duration_s)

    fillers = [FillerStat(word=w, count=c) for w, c in text.fillers]
    base = dict(
        transcript=transcript,
        transcript_confidence=round(stt_confidence, 3) if stt_confidence is not None else None,
        filler_spans=text.filler_spans,
        fillers=fillers,
        word_count=text.word_count,
        duration_s=round(duration_s, 1),
        timings_ms=timings_ms,
    )

    if not audio.available:  # nothing intelligible was said
        return Result(
            status="no_speech",
            overall=None,
            label="Not scored",
            weights={},
            audio=audio,
            expression=expression,
            content=ContentResult(available=False),
            tips=[
                Tip(
                    area="audio",
                    title="We could not hear you",
                    text="Check that the right microphone is selected, allow microphone access, and speak close to it.",
                    potential_gain=0,
                )
            ],
            reliability=Reliability(level="low", notes=["No usable speech was captured."]),
            **base,
        )

    avail = {
        "audio": audio.score,
        "expression": expression.score if expression.available else None,
        "content": content.score if content.available else None,
    }
    used = {k: weights[k] for k, v in avail.items() if v is not None}
    wsum = sum(used.values()) or 1.0
    norm = {k: w / wsum for k, w in used.items()}
    overall = int(round(sum(norm[k] * avail[k] for k in norm)))

    # reliability -------------------------------------------------------------
    notes: list[str] = []
    level = "high"
    if stt_confidence is not None and stt_confidence < 0.55:
        notes.append(
            "Speech recognition was uncertain. Some words in the transcript may be wrong, so content scores are less reliable. Try a quieter room or a closer mic."
        )
        level = "low"
    if text.word_count < 25:
        notes.append("Very short answer: scores are capped and less meaningful. Aim for at least 45 seconds.")
        level = "low"
    if not expression.available:
        notes.append("Expression was excluded from the total because camera data was missing.")
        level = "medium" if level == "high" else level
    elif not face_calibrated:
        notes.append("Camera calibration was skipped, so eye-contact is less precise.")
        level = "medium" if level == "high" else level
    if not content.llm_used:
        notes.append("Content was scored with local rules (maximum 70) because AI evaluation was unavailable.")
        level = "medium" if level == "high" else level
    if audio_feat and audio_feat.snr_db < 10:
        notes.append("Background noise was high; audio metrics may be off.")
        level = "medium" if level == "high" else level

    # tips: largest recoverable overall points first -------------------------
    tips: list[Tip] = []
    for area, mod in (("audio", audio), ("expression", expression)):
        if mod.score is None:
            continue
        w = norm.get(area, 0)
        mx = sum(c.max for c in mod.components)
        for c in mod.components:
            if c.advice:
                gain = (c.max - c.score) / mx * w * 100 if mx else 0
                tips.append(Tip(area=area, title=c.label, text=c.advice, potential_gain=max(1, int(round(gain)))))
    if content.score is not None and norm.get("content"):
        cw = norm["content"]
        if content.llm_used and content.rubric:
            weak = sorted(content.rubric, key=lambda r: (10 - r.score) * r.weight, reverse=True)
            for item, adv in zip(weak, content.improvements):
                gain = (10 - item.score) / 10 * item.weight * cw * 100
                if item.score <= 7:
                    tips.append(Tip(area="content", title=item.label, text=adv, potential_gain=max(1, int(round(gain)))))
        else:
            for adv in content.improvements:
                tips.append(Tip(area="content", title="Content", text=adv, potential_gain=max(1, int(round(cw * 100 * 0.1)))))
    tips.sort(key=lambda t: t.potential_gain, reverse=True)

    return Result(
        status="ok",
        overall=overall,
        label=label_for(overall),
        weights={k: round(v, 3) for k, v in norm.items()},
        audio=audio,
        expression=expression,
        content=content,
        tips=tips[:5],
        reliability=Reliability(level=level, notes=notes),
        **base,
    )
