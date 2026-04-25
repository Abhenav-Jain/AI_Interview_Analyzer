import speech_recognition as sr

r = sr.Recognizer()

with sr.AudioFile("../data/audio/interview.wav") as source:
    audio = r.record(source)

try:
    text = r.recognize_google(audio)
    print("Transcript:", text)

except Exception as e:
    print("Error:", e)