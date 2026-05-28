# AI Interview Analyzer

> A multimodal AI system that evaluates mock interview answers in real time across **speech**, **facial expression**, and **language** dimensions — and gives you a weighted composite score with specific, actionable feedback.

<p align="center">
  <img src="docs/screenshots/01-landing.png" alt="AI Interview Analyzer — landing screen" width="100%" />
</p>

<p align="center">
  <a href="#-features">Features</a> ·
  <a href="#-tech-stack">Tech Stack</a> ·
  <a href="#-getting-started">Getting Started</a> ·
  <a href="#-how-it-works">How It Works</a> ·
  <a href="#-project-structure">Project Structure</a> ·
  <a href="#-api-reference">API</a>
</p>

---

## ✨ Features

- **🔊 Audio analysis** — Offline speech-to-text via Vosk (Indian English model), pace (WPM), filler-word density, pitch variation, silence ratio, energy
- **📷 Expression analysis** — Real-time facial landmark tracking (OpenCV + MediaPipe) for smile detection, eye contact, emotion stability, blink rate, and head movement
- **🧠 Hybrid NLP** — Local metrics (filler count, keyword matches, sentiment, clarity) combined with Mistral LLM for semantic scoring and feedback
- **⚡ Parallel processing** — Audio and expression modules run in parallel threads; NLP runs after transcript is ready
- **📊 Detailed report** — Per-module breakdown, improvement areas, actionable tips, and full transcript saved as JSON
- **🎨 Editorial UI** — Custom dark interface with monospace data typography — no template look

---

## 📸 Screenshots

### Setup
Pick a topic, choose duration, and start the session.

<p align="center">
  <img src="docs/screenshots/01-landing.png" alt="Setup screen" width="100%" />
</p>

### Live recording
Audio, expression, and NLP modules execute in parallel while you speak.

<p align="center">
  <img src="docs/screenshots/02-live.png" alt="Live recording screen" width="100%" />
</p>

### Results — overall
Composite score, AI-generated feedback, and per-module breakdown.

<p align="center">
  <img src="docs/screenshots/03-results-top.png" alt="Results — overall score" width="100%" />
</p>

### Results — improvements
Where to focus next and which fixes give the fastest gains.

<p align="center">
  <img src="docs/screenshots/04-results-scores.png" alt="Results — improvements and tips" width="100%" />
</p>

### Results — metrics & transcript
Raw module metrics across audio, expression, and NLP.

<p align="center">
  <img src="docs/screenshots/05-results-metrics.png" alt="Results — metrics and transcript" width="100%" />
</p>

---

## 🛠 Tech Stack

### Backend (Python)
| Layer | Tech | Why |
|---|---|---|
| API | **FastAPI** | Async, type-safe, auto-generated docs |
| Server | **Uvicorn** | ASGI server with hot reload |
| Concurrency | **Python threading + BackgroundTasks** | Parallel module execution |
| Speech-to-text | **Vosk (en-in-0.5)** | Offline, ~1 GB, optimized for Indian English |
| Audio features | **librosa, soundfile, sounddevice** | WPM, pitch, energy, silence detection |
| Face analysis | **OpenCV + MediaPipe** | Facial landmarks, gaze, emotion stability |
| LLM | **Mistral AI** | Semantic scoring and feedback |
| Config | **python-dotenv** | API key management |

### Frontend
| Layer | Tech |
|---|---|
| Framework | **React 18** |
| Build tool | **Vite** |
| Styling | **Plain CSS** (custom design system, no UI kit) |
| Fonts | **Instrument Serif** + **Inter Tight** + **JetBrains Mono** (via Google Fonts) |

### Architecture
- Decoupled frontend (`localhost:5173`) ↔ backend (`localhost:8000`) with CORS-enabled REST API
- Session-based polling (1s interval) for live progress updates
- Background workers via FastAPI `BackgroundTasks` — non-blocking
- JSON-based session reports persisted to `/reports/<session_id>.json`

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** and **npm**
- A working webcam and microphone
- ~1 GB free disk space (for Vosk model)
- Optional: **Mistral API key** (the app falls back to local-only scoring without it)

