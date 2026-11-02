"""Acoustic analysis of a mono 16 kHz signal using numpy only.

v1 used librosa (heavy: numba, scipy, slow import) and judged "silence" with a
fixed RMS threshold, which breaks on quiet mics or noisy rooms. Here the
voice-activity threshold adapts to the recording's own noise floor, pauses are
measured as real gaps *between* speech (leading/trailing silence is ignored),
and pitch variation is expressed in semitones so it is speaker-independent.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

SAMPLE_RATE = 16_000
FRAME = 400  # 25 ms
HOP = 160  # 10 ms
EPS = 1e-10

PAUSE_MIN_S = 0.35  # shorter gaps are normal articulation
LONG_PAUSE_S = 1.2  # gaps that feel like "lost the thread"


def pcm16_to_float(data: bytes) -> np.ndarray:
    """Little-endian int16 PCM -> float32 in [-1, 1]. Odd trailing byte is dropped."""
    n = len(data) // 2
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(data, dtype="<i2", count=n).astype(np.float32) / 32768.0


@dataclass
class AudioFeatures:
    duration_s: float
    speaking_time_s: float  # time with voice activity
    speech_span_s: float  # first speech -> last speech
    voiced_ratio: float  # speaking_time / speech_span (how continuous the delivery is)
    pause_count: int
    long_pause_count: int
    longest_pause_s: float
    avg_pause_s: float
    pitch_std_st: float  # pitch variation in semitones
    pitch_coverage: float  # share of speech frames with a reliable pitch estimate
    loudness_dbfs: float  # mean level of speech frames
    volume_range_db: float  # p90 - p10 of speech frame levels
    noise_floor_dbfs: float
    snr_db: float
    clipping_ratio: float
    has_speech: bool

    def to_dict(self) -> dict:
        return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def _frames(y: np.ndarray) -> np.ndarray:
    if len(y) < FRAME:
        y = np.pad(y, (0, FRAME - len(y)))
    view = np.lib.stride_tricks.sliding_window_view(y, FRAME)[::HOP]
    return view


def _runs(mask: np.ndarray) -> list[tuple[int, int, bool]]:
    """Run-length encode a boolean array -> [(start, end_exclusive, value)]."""
    if mask.size == 0:
        return []
    change = np.flatnonzero(np.diff(mask.astype(np.int8))) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [mask.size]))
    return [(int(s), int(e), bool(mask[s])) for s, e in zip(starts, ends)]


def _smooth_vad(voiced: np.ndarray) -> np.ndarray:
    """Remove blips (<60 ms of 'speech') and bridge micro-gaps (<150 ms)."""
    v = voiced.copy()
    for s, e, val in _runs(v):  # bridge short gaps inside speech
        if not val and (e - s) < 15 and s > 0 and e < v.size:
            v[s:e] = True
    for s, e, val in _runs(v):  # drop isolated blips
        if val and (e - s) < 6:
            v[s:e] = False
    return v


def _pitch_semitone_std(y: np.ndarray, voiced_frames: np.ndarray) -> tuple[float, float]:
    """Autocorrelation pitch tracker over voiced frames. Returns (std in semitones, coverage)."""
    idx = np.flatnonzero(voiced_frames)
    if idx.size < 20:
        return 0.0, 0.0
    if idx.size > 1500:  # keep it fast on long answers
        idx = idx[:: int(np.ceil(idx.size / 1500))]

    win = 640  # 40 ms
    starts = idx * HOP
    starts = starts[starts + win <= len(y)]
    if starts.size < 20:
        return 0.0, 0.0
    frames = np.stack([y[s : s + win] for s in starts]).astype(np.float64)
    frames -= frames.mean(axis=1, keepdims=True)
    frames *= np.hanning(win)

    nfft = 2048
    spec = np.fft.rfft(frames, nfft, axis=1)
    ac = np.fft.irfft(spec * np.conj(spec), nfft, axis=1)[:, : win // 2]
    ac /= ac[:, :1] + EPS

    lo, hi = SAMPLE_RATE // 300, SAMPLE_RATE // 75  # 75-300 Hz covers adult speech
    seg = ac[:, lo:hi]
    peak_idx = seg.argmax(axis=1)
    peak_val = seg[np.arange(seg.shape[0]), peak_idx]
    ok = peak_val > 0.40
    coverage = float(ok.mean())
    if ok.sum() < 15:
        return 0.0, coverage

    f0 = SAMPLE_RATE / (peak_idx[ok] + lo)
    st = 12 * np.log2(f0 / np.median(f0))
    st = st[np.abs(st) <= 12]  # drop octave errors
    return (float(np.std(st)) if st.size > 10 else 0.0), coverage


def extract_audio_features(y: np.ndarray) -> AudioFeatures:
    y = np.asarray(y, dtype=np.float32)
    duration = len(y) / SAMPLE_RATE
    empty = AudioFeatures(duration, 0, 0, 0, 0, 0, 0, 0, 0, 0, -100, 0, -100, 0, 0, False)
    if len(y) < FRAME * 4:
        return empty

    fr = _frames(y)
    rms = np.sqrt(np.mean(fr.astype(np.float64) ** 2, axis=1))
    db = 20 * np.log10(rms + EPS)

    noise_floor = float(np.percentile(db, 8))
    peak_db = float(np.percentile(db, 95))
    # adaptive threshold: above noise floor, but never deep inside the signal's own range
    thr = max(noise_floor + 9.0, min(peak_db - 22.0, noise_floor + 25.0), -55.0)
    voiced = _smooth_vad(db > thr)

    if voiced.sum() < 20 or (peak_db - noise_floor) < 8:  # < 0.2 s of speech or no contrast
        empty.noise_floor_dbfs = noise_floor
        return empty

    speaking = voiced.sum() * HOP / SAMPLE_RATE
    first, last = int(np.argmax(voiced)), int(len(voiced) - np.argmax(voiced[::-1]))
    span = max((last - first) * HOP / SAMPLE_RATE, speaking)

    gaps = [(e - s) * HOP / SAMPLE_RATE for s, e, v in _runs(voiced[first:last]) if not v]
    pauses = [g for g in gaps if g >= PAUSE_MIN_S]
    long_pauses = [g for g in pauses if g >= LONG_PAUSE_S]

    speech_db = db[voiced]
    loud = float(np.mean(speech_db))
    vol_range = float(np.percentile(speech_db, 90) - np.percentile(speech_db, 10))
    pitch_std, coverage = _pitch_semitone_std(y, voiced)

    return AudioFeatures(
        duration_s=duration,
        speaking_time_s=float(speaking),
        speech_span_s=float(span),
        voiced_ratio=float(min(1.0, speaking / span)) if span > 0 else 0.0,
        pause_count=len(pauses),
        long_pause_count=len(long_pauses),
        longest_pause_s=float(max(pauses)) if pauses else 0.0,
        avg_pause_s=float(np.mean(pauses)) if pauses else 0.0,
        pitch_std_st=pitch_std,
        pitch_coverage=coverage,
        loudness_dbfs=loud,
        volume_range_db=vol_range,
        noise_floor_dbfs=noise_floor,
        snr_db=float(loud - noise_floor),
        clipping_ratio=float(np.mean(np.abs(y) > 0.99)),
        has_speech=bool(speaking >= 1.0),
    )


def has_speech_energy(y: np.ndarray) -> bool:
    """Cheap pre-check before running the STT model: is there a voice-like level
    contrast, or only steady background noise? Whisper hallucinates on noise."""
    if len(y) < FRAME * 4:
        return False
    db = 20 * np.log10(np.sqrt(np.mean(_frames(np.asarray(y, np.float32)).astype(np.float64) ** 2, axis=1)) + EPS)
    return bool(np.percentile(db, 95) > -52 and (np.percentile(db, 95) - np.percentile(db, 8)) >= 10)
