import { useMemo, useState } from 'react'
import { TOPICS } from '../lib/topics'
import { scoreTone } from '../lib/format'

export function TopicSelector({ topic, setTopic }) {
  const [open, setOpen] = useState(false)
  const filtered = useMemo(() => {
    const q = topic.trim().toLowerCase()
    return q ? TOPICS.filter((t) => t.toLowerCase().includes(q)) : TOPICS
  }, [topic])

  return (
    <div className="topic-selector">
      <input
        className="app-input"
        value={topic}
        maxLength={200}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={(e) => {
          setTopic(e.target.value)
          setOpen(true)
        }}
        placeholder="Type your own question or pick one…"
        aria-label="Interview question"
      />
      {open && filtered.length > 0 && (
        <div className="topic-dropdown">
          {filtered.slice(0, 6).map((item) => (
            <button
              key={item}
              type="button"
              className="topic-option"
              onMouseDown={() => {
                setTopic(item)
                setOpen(false)
              }}
            >
              {item}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function ScoreRing({ score }) {
  const angle = Math.max(0, Math.min(100, score || 0)) * 3.6
  return (
    <div
      className={`score-ring ${scoreTone(score)}`}
      role="img"
      aria-label={`Overall score ${score} out of 100`}
      style={{ background: `conic-gradient(var(--ring) ${angle}deg, rgba(255,255,255,0.06) ${angle}deg)` }}
    >
      <div className="score-ring-inner">
        <div className="score-ring-value">{score ?? 0}</div>
        <div className="score-ring-total">/ 100</div>
      </div>
    </div>
  )
}

export function ScoreCard({ title, value, weight, note }) {
  const has = value != null
  return (
    <div className={`score-card ${has ? '' : 'score-card-off'}`}>
      <span>
        {title}
        {has && weight != null ? <small className="weight-tag"> · {Math.round(weight * 100)}% of total</small> : null}
      </span>
      <strong>{has ? value : '–'}</strong>
      {!has && note ? <small className="score-card-note">{note}</small> : null}
    </div>
  )
}

export function Bar({ value, max, tone }) {
  const pct = max ? Math.max(0, Math.min(100, (value / max) * 100)) : 0
  const t = tone || (pct >= 80 ? 'good' : pct >= 55 ? 'mid' : 'low')
  return (
    <div className="bar" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
      <div className={`bar-fill bar-${t}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

export function LevelMeter({ level }) {
  const bars = 18
  const on = Math.round(level * bars)
  return (
    <div className="meter" aria-label="Microphone level">
      {Array.from({ length: bars }, (_, i) => (
        <span key={i} className={i < on ? 'on' : ''} style={{ height: `${30 + (i / bars) * 70}%` }} />
      ))}
    </div>
  )
}