### 1. Clone the repository

```bash
git clone https://github.com/Abhenav-Jain/AI_Interview_Analyzer.git
cd AI_Interview_Analyzer
```

### 2. Download the Vosk Indian English model

The speech-to-text model is too large to bundle in the repo. Download and extract it manually:

```powershell
# Windows PowerShell
mkdir models -Force
Invoke-WebRequest -Uri "https://alphacephei.com/vosk/models/vosk-model-en-in-0.5.zip" -OutFile "models/vosk-model.zip"
Expand-Archive -Path "models/vosk-model.zip" -DestinationPath "models/" -Force
Remove-Item "models/vosk-model.zip"
```

```bash
# macOS / Linux
mkdir -p models
curl -L https://alphacephei.com/vosk/models/vosk-model-en-in-0.5.zip -o models/vosk-model.zip
unzip models/vosk-model.zip -d models/
rm models/vosk-model.zip
```

Verify: `models/vosk-model-en-in-0.5/` should now exist with subfolders `am/`, `conf/`, `graph/`, etc.

### 3. Backend setup

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

**Set up your Mistral API key** (optional but recommended). Create a `.env` file inside `backend/`:

```env
MISTRAL_API_KEY=your_api_key_here
```

Get a free key from [console.mistral.ai](https://console.mistral.ai/).

**Run the backend:**

```bash
python main_api.py
```

The API starts at **http://localhost:8000**. Verify with:
```
{"message": "AI Interview Analyzer API running 🚀"}
```

Swagger docs available at **http://localhost:8000/docs**.

### 4. Frontend setup

Open a **new terminal**:

```bash
cd frontend/frontend
npm install
npm run dev
```

Visit **http://localhost:5173** — the app should load with both backend and frontend connected.

---

## 🧠 How It Works

```
┌─────────────────────────┐
│  User clicks "Start"    │
└────────────┬────────────┘
             │  POST /session/start
             ▼
┌─────────────────────────────────────────────┐
│  FastAPI creates session, returns UUID      │
│  Spawns background worker thread             │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│  Two parallel threads launched              │
├──────────────────────┬──────────────────────┤
│  🔊 Audio thread     │  📷 Expression thread│
│  • Mic capture       │  • Webcam capture    │
│  • Vosk transcribe   │  • MediaPipe analyze │
│  • librosa features  │  • Per-frame metrics │
│  • Score (0-100)     │  • Score (0-100)     │
└──────────────────────┴──────────────────────┘
             │  Both threads join
             ▼
┌─────────────────────────┐
│  🧠 NLP analysis        │
│  • Local metrics        │
│    (regex, sentiment,   │
│     clarity heuristics) │
│  • Mistral API for      │
│    semantic score +     │
│    feedback             │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Weighted composite score                │
│  final = 0.35·audio + 0.35·expression    │
│        + 0.30·nlp                        │
└────────────┬─────────────────────────────┘
             │
             ▼
┌─────────────────────────┐
│  Session saved to       │
│  /reports/<uuid>.json   │
│  Frontend polls until   │
│  status: "done"         │
└─────────────────────────┘
```

**Design decisions worth noting:**

- **Audio & expression in parallel** — both capture real-time data for the full session duration. Running them sequentially would double the wait time.
- **NLP runs after audio** — it depends on the transcript, so it's a sequential dependency.
- **Hybrid NLP scoring** — local rule-based metrics are deterministic, free, and fast; the LLM is reserved for things rules can't measure (semantic depth, contextual quality).
- **Polling over WebSocket** — simpler implementation for 1s update frequency. WebSocket would be a clean upgrade for finer-grained live updates.

---

## 📁 Project Structure

```
AI_Interview_Analyzer/
├── backend/
│   ├── main_api.py           # FastAPI app — routes, session lifecycle
│   ├── requirements.txt
│   └── venv/                 # virtual env (gitignored)
├── src/                      # Analysis modules
│   ├── audio_module.py       # Mic recording + Vosk STT + librosa scoring
│   ├── expression_module.py  # OpenCV + MediaPipe face analysis
│   ├── nlp_analysis.py       # Local metrics + Mistral integration
│   └── main.py               # Standalone CLI runner (no API)
├── frontend/
│   └── frontend/             # Vite + React app
│       ├── src/
│       │   ├── App.jsx       # Main UI — setup, live, results states
│       │   ├── App.css       # Design system + component styles
│       │   ├── index.css     # Global resets, font loading
│       │   └── main.jsx
│       ├── package.json
│       └── vite.config.js
├── models/
│   └── vosk-model-en-in-0.5/ # Speech recognition model (downloaded separately)
├── data/
│   └── audio/                # Recorded audio (interview.wav) — gitignored
├── reports/                  # Saved session reports as JSON
├── docs/
│   └── screenshots/          # README images
├── .env                      # API keys (gitignored)
├── .gitignore
└── README.md
```

---

## 🔌 API Reference

Full interactive docs available at **http://localhost:8000/docs** (Swagger UI).

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Health check |
| `/health` | GET | Status + active session count |
| `/session/start` | POST | Start a new interview session |
| `/session/{id}` | GET | Poll session status / fetch results |
| `/session/{id}` | DELETE | Remove a session and its report |
| `/sessions` | GET | List all completed sessions |

### Example: start a session

```bash
curl -X POST http://localhost:8000/session/start \
  -H "Content-Type: application/json" \
  -d '{"duration": 25, "topic": "Tell me about yourself"}'
```

Response:
```json
{ "session_id": "a1b2c3d4-..." }
```

### Example: poll status

```bash
curl http://localhost:8000/session/a1b2c3d4-...
```

Response while running:
```json
{
  "session_id": "a1b2c3d4-...",
  "status": "running",
  "progress": 45
}
```

Response when done:
```json
{
  "session_id": "a1b2c3d4-...",
  "status": "done",
  "progress": 100,
  "final_score": 72,
  "audio_score": 78,
  "expression_score": 65,
  "nlp_score": 74,
  "audio_metrics": { "wpm": 142.3, "filler_count": 3, "...": "..." },
  "expression_metrics": { "eye_contact": 0.99, "avg_smile": 0.4, "...": "..." },
  "nlp_metrics": { "Filler Words": 3, "Sentiment Score": 65, "...": "..." },
  "transcript": "I worked on a project where I...",
  "feedback": "Strong answer with clear structure. Reduce filler words..."
}
```

---

## ⚙️ Configuration

Composite score weights live in `backend/main_api.py`:

```python
W_AUDIO      = 0.35   # 35% — voice delivery quality
W_EXPRESSION = 0.35   # 35% — non-verbal presence
W_NLP        = 0.30   # 30% — content quality
DURATION     = 25     # default seconds per session
```

Adjust to bias scoring toward whichever signal matters most for your use case. Currently hand-tuned — a learnable weighting trained on a labeled interview dataset is a planned improvement.

---

## 🗺 Roadmap

- [ ] Replace polling with WebSocket for lower-latency live updates
- [ ] Browser-side audio/video recording (currently backend uses local mic/camera)
- [ ] Per-question session mode (multi-question interviews)
- [ ] Role-specific question banks (frontend, PM, ML, consulting, etc.)
- [ ] Learnable weights from a labeled dataset instead of hand-tuned
- [ ] Persistent user profiles + progress tracking over time
- [ ] Side-by-side answer replay with module-level overlays
- [ ] Docker containerization for easier deployment
- [ ] Unit + integration tests (pytest + Jest)

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

```bash
git checkout -b feature/your-feature
# make changes
git commit -m "feat: add your feature"
git push origin feature/your-feature
```

---

## 📄 License

MIT © [Abhenav Jain](https://github.com/Abhenav-Jain)

See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- **[Vosk](https://alphacephei.com/vosk/)** — offline speech recognition
- **[MediaPipe](https://google.github.io/mediapipe/)** — facial landmark detection
- **[Mistral AI](https://mistral.ai/)** — LLM-powered semantic feedback
- **[FastAPI](https://fastapi.tiangolo.com/)** & **[React](https://react.dev/)** — the backbone
- **[librosa](https://librosa.org/)** — audio feature extraction
