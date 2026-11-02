# v1 → v2: what was wrong and what changed

Findings come from reading the v1 code and the 29 saved reports in `reports/`.

| # | v1 weakness (evidence) | v2 fix |
|---|---|---|
| 1 | `sounddevice` / `cv2.VideoCapture(0)` ran on the **server**: every deployed user would use the server's mic/camera. | Capture in the browser (`getUserMedia`, AudioWorklet → 16 kHz PCM over WebSocket). Video never leaves the device. |
| 2 | Vosk *small US* model (README promised `en-in`); a saved transcript read "derby when my name is up you know extent…". 18/29 reports had empty NLP metrics, 8 scored 0. Failure to load the model was silent. | `faster-whisper` (configurable size), disfluency-preserving prompt, silence/noise gating against hallucination, confidence reported, visible `/api/ready` + clear UI errors. |
| 3 | Everything ran *after* recording, sequentially. | Rolling transcription during speech, audio DSP in parallel, async LLM with cache. |
| 4 | Eye contact = 1.0 in 17/26 reports (iris-ratio window far too wide, no head pose). Blinks 0–91/min (fixed EAR threshold, no debounce). "Smile" was mouth width. | Per-user calibration, head pose + gaze, blendshape-based blinks with hysteresis and a reliability check, real smile blendshape. DeepFace/TensorFlow removed. |
| 5 | Scores had cliffs (110 wpm = 25 pts, 109 = 15), counted wall-clock for pace, rewarded buzzwords ("led", "built"), counted "so/like/right" as fillers, and kept two different filler lists. | Smooth band functions, pace on speaking time, one filler detector that needs punctuation evidence for ambiguous words, no buzzword reward. |
| 6 | LLM prompt said "score generously", parsed JSON by slicing braces, no timeout/retry. | Rubric with anchors, code computes the score, pydantic-validated JSON, retries + backoff, circuit breaker, cache, prompt-injection guard, length caps. |
| 7 | Missing camera/LLM counted as 0; silence produced a fake score. | Modules are excluded and weights re-normalised; silence → "no speech"; every report has a confidence level with reasons. |
| 8 | In-memory sessions + loose JSON files; `GET /sessions` could list everyone's reports; `allow_origins=["*"]` with credentials; one global `interview.wav` (parallel sessions overwrote each other). | SQLite, per-session secret token, no listing endpoint, strict CORS + WebSocket origin check, rate limit, concurrency cap, retention, delete endpoint, audio never persisted. |
| 9 | `requirements.txt` listed 2 packages; no Docker, tests or CI; `app.py` and `utils/` empty; hard-coded `localhost:8000`; 1 GB of models and personal reports committed; README screenshot links broken. | Pinned requirements, Dockerfile + compose, 30 backend tests, CI, same-origin API, `.gitignore`, history-purge guide, rewritten README. |
| 10 | No way to see progress. | Local history + trend chart, quick wins ranked by points gained, filler highlighting, JSON/PDF export, erase-my-data button. |

## Not verified in the build environment

The sandbox had no camera, no browser and no access to model hosts, so these paths were reviewed but **not executed end-to-end**: the real Whisper transcription, the MediaPipe face tracker in a live browser, and the Docker build. Everything else (DSP, scoring, LLM client, streaming STT logic with a fake engine, the full WebSocket protocol on a real uvicorn server, frontend lint + production build, AudioWorklet resampling) was run and passes.
