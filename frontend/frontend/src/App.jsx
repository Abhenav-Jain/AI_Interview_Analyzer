import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

const API = "http://localhost:8000";

const DEFAULT_TOPIC = "General Interview";

const topicSuggestions = [
  "Tell me about yourself",
  "Why should we hire you?",
  "Describe a challenging project",
  "Explain a leadership experience",
  "How would you scale a backend system?",
  "Explain system design of Netflix",
];

function scoreColor(score) {
  if (score >= 85) return "excellent";
  if (score >= 70) return "strong";
  if (score >= 55) return "average";
  return "weak";
}

function scoreLabel(score) {
  if (score >= 85) return "Outstanding";
  if (score >= 70) return "Strong";
  if (score >= 55) return "Decent";
  return "Needs Work";
}

function scoreMessage(score) {
  if (score >= 85) return "You are interview-ready with only minor refinements left.";
  if (score >= 70) return "Good base. A little more structure and polish can push you higher.";
  if (score >= 55) return "You have potential, but clarity and consistency need work.";
  return "The fundamentals need improvement before this becomes interview-ready.";
}

function normalizeMetricEntries(metrics) {
  if (!metrics || typeof metrics !== "object") return [];
  return Object.entries(metrics);
}

function extractImprovementAreas(session) {
  const areas = [];

  if ((session?.nlp_score ?? 0) < 60) {
    areas.push({
      title: "Answer structure",
      text: "Your response needs better flow, clearer sequencing, and more coherent sentence construction.",
    });
  }

  if ((session?.audio_score ?? 0) < 60) {
    areas.push({
      title: "Speech delivery",
      text: "Work on filler-word control, pace balance, and cleaner verbal delivery.",
    });
  }

  if ((session?.expression_score ?? 0) < 60) {
    areas.push({
      title: "Expression and presence",
      text: "Improve eye contact, confidence, facial engagement, and on-camera stability.",
    });
  }

  if (!areas.length) {
    areas.push({
      title: "Fine-tuning",
      text: "Your performance is solid overall. Focus on sharper examples and more concise responses.",
    });
  }

  return areas;
}

function buildTips(session) {
  const tips = [];

  if ((session?.nlp_score ?? 0) < 70) {
    tips.push("Use a simple beginning-middle-end structure before answering.");
    tips.push("Avoid rambling; keep each answer focused on one clear point.");
  }

  if ((session?.audio_score ?? 0) < 70) {
    tips.push("Reduce filler words by slowing down before key points.");
  }

  if ((session?.expression_score ?? 0) < 70) {
    tips.push("Maintain steady posture and consistent facial engagement while speaking.");
  }

  if (!tips.length) {
    tips.push("Practice with role-specific questions to sharpen your delivery further.");
  }

  return [...new Set(tips)].slice(0, 4);
}

