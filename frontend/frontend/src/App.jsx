import { useState, useEffect, useRef, useCallback } from "react";

// ─── API base ─────────────────────────────────────────────────────────────────
const API = "http://localhost:8000";

// ─── Colour helpers ───────────────────────────────────────────────────────────
const scoreColor = (s) =>
  s >= 85 ? "#10B981" : s >= 70 ? "#3B82F6" : s >= 55 ? "#F59E0B" : "#EF4444";

const scoreLabel = (s) =>
  s >= 85 ? "Outstanding" : s >= 70 ? "Strong" : s >= 55 ? "Decent" : "Needs Work";

// ─── Animated number ──────────────────────────────────────────────────────────
function AnimNumber({ value, duration = 900 }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    const start = performance.now();
    const from = display;
    const tick = (now) => {
      const p = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      setDisplay(Math.round(from + (value - from) * ease));
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [value]);
  return <>{display}</>;
}

// ─── Radial gauge ─────────────────────────────────────────────────────────────
function Gauge({ score, label, size = 120 }) {
  const r = 44, cx = 60, cy = 60;
  const circ = 2 * Math.PI * r;
  const arc = circ * 0.75;
  const offset = arc - (arc * Math.min(score, 100)) / 100;
  const color = scoreColor(score);
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <svg width={size} height={size} viewBox="0 0 120 120">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#E5E7EB" strokeWidth="8"
          strokeDasharray={`${arc} ${circ}`} strokeLinecap="round"
          transform="rotate(135 60 60)" />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={`${arc - offset} ${circ}`} strokeLinecap="round"
          transform="rotate(135 60 60)"
          style={{ transition: "stroke-dasharray 1s cubic-bezier(.4,0,.2,1)" }} />
        <text x={cx} y={cy - 4} textAnchor="middle" fontSize="20" fontWeight="700"
          fontFamily="'DM Sans', sans-serif" fill={color}>
          <AnimNumber value={score} />
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" fontSize="10" fill="#6B7280"
          fontFamily="'DM Sans', sans-serif">/ 100</text>
      </svg>
      <span style={{ fontSize: 12, fontWeight: 600, color: "#374151", letterSpacing: "0.05em", textTransform: "uppercase" }}>
        {label}
      </span>
    </div>
  );
}

// ─── Bar metric row ───────────────────────────────────────────────────────────
function MetricBar({ label, value, max, unit = "", color = "#3B82F6" }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: "#6B7280", fontWeight: 500 }}>{label}</span>
        <span style={{ fontSize: 12, color: "#111827", fontWeight: 600 }}>
          {typeof value === "number" ? value.toLocaleString() : value}{unit}
        </span>
      </div>
      <div style={{ height: 6, background: "#F3F4F6", borderRadius: 99, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${pct}%`, background: color, borderRadius: 99,
          transition: "width 1s cubic-bezier(.4,0,.2,1)"
        }} />
      </div>
    </div>
  );
}

// ─── Card ─────────────────────────────────────────────────────────────────────
function Card({ title, accent = "#3B82F6", children, style = {} }) {
  return (
    <div style={{
      background: "#fff", borderRadius: 14, padding: "22px 24px",
      boxShadow: "0 1px 3px rgba(0,0,0,.08), 0 4px 16px rgba(0,0,0,.04)",
      borderTop: `3px solid ${accent}`, ...style
    }}>
      {title && (
        <h3 style={{ margin: "0 0 18px", fontSize: 13, fontWeight: 700,
          letterSpacing: "0.07em", textTransform: "uppercase", color: "#9CA3AF" }}>
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}

// ─── Section header ───────────────────────────────────────────────────────────
function SectionHeader({ step, title, subtitle }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 6 }}>
      <div style={{
        width: 32, height: 32, borderRadius: "50%", background: "#1D4ED8",
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "#fff", fontSize: 13, fontWeight: 700, flexShrink: 0
      }}>{step}</div>
      <div>
        <div style={{ fontSize: 16, fontWeight: 700, color: "#111827" }}>{title}</div>
        <div style={{ fontSize: 12, color: "#6B7280", marginTop: 1 }}>{subtitle}</div>
      </div>
    </div>
  );
}

// ─── Progress bar (session running) ──────────────────────────────────────────
function SessionProgress({ progress }) {
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ fontSize: 13, color: "#6B7280" }}>Analyzing…</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: "#1D4ED8" }}>{progress}%</span>
      </div>
      <div style={{ height: 8, background: "#EFF6FF", borderRadius: 99, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${progress}%`, borderRadius: 99,
          background: "linear-gradient(90deg,#3B82F6,#1D4ED8)",
          transition: "width .5s ease", boxShadow: "0 0 8px rgba(59,130,246,.4)"
        }} />
      </div>
    </div>
  );
}

