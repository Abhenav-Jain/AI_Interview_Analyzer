# Architecture notes

## Decisions

| Decision | Reason |
|---|---|
| Capture in the browser, not on the server | A server cannot open each user's mic/camera. Also keeps video on the device. |
| Face analysis with MediaPipe in the browser | Gives blink, smile and head-pose signals directly (blendshapes + transformation matrix), no TensorFlow/DeepFace on the server. |
| Calibration before recording | "Looking at the camera" depends on where the camera is. We compare against the user's own baseline instead of a fixed iris ratio. |
| faster-whisper, int8 on CPU | Much better accuracy on accented English than Vosk-small, no API cost, no data leaves the server. |
| Rolling transcription | Hides most of the STT latency inside the time the person is speaking. Cuts are made at the quietest 100 ms window so words are not split. |
| Numpy-only DSP | Removes librosa/numba (slow import, heavy install). Adaptive VAD threshold, pitch in semitones. |
| LLM only grades a rubric | Score is computed in code from validated sub-scores: reproducible, explainable, capped for short answers. |
| Treat transcript as untrusted | Fenced in tags + explicit instruction; a candidate cannot talk the grader into a higher score. |
| Graceful degradation | LLM down: circuit breaker + local score. Camera denied: module excluded and weights re-normalised. Socket drops after `end`: client polls REST for the result. |
| SQLite + token per session | Survives restarts, no global listing, same 404 for "missing" and "wrong token". |

## Message protocol (WebSocket)

Client → server: `{"type":"calibration","samples":[...]}`, `{"type":"start"}`, binary PCM16LE mono 16 kHz frames, `{"type":"face","samples":[{t,v,sm,bl,yw,pt,gx,gy}]}`, `{"type":"end"}`, `{"type":"ping"}`.

Server → client: `ready`, `partial {text}`, `stage {stage, progress}`, `result {data}`, `error {message}`, `pong`.

Limits: audio bytes are capped to `duration + grace`; face samples are validated (finite, bounded) and capped; sessions are single use.

## Extending

- New rubric criterion: add it to `RUBRIC` in `llm.py` (weight must keep the sum at 1.0) and to the prompt schema.
- New STT backend: implement `load()` / `transcribe()` from `stt.STTEngine` and select it in `main.build_engine`.
- New face metric: add it in `face.aggregate_face`, score it as a `Component` in `scoring.score_expression`.