function TopicSelector({ topic, setTopic }) {
  const [open, setOpen] = useState(false);

  const filtered = useMemo(() => {
    if (!topic.trim()) return topicSuggestions;
    return topicSuggestions.filter((item) =>
      item.toLowerCase().includes(topic.toLowerCase())
    );
  }, [topic]);

  return (
    <div className="topic-selector">
      <input
        className="app-input"
        value={topic}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={(e) => {
          setTopic(e.target.value);
          setOpen(true);
        }}
        placeholder="Type or pick an interview topic..."
      />
      {open && filtered.length > 0 && (
        <div className="topic-dropdown">
          {filtered.slice(0, 6).map((item) => (
            <button
              key={item}
              type="button"
              className="topic-option"
              onMouseDown={() => {
                setTopic(item);
                setOpen(false);
              }}
            >
              {item}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ScoreRing({ score }) {
  const angle = Math.max(0, Math.min(100, score || 0)) * 3.6;
  return (
    <div
      className={`score-ring ${scoreColor(score)}`}
      style={{
        background: `conic-gradient(var(--ring) ${angle}deg, rgba(255,255,255,0.06) ${angle}deg)`,
      }}
    >
      <div className="score-ring-inner">
        <div className="score-ring-value">{score ?? 0}</div>
        <div className="score-ring-total">/ 100</div>
      </div>
    </div>
  );
}

function ScoreCard({ title, value }) {
  return (
    <div className="score-card">
      <span>{title}</span>
      <strong>{value ?? 0}</strong>
    </div>
  );
}

function MetricList({ title, metrics }) {
  const items = normalizeMetricEntries(metrics);

  return (
    <div className="detail-card">
      <div className="detail-card-head">
        <h4>{title}</h4>
      </div>
      {items.length ? (
        <div className="metric-list">
          {items.map(([key, value]) => (
            <div key={key} className="metric-row">
              <span>{key}</span>
              <strong>{String(value)}</strong>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty-text">Detailed metrics were not available for this module.</p>
      )}
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [polling, setPolling] = useState(false);
  const [duration, setDuration] = useState("25");
  const [topic, setTopic] = useState("");
  const [error, setError] = useState("");
  const pollRef = useRef(null);

  const isRunning = session?.status === "running";
  const isDone = session?.status === "done";
  const progress = session?.progress ?? 0;

  useEffect(() => {
    if (!polling || !sessionId) return;

    pollRef.current = setInterval(async () => {
      try {
        const response = await fetch(`${API}/session/${sessionId}`);
        if (!response.ok) {
          throw new Error("Unable to fetch session status");
        }
        const data = await response.json();
        setSession(data);

        if (data.status === "done") {
          clearInterval(pollRef.current);
          setPolling(false);
        }

        if (data.error) {
          setError(data.error);
        }
      } catch (err) {
        clearInterval(pollRef.current);
        setPolling(false);
        setError(err.message || "Something went wrong while fetching session data.");
      }
    }, 1000);

    return () => clearInterval(pollRef.current);
  }, [polling, sessionId]);

  const startSession = async () => {
    setError("");
    setSession(null);

    try {
      const response = await fetch(`${API}/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          duration: parseInt(duration, 10),
          topic: topic.trim() || DEFAULT_TOPIC,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to start interview session");
      }

      const data = await response.json();
      setSessionId(data.session_id);
      setSession({
        status: "running",
        progress: 0,
        topic: topic.trim() || DEFAULT_TOPIC,
      });
      setPolling(true);
    } catch (err) {
      setError(err.message || "Unable to start the interview.");
    }
  };

  const resetApp = () => {
    setSession(null);
    setSessionId(null);
    setPolling(false);
    setError("");
    setTopic("");
    setDuration("25");
    if (pollRef.current) clearInterval(pollRef.current);
  };

  const improvementAreas = extractImprovementAreas(session);
  const tips = buildTips(session);

  return (
    <div className="app-shell">
      <main className="app-container">
        {/* ============ HERO ============ */}
        <section className="hero-card">
          <div className="hero-copy">
            <span className="eyebrow">/ AI-powered interview workspace</span>
            <h1>
              Practice the interview.{" "}
              <em style={{ color: "var(--primary)", fontStyle: "italic" }}>
                Read the room.
              </em>
            </h1>
            <p>
              An AI second opinion on every answer — your voice, your expressions,
              your words — scored in real time so you walk into the real thing already warmed up.
            </p>
          </div>

          <div className="hero-badge">
            <span>● Active topic</span>
            <strong>{topic.trim() || DEFAULT_TOPIC}</strong>
          </div>
        </section>

        {/* ============ SETUP ============ */}
        {!isRunning && !isDone && (
          <section className="setup-grid">
            <div className="panel panel-lg">
              <div className="panel-head">
                <h2>Interview setup</h2>
                <p>Pick your topic and session length, then start recording.</p>
              </div>

              <div className="form-stack">
                <div className="field-block">
                  <label className="field-label">/ Interview topic</label>
                  <TopicSelector topic={topic} setTopic={setTopic} />
                </div>

                <div className="field-block">
                  <label className="field-label">/ Duration</label>
                  <div className="duration-row">
                    {["15", "25", "35", "45"].map((item) => (
                      <button
                        key={item}
                        type="button"
                        className={`chip ${duration === item ? "active" : ""}`}
                        onClick={() => setDuration(item)}
                      >
                        {item}s
                      </button>
                    ))}
                  </div>
                </div>

                <button type="button" className="primary-btn" onClick={startSession}>
                  Start interview →
                </button>

                {error && <div className="error-box">{error}</div>}
              </div>
            </div>

            <div className="panel panel-lg">
              <div className="panel-head">
                <h2>What you'll get</h2>
                <p>Real interview-style analysis from three independent modules.</p>
              </div>

              <div className="feature-list">
                <div className="feature-card">
                  <div className="feature-icon">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
                      <rect x="7" y="3" width="6" height="10" rx="3" />
                      <path d="M4 10a6 6 0 0 0 12 0M10 16v3" strokeLinecap="round" />
                    </svg>
                  </div>
                  <div>
                    <strong>Audio analysis</strong>
                    <p>Speech pace, filler-word density, and fluency markers.</p>
                  </div>
                </div>

                <div className="feature-card">
                  <div className="feature-icon">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
                      <circle cx="10" cy="10" r="7" />
                      <circle cx="7.5" cy="8.5" r="0.8" fill="currentColor" />
                      <circle cx="12.5" cy="8.5" r="0.8" fill="currentColor" />
                      <path d="M7.5 12.5c1 1 4 1 5 0" strokeLinecap="round" />
                    </svg>
                  </div>
                  <div>
                    <strong>Expression analysis</strong>
                    <p>Confidence, on-camera presence, and eye-contact cues.</p>
                  </div>
                </div>

                <div className="feature-card">
                  <div className="feature-icon">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
                      <path d="M4 5h12M4 10h12M4 15h8" strokeLinecap="round" />
                      <circle cx="15" cy="15" r="1.5" fill="currentColor" />
                    </svg>
                  </div>
                  <div>
                    <strong>NLP analysis</strong>
                    <p>Structure, coherence, and semantic answer quality.</p>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ============ LIVE ============ */}
        {isRunning && (
          <section className="live-layout">
            <div className="panel live-panel">
              <div className="live-status">
                <div className="live-dot"></div>
                <span>Recording</span>
              </div>

              <h2>Reading your answer in real time</h2>
              <p className="muted">
                Speak naturally — audio, expression, and language quality are being processed simultaneously.
              </p>

              <div className="progress-block">
                <div className="progress-meta">
                  <span>/ Progress</span>
                  <strong>{progress}%</strong>
                </div>
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${progress}%` }} />
                </div>
              </div>

              <div className="live-grid">
                <div className="mini-card">
                  <span>Topic</span>
                  <strong>{session?.topic || topic || DEFAULT_TOPIC}</strong>
                </div>
                <div className="mini-card">
                  <span>Duration</span>
                  <strong>{duration}s</strong>
                </div>
                <div className="mini-card">
                  <span>Status</span>
                  <strong style={{ color: "var(--primary)" }}>Running</strong>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ============ RESULTS ============ */}
        {isDone && (
          <section className="results-layout">
            <div className="results-top">
              <div className="panel result-hero">
                <div className="result-main">
                  <ScoreRing score={session.final_score} />
                  <div className="result-copy">
                    <div className={`score-pill ${scoreColor(session.final_score)}`}>
                      {scoreLabel(session.final_score)}
                    </div>
                    <h2>Overall interview performance</h2>
                    <p>{scoreMessage(session.final_score)}</p>
                  </div>
                </div>

                <div className="feedback-box">
                  <span>/ AI feedback</span>
                  <p>{session?.nlp_feedback || session?.feedback || "Feedback not available."}</p>
                </div>
              </div>

              <div className="panel action-panel">
                <div className="panel-head">
                  <h3>Next attempt</h3>
                  <p>Use this review to iterate before trying again. Most improvement happens in run 2 and 3.</p>
                </div>

                <button className="primary-btn" type="button" onClick={resetApp}>
                  Run it back →
                </button>
              </div>
            </div>

            <div className="score-grid">
              <ScoreCard title="Audio" value={session.audio_score} />
              <ScoreCard title="Expression" value={session.expression_score} />
              <ScoreCard title="NLP" value={session.nlp_score} />
            </div>

            <div className="insight-grid">
              <div className="panel">
                <div className="panel-head">
                  <h3>Where to improve</h3>
                  <p>Focus on the lowest-scoring area first for fastest gains.</p>
                </div>

                <div className="improvement-list">
                  {improvementAreas.map((item) => (
                    <div key={item.title} className="improvement-card">
                      <strong>{item.title}</strong>
                      <p>{item.text}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h3>Actionable tips</h3>
                  <p>Easy fixes you can apply in your next answer.</p>
                </div>

                <ul className="tips-list">
                  {tips.map((tip) => (
                    <li key={tip}>{tip}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="details-grid">
              <MetricList title="Audio metrics" metrics={session.audio_metrics} />
              <MetricList title="Expression metrics" metrics={session.expression_metrics} />
              <MetricList title="NLP metrics" metrics={session.nlp_metrics} />
            </div>

            <div className="panel transcript-panel">
              <div className="panel-head">
                <h3>Transcript</h3>
                <p>What the system actually captured during your answer.</p>
              </div>

              <div className="transcript-box">
                {session?.transcript?.trim()
                  ? session.transcript
                  : "Transcript not available for this session."}
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
