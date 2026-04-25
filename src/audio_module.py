import os
import wave
import json
import time
import re

import numpy as np
import soundfile as sf
import librosa
import sounddevice as sd
import soundfile as sf

from vosk import Model, KaldiRecognizer


# =====================================================
# PATH SETUP
# =====================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AUDIO_PATH = os.path.join(BASE_DIR, "data", "audio", "interview.wav")
MODEL_PATH = os.path.join(BASE_DIR, "models", "vosk-model-small-en-us-0.15")

os.makedirs(os.path.dirname(AUDIO_PATH), exist_ok=True)

FILLER_WORDS = ["uh", "um", "like", "you know", "actually", "basically", "so"]


# =====================================================
# LOAD MODEL ONLY ONCE
# =====================================================

print("Loading Vosk model once...")
model = Model(MODEL_PATH)


# =====================================================
# RECORD AUDIO (MEMORY SAFE)
# =====================================================

def record_audio(duration=10):

    RATE = 16000

    print("\n🎙 Recording audio... Speak clearly")

    audio_data = sd.rec(
        int(duration * RATE),
        samplerate=RATE,
        channels=1,
        dtype="int16"
    )

    sd.wait()

    sf.write(AUDIO_PATH, audio_data, RATE)

    print("✅ Audio saved:", AUDIO_PATH)


# =====================================================
# SPEECH RECOGNITION
# =====================================================

def speech_to_text():

    print("Starting speech recognition...")

    wf = wave.open(AUDIO_PATH, "rb")

    recognizer = KaldiRecognizer(model, wf.getframerate())

    transcript = ""

    while True:

        data = wf.readframes(2000)

        if len(data) == 0:
            break

        if recognizer.AcceptWaveform(data):

            result = json.loads(recognizer.Result())
            transcript += result.get("text", "") + " "

    final = json.loads(recognizer.FinalResult())
    transcript += final.get("text", "")

    wf.close()

    return transcript.strip()


# =====================================================
# FILLER COUNT
# =====================================================

def count_fillers(text):

    text = text.lower()

    count = 0

    for word in FILLER_WORDS:
        count += len(re.findall(rf"\b{re.escape(word)}\b", text))

    return count


# =====================================================
# AUDIO ANALYSIS
# =====================================================

def run_audio_analysis(duration=25):

    # 1️⃣ Record
    record_audio(duration)

    # 2️⃣ Speech recognition
    text = speech_to_text()

    print("\n📝 ===== TRANSCRIPT =====")
    print(text)

    # 3️⃣ Load audio
    y, sr_rate = sf.read(AUDIO_PATH)

    if len(y.shape) > 1:
        y = y.mean(axis=1)

    duration = len(y) / sr_rate

    # 4️⃣ Word metrics
    word_count = len(text.split())

    if duration > 0:
        wpm = word_count / (duration / 60)
    else:
        wpm = 0

    filler_count = count_fillers(text)

    # 5️⃣ Energy
    energy = float(np.mean(np.square(y)))

    # 6️⃣ Pitch
    try:

        f0 = librosa.yin(y.astype(float), fmin=80, fmax=300, sr=sr_rate)
        f0 = f0[~np.isnan(f0)]

        avg_pitch = np.mean(f0) if len(f0) > 0 else 0
        pitch_variation = np.std(f0) if len(f0) > 0 else 0

    except:

        avg_pitch = 0
        pitch_variation = 0

    # =====================================================
    # CONFIDENCE SCORE
    # =====================================================

    confidence = 100

    if word_count == 0:
        confidence = 0

    if filler_count > 3:
        confidence -= 10

    if wpm < 100 or wpm > 170:
        confidence -= 10

    if energy < 0.0001:
        confidence -= 10

    confidence = max(0, min(100, int(confidence)))

    # =====================================================
    # METRICS
    # =====================================================

    metrics = {

        "word_count": word_count,
        "wpm": round(wpm, 2),
        "filler_count": filler_count,
        "energy": round(energy, 6),
        "avg_pitch": round(avg_pitch, 2),
        "pitch_variation": round(pitch_variation, 2),
        "duration": round(duration, 2)

    }

    print("\n📊 ===== AUDIO METRICS =====")

    for k, v in metrics.items():
        print(f"{k}: {v}")

    print("\n🎯 Audio Confidence Score:", confidence)

    return confidence, metrics, text

if __name__ == "__main__":

    print("\nRunning standalone audio test...\n")

    score, metrics, text = run_audio_analysis(10)

    print("\nFinal Transcript:", text)
    print("\nScore:", score)
    print("\nMetrics:", metrics)


