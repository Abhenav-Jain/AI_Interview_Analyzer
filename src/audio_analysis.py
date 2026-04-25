import speech_recognition as sr
import soundfile as sf
import librosa
import numpy as np
import re
import os
import pyaudio
import wave
import threading
import time

# ================= CONFIG =================
AUDIO_PATH = "../data/audio/interview.wav"
RECORD_SECONDS = 60
os.makedirs("../data/audio", exist_ok=True)

# ================= RECORD AUDIO (FIXED) =================
def record_audio(duration=RECORD_SECONDS):

    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK = 1024

    audio = pyaudio.PyAudio()
    frames = []

    stream = audio.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

    print("\n🎙 Recording started...")
    print("Press ENTER to stop early.\n")

    stop_flag = {"stop": False}

    def wait_for_enter():
        input()
        stop_flag["stop"] = True

    threading.Thread(target=wait_for_enter).start()

    start_time = time.time()

    while time.time() - start_time < duration:
        if stop_flag["stop"]:
            break
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

    print("🛑 Recording stopped")

    stream.stop_stream()
    stream.close()
    audio.terminate()

    # Proper WAV save
    wf = wave.open(AUDIO_PATH, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

    print("✅ Audio saved properly")

record_audio()

# ================= SPEECH TO TEXT =================
recognizer = sr.Recognizer()
with sr.AudioFile(AUDIO_PATH) as source:
    audio_data = recognizer.record(source)

try:
    text = recognizer.recognize_google(audio_data)
    print("\n📝 Transcription:", text)
except:
    print("❌ Could not recognize speech")
    text = ""

# ================= LOAD AUDIO =================
y, sr_rate = sf.read(AUDIO_PATH)

if len(y.shape) > 1:
    y = np.mean(y, axis=1)

total_duration = librosa.get_duration(y=y, sr=sr_rate)

# ================= FILLER ANALYSIS =================
filler_words = ["uh", "um", "like", "you know", "actually", "basically", "so"]

def count_fillers(text):
    text = text.lower()
    return sum(len(re.findall(rf"\b{re.escape(f)}\b", text)) for f in filler_words)

filler_count = count_fillers(text)

# ================= SPEECH RATE =================
word_count = len(text.split())
minutes = total_duration / 60 if total_duration > 0 else 1
wpm = word_count / minutes

# ================= PAUSE ANALYSIS =================
intervals = librosa.effects.split(y, top_db=25)
speaking_duration = sum((end - start) for start, end in intervals) / sr_rate
pause_duration = total_duration - speaking_duration
pause_ratio = pause_duration / total_duration if total_duration > 0 else 0

# ================= ENERGY =================
rms_energy = np.mean(librosa.feature.rms(y=y))

# ================= PITCH =================
f0 = librosa.yin(y, fmin=80, fmax=300)
f0 = f0[~np.isnan(f0)]
avg_pitch = np.mean(f0) if len(f0) > 0 else 0
pitch_variation = np.std(f0) if len(f0) > 0 else 0

# ================= CONFIDENCE SCORING =================
confidence = 100

confidence -= filler_count * 5
confidence -= pause_ratio * 40

if wpm < 110 or wpm > 170:
    confidence -= 10

if rms_energy < 0.02:
    confidence -= 10

if pitch_variation < 15:
    confidence -= 10

# Penalize too short answers
if total_duration < 5:
    confidence -= 10

confidence = max(0, min(100, int(confidence)))

# ================= REPORT =================
print("\n📊 -------- AUDIO ANALYSIS REPORT --------")
print(f"🗣 Words Spoken: {word_count}")
print(f"⚡ Speech Rate: {int(wpm)} WPM")
print(f"🤐 Filler Words: {filler_count}")
print(f"⏸ Pause Duration: {round(pause_duration,2)} sec")
print(f"🔊 Energy Level: {round(rms_energy,4)}")
print(f"🎵 Avg Pitch: {round(avg_pitch,2)} Hz")
print(f"📈 Pitch Variation: {round(pitch_variation,2)}")
print(f"⏳ Duration: {round(total_duration,2)} sec")
print(f"\n🔥 CONFIDENCE SCORE: {confidence}/100")

# ================= FEEDBACK =================
print("\n💡 FEEDBACK:")

if filler_count > 3:
    print("• Reduce filler words.")

if pause_ratio > 0.3:
    print("• Reduce long pauses.")

if wpm < 110:
    print("• Speak slightly faster.")
elif wpm > 170:
    print("• Slow down your speech.")

if rms_energy < 0.02:
    print("• Speak with more energy.")

if pitch_variation < 15:
    print("• Add more vocal variation.")

if total_duration < 5:
    print("• Provide more detailed answers.")

if confidence >= 80:
    print("💪 Excellent Interview Presence!")
elif confidence >= 60:
    print("🙂 Good, but can improve.")
else:
    print("⚠ Needs serious improvement.")
