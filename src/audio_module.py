import os
import wave
import json
import time
import re

import numpy as np
import soundfile as sf
import librosa
import sounddevice as sd

from vosk import Model, KaldiRecognizer

# ── Path setup ───────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_PATH = os.path.join(BASE_DIR, "data", "audio", "interview.wav")
MODEL_PATH = os.path.join(BASE_DIR, "models", "vosk-model-en-in-0.5")   # ← Indian English model

os.makedirs(os.path.dirname(AUDIO_PATH), exist_ok=True)

FILLER_WORDS = ["uh", "um", "like", "you know", "actually", "basically", "so"]
CONFIDENT_WORDS = ["led", "built", "developed", "achieved", "implemented",
                   "designed", "managed", "created", "improved", "delivered"]

# ── Load model safely ─────────────────────────────────────────
print("Loading Vosk model...")
try:
    _model = Model(MODEL_PATH)
    print("✅ Vosk model loaded")
except Exception as e:
    print("❌ Vosk model load failed:", e)
    _model = None


# ── Record audio safely ───────────────────────────────────────
def record_audio(duration: int = 25):
    RATE = 16000
    try:
        print(f"\n🎙 Recording for {duration}s...")
        audio_data = sd.rec(int(duration * RATE), samplerate=RATE, channels=1, dtype="int16")
        sd.wait()
        sf.write(AUDIO_PATH, audio_data, RATE)
        print("✅ Audio saved")
    except Exception as e:
        print("❌ Recording error:", e)
        raise


# ── Speech-to-text ───────────────────────────────────────────
def speech_to_text():
    if _model is None:
        return ""

    try:
        wf = wave.open(AUDIO_PATH, "rb")
        recognizer = KaldiRecognizer(_model, wf.getframerate())

        transcript = ""

        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if recognizer.AcceptWaveform(data):
                transcript += json.loads(recognizer.Result()).get("text", "") + " "

        transcript += json.loads(recognizer.FinalResult()).get("text", "")
        wf.close()

        return transcript.strip()

    except Exception as e:
        print("❌ Speech error:", e)
        return ""


# ── Utility functions ─────────────────────────────────────────
def count_fillers(text):
    text = text.lower()
    return sum(len(re.findall(rf"\b{re.escape(w)}\b", text)) for w in FILLER_WORDS)


def count_confident_words(text):
    text = text.lower()
    return sum(len(re.findall(rf"\b{re.escape(w)}\b", text)) for w in CONFIDENT_WORDS)


def silence_ratio(y):
    rms = librosa.feature.rms(y=y)[0]
    return float(np.mean(rms < 0.01))


# ── MAIN FUNCTION ─────────────────────────────────────────────
def run_audio_analysis(duration: int = 25):

    record_audio(duration)
    transcript = speech_to_text()

    if not transcript:
        print("⚠ No speech detected")

    print(f"\n📝 Transcript: {transcript[:100]}...")

    y, sr = sf.read(AUDIO_PATH)
    if y.ndim > 1:
        y = y.mean(axis=1)

    # Convert int16 PCM to float32 for librosa
    if y.dtype == np.int16:
        y = y.astype(np.float32) / 32768.0

    actual_duration = len(y) / sr

    words = transcript.split()
    word_count = len(words)
    wpm = word_count / (actual_duration / 60) if actual_duration > 0 else 0

    filler_count = count_fillers(transcript)
    confident_count = count_confident_words(transcript)
    silence = silence_ratio(y)

    energy = float(np.mean(y ** 2))

    try:
        f0 = librosa.yin(y, fmin=80, fmax=300, sr=sr)
        f0_clean = f0[~np.isnan(f0)]
        pitch_var = float(np.std(f0_clean)) if len(f0_clean) else 0
    except Exception:
        pitch_var = 0

    # ── SCORING ───────────────────────────────────────────────
    score = 0

    # Speaking pace
    if 110 <= wpm <= 160:
        score += 25
    elif 90 <= wpm <= 180:
        score += 15
    else:
        score += 5

    # Energy
    if energy > 0.005:
        score += 20
    elif energy > 0.001:
        score += 10

    # Fillers
    score += max(0, 20 - filler_count * 3)

    # Pitch variation
    score += min(15, pitch_var / 3)

    # Silence
    score += max(0, 10 - silence * 20)

    # Confidence words
    score += min(10, confident_count * 2)

    if word_count == 0:
        score = 0

    score = int(max(0, min(100, score)))

    # ── Confidence score (NEW) ────────────────────────────────
    # Audio confidence = derived from overall delivery quality
    audio_confidence = int(min(100, max(0, score)))

    metrics = {
        "word_count":      word_count,
        "wpm":             round(wpm, 1),
        "filler_count":    filler_count,
        "confident_words": confident_count,
        "silence_ratio":   round(silence, 2),
        "energy":          round(energy, 6),
        "pitch_variation": round(pitch_var, 1),
        "duration":        round(actual_duration, 1),
        "confidence_score": audio_confidence,
    }

    print(f"\n🎯 Audio Score: {score}/100")

    return score, metrics, transcript