// ─── History row ──────────────────────────────────────────────────────────────
function HistoryRow({ item, onSelect }) {
  const d = new Date(item.started_at);
  const time = isNaN(d) ? item.started_at : d.toLocaleString();
  const color = scoreColor(item.final_score);
  return (
    <div onClick={() => onSelect(item)} style={{
      display: "flex", alignItems: "center", gap: 14, padding: "12px 16px",
      borderRadius: 10, cursor: "pointer", transition: "background .15s",
      marginBottom: 6, border: "1px solid #F3F4F6"
    }}
      onMouseEnter={e => e.currentTarget.style.background = "#F9FAFB"}
      onMouseLeave={e => e.currentTarget.style.background = "transparent"}
    >
      <div style={{
        width: 42, height: 42, borderRadius: "50%", background: color + "18",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 15, fontWeight: 800, color, flexShrink: 0
      }}>{item.final_score}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#111827" }}>
          {scoreLabel(item.final_score)}
        </div>
        <div style={{ fontSize: 11, color: "#9CA3AF", marginTop: 2 }}>{time}</div>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        {[
          { l: "A", v: item.audio_score },
          { l: "E", v: item.expression_score },
          { l: "N", v: item.nlp_score },
        ].map(({ l, v }) => (
          <div key={l} style={{
            fontSize: 10, fontWeight: 700, color: scoreColor(v),
            background: scoreColor(v) + "18", borderRadius: 6, padding: "2px 6px"
          }}>
            {l} {v}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [view, setView]           = useState("dashboard"); // "dashboard" | "history"
  const [sessionId, setSessionId] = useState(null);
  const [session, setSession]     = useState(null);
  const [polling, setPolling]     = useState(false);
  const [history, setHistory]     = useState([]);
  const [selected, setSelected]   = useState(null);  // history detail
  const [duration, setDuration]   = useState("25");
  const [starting, setStarting]   = useState(false);
  const pollRef = useRef(null);

  // ── Derived state (FIX: these were missing, causing ReferenceError) ────────
  const isRunning = session?.status === "running";
  const isDone    = session?.status === "done";

  // ── Fetch history ────────────────────────────────────────────────────────
  const fetchHistory = useCallback(async () => {
    try {
      const r = await fetch(`${API}/sessions`);
      const d = await r.json();
      setHistory(d);
    } catch (_) {}
  }, []);

  useEffect(() => { fetchHistory(); }, []);

  // ── Poll session ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!polling || !sessionId) return;
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${API}/session/${sessionId}`);
        const d = await r.json();
        setSession(d);
        if (d.status === "done" || d.status === "error") {
          clearInterval(pollRef.current);
          setPolling(false);
          if (d.status === "done") fetchHistory();
        }
      } catch (_) {}
    }, 800);
    return () => clearInterval(pollRef.current);
  }, [polling, sessionId]);

  // ── Start session ─────────────────────────────────────────────────────────
  const startSession = async () => {
    const parsedDuration = parseInt(duration, 10);
    if (!parsedDuration || parsedDuration < 5 || parsedDuration > 120) {
      alert("Duration must be between 5 and 120 seconds");
      return;
    }

    setStarting(true);
    setSession(null);

    try {
      const r = await fetch(`${API}/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ duration: parsedDuration }),
      });

      const d = await r.json();
      setSessionId(d.session_id);
      setSession({ status: "running", progress: 0 });
      setPolling(true);

    } catch (e) {
      alert("Could not reach the API. Make sure FastAPI is running on port 8000.");
    }

    setStarting(false);
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Layout
  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div style={{
      minHeight: "100vh", background: "#F8FAFC",
      fontFamily: "'DM Sans', 'Segoe UI', sans-serif", color: "#111827"
    }}>
      {/* Google Font */}
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet" />

      {/* ── Top nav ── */}
      <header style={{
        background: "#fff", borderBottom: "1px solid #E5E7EB",
        padding: "0 32px", display: "flex", alignItems: "center",
        justifyContent: "space-between", height: 60, position: "sticky", top: 0, zIndex: 50
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, background: "#1D4ED8",
            display: "flex", alignItems: "center", justifyContent: "center"
          }}>
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
                stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span style={{ fontSize: 16, fontWeight: 800, color: "#111827", letterSpacing: "-0.02em" }}>
            Interview Analyzer
          </span>
        </div>
        <nav style={{ display: "flex", gap: 4 }}>
          {["dashboard", "history"].map(v => (
            <button key={v} onClick={() => { setView(v); setSelected(null); }} style={{
              padding: "6px 16px", borderRadius: 8, border: "none", cursor: "pointer",
              fontSize: 13, fontWeight: 600, transition: "all .15s",
              background: view === v ? "#EFF6FF" : "transparent",
              color: view === v ? "#1D4ED8" : "#6B7280"
            }}>
              {v.charAt(0).toUpperCase() + v.slice(1)}
            </button>
          ))}
        </nav>
      </header>

      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>

        {/* ════════════════════════════════════════════════════════════════
            DASHBOARD VIEW
        ════════════════════════════════════════════════════════════════ */}
        {view === "dashboard" && (
          <>
            {/* ── Hero row ── */}
            <div style={{ marginBottom: 28 }}>
              <h1 style={{ fontSize: 26, fontWeight: 800, color: "#111827",
                letterSpacing: "-0.03em", margin: "0 0 4px" }}>
                AI Interview Analyzer
              </h1>
              <p style={{ fontSize: 14, color: "#6B7280", margin: 0 }}>
                Real-time audio, expression & NLP scoring for interview performance
              </p>
            </div>

            {/* ── Controls ── */}
            <Card title="Start New Session" accent="#1D4ED8" style={{ marginBottom: 24 }}>
              <SectionHeader step="1" title="Configure & Record"
                subtitle="Set your desired duration, then click Start Analysis" />
              <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#6B7280",
                    display: "block", marginBottom: 6 }}>
                    DURATION (seconds)
                  </label>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <input
                      type="number"
                      min={5}
                      max={120}
                      value={duration}
                      onChange={(e) => setDuration(e.target.value)}
                      disabled={isRunning}
                      style={{
                        width: 110, padding: "10px 12px",
                        border: "2px solid #3B82F6",
                        borderRadius: 8, fontSize: 18, fontWeight: 700,
                        outline: "none", textAlign: "center",
                        color: "#111827",
                        background: isRunning ? "#F9FAFB" : "#fff",
                        boxShadow: "0 0 0 3px rgba(59,130,246,0.15)"
                      }}
                    />
                    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      <button
                        disabled={isRunning}
                        onClick={() => setDuration(d => String(Math.min(120, parseInt(d||"0",10) + 5)))}
                        style={{
                          width: 32, height: 28, borderRadius: 6, border: "1.5px solid #E5E7EB",
                          background: "#fff", cursor: "pointer", fontSize: 14, fontWeight: 700,
                          color: "#1D4ED8", display: "flex", alignItems: "center", justifyContent: "center"
                        }}>▲</button>
                      <button
                        disabled={isRunning}
                        onClick={() => setDuration(d => String(Math.max(5, parseInt(d||"0",10) - 5)))}
                        style={{
                          width: 32, height: 28, borderRadius: 6, border: "1.5px solid #E5E7EB",
                          background: "#fff", cursor: "pointer", fontSize: 14, fontWeight: 700,
                          color: "#1D4ED8", display: "flex", alignItems: "center", justifyContent: "center"
                        }}>▼</button>
                    </div>
                    <div style={{
                      padding: "6px 12px", background: "#EFF6FF", borderRadius: 8,
                      fontSize: 13, color: "#1D4ED8", fontWeight: 600
                    }}>
                      {parseInt(duration||"0",10)}s&nbsp;
                      <span style={{ fontWeight: 400, color: "#6B7280" }}>
                        (~{Math.ceil(parseInt(duration||"0",10)/60)} min)
                      </span>
                    </div>
                  </div>
                </div>
                <div style={{ alignSelf: "flex-end" }}>
                  <button onClick={startSession} disabled={isRunning || starting} style={{
                    padding: "10px 28px", background: isRunning ? "#93C5FD" : "#1D4ED8",
                    color: "#fff", border: "none", borderRadius: 8, fontSize: 14,
                    fontWeight: 700, cursor: isRunning ? "not-allowed" : "pointer",
                    boxShadow: isRunning ? "none" : "0 2px 8px rgba(29,78,216,.35)",
                    transition: "all .2s"
                  }}>
                    {isRunning ? "⏳  Analyzing…" : starting ? "Starting…" : "▶  Start Analysis"}
                  </button>
                </div>
              </div>
              {isRunning && <SessionProgress progress={session.progress} />}
              {session?.status === "error" && (
                <div style={{ marginTop: 12, padding: "10px 14px", background: "#FEF2F2",
                  borderRadius: 8, fontSize: 13, color: "#B91C1C" }}>
                  ⚠ {session.error || "An error occurred."}
                </div>
              )}
            </Card>

            {/* ── Results ── */}
            {isDone && (
              <>
                {/* Overall score banner */}
                <div style={{
                  background: "#fff", borderRadius: 14, padding: "24px 28px",
                  boxShadow: "0 1px 3px rgba(0,0,0,.08), 0 4px 16px rgba(0,0,0,.04)",
                  marginBottom: 24, display: "flex", alignItems: "center", gap: 28,
                  flexWrap: "wrap", borderLeft: `5px solid ${scoreColor(session.final_score)}`
                }}>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#9CA3AF",
                      letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: 4 }}>
                      Final Score
                    </div>
                    <div style={{ fontSize: 52, fontWeight: 800,
                      color: scoreColor(session.final_score), lineHeight: 1, letterSpacing: "-0.03em" }}>
                      <AnimNumber value={session.final_score} /><span style={{ fontSize: 22 }}>/100</span>
                    </div>
                    <div style={{ fontSize: 16, fontWeight: 700,
                      color: scoreColor(session.final_score), marginTop: 4 }}>
                      {scoreLabel(session.final_score)}
                    </div>
                  </div>
                  <div style={{ flex: 1, minWidth: 240 }}>
                    <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.6,
                      padding: "14px 18px", background: "#F9FAFB", borderRadius: 10 }}>
                      💬 {session.feedback}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 20 }}>
                    <Gauge score={session.audio_score}      label="Audio"      />
                    <Gauge score={session.expression_score} label="Expression" />
                    <Gauge score={session.nlp_score}        label="NLP"        />
                  </div>
                </div>

                {/* ── Three analysis panels ── */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 20 }}>

                  {/* Audio */}
                  <Card title="Audio Metrics" accent="#3B82F6">
                    <SectionHeader step="A" title="Audio Analysis"
                      subtitle={`Score: ${session.audio_score}/100`} />
                    <div style={{ marginTop: 18 }}>
                      <MetricBar label="Words Per Minute"  value={session.audio_metrics?.wpm || 0}        max={200}  unit=" wpm" color="#3B82F6" />
                      <MetricBar label="Word Count"        value={session.audio_metrics?.word_count || 0} max={500}            color="#3B82F6" />
                      <MetricBar label="Filler Words"      value={session.audio_metrics?.filler_count||0} max={20}             color="#F59E0B" />
                      <MetricBar label="Avg Pitch (Hz)"    value={session.audio_metrics?.avg_pitch || 0}  max={300}  unit=" Hz" color="#8B5CF6" />
                      <MetricBar label="Pitch Variation"   value={session.audio_metrics?.pitch_variation||0} max={80}          color="#8B5CF6" />
                      <MetricBar label="Energy Level"      value={Math.round((session.audio_metrics?.energy||0)*1e5)} max={100} color="#10B981" />
                    </div>
                    {session.transcript && (
                      <div style={{ marginTop: 16, padding: "12px 14px", background: "#EFF6FF",
                        borderRadius: 8, fontSize: 12, color: "#1E40AF", lineHeight: 1.6 }}>
                        <strong style={{ display: "block", marginBottom: 4, fontSize: 11,
                          textTransform: "uppercase", letterSpacing: "0.05em" }}>Transcript</strong>
                        {session.transcript}
                      </div>
                    )}
                  </Card>

                  {/* Expression */}
                  <Card title="Expression Metrics" accent="#10B981">
                    <SectionHeader step="E" title="Expression Analysis"
                      subtitle={`Score: ${session.expression_score}/100`} />
                    <div style={{ marginTop: 18 }}>
                      <MetricBar label="Average Smile"       value={session.expression_metrics?.avg_smile || 0}          max={0.5}  color="#10B981" />
                      <MetricBar label="Smile Consistency"   value={Math.max(0,1-(session.expression_metrics?.smile_variance||0)*200)} max={1} color="#10B981" />
                      <MetricBar label="Head Movement"       value={(session.expression_metrics?.avg_movement||0)*1000}   max={12}   color="#3B82F6" />
                      <MetricBar label="Emotion Stability"   value={session.expression_metrics?.emotion_stability || 0}   max={1}    color="#8B5CF6" />
                    </div>
                    <div style={{ marginTop: 16 }}>
                      {[
                        { label: "Smile Score",  val: session.expression_metrics?.avg_smile,          fmt: v => (v*100).toFixed(0)+"%" },
                        { label: "Stability",    val: session.expression_metrics?.emotion_stability,   fmt: v => (v*100).toFixed(0)+"%" },
                      ].map(({ label, val, fmt }) => (
                        <div key={label} style={{
                          display: "flex", justifyContent: "space-between",
                          padding: "8px 0", borderBottom: "1px solid #F3F4F6", fontSize: 13
                        }}>
                          <span style={{ color: "#6B7280" }}>{label}</span>
                          <span style={{ fontWeight: 700, color: "#111827" }}>{val != null ? fmt(val) : "—"}</span>
                        </div>
                      ))}
                    </div>
                  </Card>

                  {/* NLP */}
                  <Card title="NLP Metrics" accent="#8B5CF6">
                    <SectionHeader step="N" title="NLP Analysis"
                      subtitle={`Score: ${session.nlp_score}/100`} />
                    <div style={{ marginTop: 18 }}>
                      <MetricBar label="Filler Words"     value={session.nlp_metrics?.["Filler Words"]||0}    max={20}   color="#F59E0B" />
                      <MetricBar label="Keyword Matches"  value={session.nlp_metrics?.["Keyword Matches"]||0} max={8}    color="#10B981" />
                      <MetricBar label="Sentiment Score"  value={session.nlp_metrics?.["Sentiment Score"]||0} max={100}  color="#3B82F6" />
                      <MetricBar label="Clarity Score"    value={session.nlp_metrics?.["Clarity Score"]||0}   max={100}  color="#8B5CF6" />
                    </div>
                    <div style={{ marginTop: 16 }}>
                      {Object.entries(session.nlp_metrics || {}).map(([k, v]) => (
                        <div key={k} style={{
                          display: "flex", justifyContent: "space-between",
                          padding: "8px 0", borderBottom: "1px solid #F3F4F6", fontSize: 13
                        }}>
                          <span style={{ color: "#6B7280" }}>{k}</span>
                          <span style={{ fontWeight: 700, color: "#111827" }}>{v}</span>
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>
              </>
            )}

            {/* Empty state */}
            {!session && (
              <div style={{ textAlign: "center", padding: "60px 20px", color: "#9CA3AF" }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>🎙</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: "#6B7280" }}>
                  No analysis yet
                </div>
                <div style={{ fontSize: 13, marginTop: 6 }}>
                  Configure your session above and click Start Analysis
                </div>
              </div>
            )}
          </>
        )}

        {/* ════════════════════════════════════════════════════════════════
            HISTORY VIEW
        ════════════════════════════════════════════════════════════════ */}
        {view === "history" && (
          <>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
              <div>
                <h1 style={{ fontSize: 22, fontWeight: 800, margin: "0 0 4px", letterSpacing: "-0.02em" }}>
                  Session History
                </h1>
                <p style={{ fontSize: 13, color: "#6B7280", margin: 0 }}>
                  {history.length} completed session{history.length !== 1 ? "s" : ""}
                </p>
              </div>
              <button onClick={fetchHistory} style={{
                padding: "8px 16px", borderRadius: 8, border: "1.5px solid #E5E7EB",
                background: "#fff", cursor: "pointer", fontSize: 13, fontWeight: 600, color: "#374151"
              }}>↻ Refresh</button>
            </div>

            {selected ? (
              // ── Expanded history detail ──
              <div>
                <button onClick={() => setSelected(null)} style={{
                  marginBottom: 20, padding: "6px 14px", borderRadius: 8,
                  border: "1.5px solid #E5E7EB", background: "#fff",
                  cursor: "pointer", fontSize: 13, fontWeight: 600, color: "#374151"
                }}>← Back to list</button>

                <div style={{ display: "flex", gap: 20, marginBottom: 20, flexWrap: "wrap" }}>
                  <div style={{
                    flex: "0 0 auto", background: "#fff", borderRadius: 14,
                    padding: "24px 28px", boxShadow: "0 1px 3px rgba(0,0,0,.08)",
                    borderLeft: `5px solid ${scoreColor(selected.final_score)}`
                  }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#9CA3AF",
                      textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 6 }}>
                      Final Score
                    </div>
                    <div style={{ fontSize: 48, fontWeight: 800, color: scoreColor(selected.final_score),
                      letterSpacing: "-0.03em", lineHeight: 1 }}>
                      {selected.final_score}<span style={{ fontSize: 20 }}>/100</span>
                    </div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: scoreColor(selected.final_score), marginTop: 6 }}>
                      {scoreLabel(selected.final_score)}
                    </div>
                  </div>
                  <div style={{
                    flex: 1, minWidth: 200, background: "#fff", borderRadius: 14,
                    padding: "24px 28px", boxShadow: "0 1px 3px rgba(0,0,0,.08)"
                  }}>
                    <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.6 }}>
                      💬 {selected.feedback}
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 16, justifyContent: "center", marginBottom: 28 }}>
                  <Gauge score={selected.audio_score}      label="Audio"      size={140} />
                  <Gauge score={selected.expression_score} label="Expression" size={140} />
                  <Gauge score={selected.nlp_score}        label="NLP"        size={140} />
                </div>
              </div>
            ) : (
              // ── History list ──
              <Card title="Past Sessions" accent="#1D4ED8">
                {history.length === 0 ? (
                  <div style={{ textAlign: "center", padding: "40px 0", color: "#9CA3AF" }}>
                    <div style={{ fontSize: 36, marginBottom: 12 }}>📋</div>
                    No completed sessions yet. Run your first analysis from the Dashboard.
                  </div>
                ) : (
                  history.map(item => (
                    <HistoryRow key={item.session_id} item={item} onSelect={setSelected} />
                  ))
                )}
              </Card>
            )}
          </>
        )}
      </main>
    </div>
  );
}
