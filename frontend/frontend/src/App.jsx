import { useState, useEffect, useRef } from "react";

const API = "http://localhost:8000";

const scoreColor = (s) =>
  s >= 85 ? "#22c55e" : s >= 70 ? "#3b82f6" : s >= 55 ? "#f59e0b" : "#ef4444";

const scoreLabel = (s) =>
  s >= 85 ? "Outstanding" : s >= 70 ? "Strong" : s >= 55 ? "Decent" : "Needs Work";

// ─────────────────────────────────────────────
// Topic Selector (Search + Manual + Suggestions)
// ─────────────────────────────────────────────
function TopicSelector({ topic, setTopic }) {
  const suggestions = [
    "Tell me about yourself",
    "Explain a challenging project",
    "Why should we hire you?",
    "Describe leadership experience",
    "Explain system design of Netflix",
    "How would you scale a backend system?",
  ];

  const [filtered, setFiltered] = useState([]);

  useEffect(() => {
    if (!topic) return setFiltered([]);

    const f = suggestions.filter((t) =>
      t.toLowerCase().includes(topic.toLowerCase())
    );
    setFiltered(f);
  }, [topic]);

  return (
    <div style={{ position: "relative" }}>
      <input
        value={topic}
        onChange={(e) => setTopic(e.target.value)}
        placeholder="Type or search topic..."
        style={styles.input}
      />

      {filtered.length > 0 && (
        <div style={styles.dropdown}>
          {filtered.map((t, i) => (
            <div
              key={i}
              style={styles.dropdownItem}
              onClick={() => setTopic(t)}
            >
              {t}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// Live Interview UI
// ─────────────────────────────────────────────
function LiveInterview({ duration }) {
  const [time, setTime] = useState(duration);

  useEffect(() => {
    const interval = setInterval(() => {
      setTime((t) => (t > 0 ? t - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={styles.liveCard}>
      <div style={styles.pulse}></div>
      <h2>🎙 Interview in Progress</h2>
      <div style={styles.timer}>{time}s</div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Score Card
// ─────────────────────────────────────────────
function ScoreCard({ label, value }) {
  return (
    <div style={styles.scoreCard}>
      <div style={{ fontSize: 13, color: "#94a3b8" }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

// ─────────────────────────────────────────────
// MAIN APP
// ─────────────────────────────────────────────
export default function App() {
  const [session, setSession] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [polling, setPolling] = useState(false);
  const [duration, setDuration] = useState("25");
  const [topic, setTopic] = useState("");

  const pollRef = useRef(null);

  const isRunning = session?.status === "running";
  const isDone = session?.status === "done";

  useEffect(() => {
    if (!polling || !sessionId) return;

    pollRef.current = setInterval(async () => {
      const r = await fetch(`${API}/session/${sessionId}`);
      const d = await r.json();
      setSession(d);

      if (d.status === "done") {
        clearInterval(pollRef.current);
        setPolling(false);
      }
    }, 800);

    return () => clearInterval(pollRef.current);
  }, [polling, sessionId]);

  const startSession = async () => {
    const r = await fetch(`${API}/session/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        duration: parseInt(duration),
        topic: topic || "General Interview",
      }),
    });

    const d = await r.json();

    setSessionId(d.session_id);
    setSession({ status: "running" });
    setPolling(true);
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>AI Interview Analyzer</h1>
        <p style={styles.subtitle}>Practice interviews with AI feedback</p>

        {!isRunning && !isDone && (
          <>
            <div style={styles.field}>
              <label style={styles.label}>Interview Topic</label>
              <TopicSelector topic={topic} setTopic={setTopic} />
            </div>

            <div style={styles.field}>
              <label style={styles.label}>Duration (seconds)</label>
              <input
                type="number"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                style={styles.input}
              />
            </div>

            <button style={styles.button} onClick={startSession}>
              🚀 Start Interview
            </button>
          </>
        )}

        {isRunning && <LiveInterview duration={parseInt(duration)} />}

        {isDone && (
          <div style={styles.results}>
            <h2 style={{ color: scoreColor(session.final_score) }}>
              {session.final_score}/100
            </h2>
            <p>{scoreLabel(session.final_score)}</p>

            <div style={styles.feedback}>
              🤖 {session.nlp_feedback || session.feedback}
            </div>

            <div style={styles.scoreGrid}>
              <ScoreCard label="Audio" value={session.audio_score} />
              <ScoreCard label="Expression" value={session.expression_score} />
              <ScoreCard label="NLP" value={session.nlp_score} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// STYLES
// ─────────────────────────────────────────────
const styles = {
  container: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "linear-gradient(135deg,#020617,#0f172a)",
    fontFamily: "Inter, sans-serif",
  },

  card: {
    width: "100%",
    maxWidth: 600,
    padding: 30,
    borderRadius: 20,
    background: "rgba(255,255,255,0.05)",
    backdropFilter: "blur(20px)",
    boxShadow: "0 20px 80px rgba(0,0,0,0.5)",
    color: "#fff",
  },

  title: {
    fontSize: 32,
    fontWeight: 800,
    textAlign: "center",
  },

  subtitle: {
    textAlign: "center",
    color: "#94a3b8",
    marginBottom: 30,
  },

  field: {
    marginBottom: 20,
  },

  label: {
    fontSize: 13,
    marginBottom: 6,
    display: "block",
    color: "#94a3b8",
  },

  input: {
    width: "100%",
    padding: 14,
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,0.1)",
    background: "rgba(255,255,255,0.05)",
    color: "#fff",
  },

  dropdown: {
    position: "absolute",
    width: "100%",
    background: "#020617",
    borderRadius: 10,
    marginTop: 6,
    overflow: "hidden",
  },

  dropdownItem: {
    padding: 10,
    cursor: "pointer",
  },

  button: {
    width: "100%",
    padding: 14,
    borderRadius: 12,
    border: "none",
    background: "linear-gradient(90deg,#6366f1,#3b82f6)",
    color: "#fff",
    fontWeight: 700,
    cursor: "pointer",
  },

  liveCard: {
    textAlign: "center",
    padding: 30,
  },

  timer: {
    fontSize: 40,
    fontWeight: 800,
  },

  pulse: {
    width: 20,
    height: 20,
    background: "red",
    borderRadius: "50%",
    margin: "0 auto 10px",
    animation: "pulse 1s infinite",
  },

  results: {
    textAlign: "center",
  },

  feedback: {
    marginTop: 10,
    background: "rgba(255,255,255,0.05)",
    padding: 12,
    borderRadius: 10,
  },

  scoreGrid: {
    display: "flex",
    justifyContent: "space-between",
    marginTop: 20,
  },

  scoreCard: {
    flex: 1,
    margin: 5,
    padding: 15,
    background: "rgba(255,255,255,0.05)",
    borderRadius: 10,
  },
};
