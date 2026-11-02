import numpy as np

from app.audio_features import extract_audio_features, pcm16_to_float
from app.text_metrics import analyze_text, find_fillers

from .conftest import silence, speech_clip, to_pcm16, voiced


def test_pauses_detected_and_edges_ignored():
    f = extract_audio_features(speech_clip())
    assert f.has_speech
    assert f.pause_count == 2 and f.long_pause_count == 1
    assert 1.3 < f.longest_pause_s < 1.7
    assert 7.5 < f.speaking_time_s < 8.6


def test_pitch_variation_vs_monotone():
    varied = extract_audio_features(np.concatenate([silence(1), voiced(6, 100, 160), silence(1)]))
    mono = extract_audio_features(np.concatenate([silence(1), voiced(6, 130, 130.3), silence(1)]))
    assert varied.pitch_std_st > 1.5 > 0.5 > mono.pitch_std_st


def test_silence_is_not_speech_and_quiet_mic_still_works():
    assert not extract_audio_features(silence(5)).has_speech
    assert extract_audio_features(speech_clip() * 0.1).has_speech


def test_pcm_roundtrip():
    y = voiced(1)
    assert np.allclose(pcm16_to_float(to_pcm16(y)), y, atol=1e-3)
    assert len(pcm16_to_float(b"\x01")) == 0


def test_fillers_only_when_really_fillers():
    assert analyze_text("I like coding and so we shipped it").filler_count == 0
    t = "So, um, it was, like, huge, you know."
    spans = find_fillers(t)[1]
    assert [t[s:e].lower() for s, e in spans] == ["so", "um", "like", "you know"]


def test_content_cues():
    m = analyze_text("I led a team. We reduced latency by 40% and saved 2 million. The challenge was scale.")
    assert m.action_count == 1 and m.impact_count >= 2 and m.number_count >= 2 and m.context_count == 1
