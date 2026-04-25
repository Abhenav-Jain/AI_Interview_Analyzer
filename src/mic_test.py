import sounddevice as sd
import soundfile as sf
import numpy as np

RATE = 16000
DEVICE = 14

print("Recording using device:", DEVICE)

audio = sd.rec(
    int(5 * RATE),
    samplerate=RATE,
    channels=1,
    dtype="int16",
    device=DEVICE
)

sd.wait()

sf.write("test.wav", audio, RATE)

print("Saved test.wav")

print("Average amplitude:", np.mean(np.abs(audio)))