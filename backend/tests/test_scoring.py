import pytest

from app.audio_features import extract_audio_features
from app.face import Baseline, FaceSample, aggregate_face, compute_baseline
from app.llm import LLMEvaluation
from app.scoring import band, build_result, score_content, score_expression
from app.text_metrics import analyze_text

from .conftest import speech_clip

W = {"audio": 0.35, "expression": 0.20, "content": 0.45}
GOOD = (
    "I led a team of five engineers when our checkout was slow. The challenge was latency. "
    "I redesigned the cache layer and we reduced latency by 40 percent, which saved two million dollars."
)


def llm_eval(score=8):
    d = {"score": score, "reason": "ok"}
    return LLMEvaluation(
        relevance=d,
        structure=d,
        specificity=d,
        depth=d,
        clarity=d,
        strengths=["a"],
        improvements=["Add detail"],
        summary="s",
        transcript_quality="good",
    )


def face_samples(n=120, yaw=0.0, smile=0.3, dt=0.1):
    return [
        FaceSample(
            t=i * dt, v=1, sm=smile, bl=0.8 if i % 40 == 0 else 0.0, yw=yaw + (i % 7) * 0.8, pt=(i % 5) * 0.6, gx=0.0, gy=0.0
        )
        for i in range(n)
    ]


def test_band_shape():
    assert band(140, 80, 120, 165, 210) == 1
    assert band(100, 80, 120, 165, 210) == pytest.approx(0.5)
    assert band(300, 80, 120, 165, 210) == 0


def test_llm_weighted_score_is_deterministic():
    assert llm_eval(8).weighted_score() == 80


def test_short_answer_capped_even_if_llm_generous():
    c = score_content(llm_eval(10), analyze_text("I am a hard worker and a team player ok"), 20)
    assert c.score <= 35


def test_fallback_without_llm_capped_at_70():
    c = score_content(None, analyze_text(GOOD), 30)
    assert not c.llm_used and c.score <= 70


def test_eye_contact_uses_calibration_not_constant_one():
    cal = face_samples(30, yaw=25)  # user's "camera" direction is yaw 25
    base = compute_baseline(cal)
    on = aggregate_face(face_samples(100, yaw=25), base)
    off = aggregate_face(face_samples(100, yaw=60), base)
    assert on["eye_contact"] > 0.9 and off["eye_contact"] < 0.1


def test_blink_rate_and_unusable_video():
    m = aggregate_face(face_samples(300), Baseline())
    assert 10 <= m["blink_rate"] <= 20 and m["blink_reliable"]
    assert aggregate_face(face_samples(5)) is None
    gone = [FaceSample(t=i * 0.1, v=0) for i in range(100)]
    assert aggregate_face(gone)["usable"] is False
    assert score_expression(aggregate_face(gone)).available is False


def _result(face=None, llm=None, text=GOOD, conf=0.9):
    y = speech_clip()
    return build_result(
        weights=W,
        duration_s=12,
        transcript=text,
        stt_confidence=conf,
        audio_feat=extract_audio_features(y),
        face=face,
        llm=llm,
        text=analyze_text(text),
        face_calibrated=True,
        timings_ms={},
    )


def test_missing_modalities_renormalise_not_zero():
    full = _result(face=aggregate_face(face_samples(200), Baseline()), llm=llm_eval(8))
    nocam = _result(face=None, llm=llm_eval(8))
    assert full.status == nocam.status == "ok"
    assert nocam.expression.available is False
    assert abs(sum(nocam.weights.values()) - 1) < 0.01 and "expression" not in nocam.weights
    assert nocam.overall > 40  # v1 would have scored the missing camera as 0


def test_low_stt_confidence_flags_reliability():
    r = _result(llm=llm_eval(6), conf=0.3)
    assert r.reliability.level == "low" and any("recognition" in n for n in r.reliability.notes)


def test_no_speech_gives_no_fake_score():
    from .conftest import silence

    r = build_result(
        weights=W,
        duration_s=5,
        transcript="",
        stt_confidence=None,
        audio_feat=extract_audio_features(silence(5)),
        face=None,
        llm=None,
        text=analyze_text(""),
        face_calibrated=False,
        timings_ms={},
    )
    assert r.status == "no_speech" and r.overall is None


def test_tips_sorted_by_gain():
    r = _result(face=aggregate_face(face_samples(200, smile=0.0), Baseline()), llm=llm_eval(5))
    gains = [t.potential_gain for t in r.tips]
    assert gains == sorted(gains, reverse=True) and r.tips
