import { useMemo, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { deleteSession } from '../lib/api'
import { download, scoreMessage, scoreTone } from '../lib/format'
import { clearHistory, loadHistory } from '../lib/history'
import { Bar, ScoreCard, ScoreRing } from './ui'

function Transcript({ text, spans }) {
  const parts = useMemo(() => {
    const out = []
    let i = 0
    for (const [s, e] of [...(spans || [])].sort((a, b) => a[0] - b[0])) {
      if (s < i) continue
      if (s > i) out.push({ t: text.slice(i, s) })
      out.push({ t: text.slice(s, e), f: true })
      i = e
    }
    if (i < text.length) out.push({ t: text.slice(i) })
    return out
  }, [text, spans])
  return (
    <div className="transcript-box">
      {parts.map((p, k) => (p.f ? <mark key={k} className="filler-mark">{p.t}</mark> : <span key={k}>{p.t}</span>))}
    </div>
  )
}

function Components({ title, module, empty }) {
  return (
    <div className="detail-card">
      <div className="detail-card-head">
        <h4>{title}</h4>
        {module.score != null && <strong className="detail-score">{module.score}</strong>}
      </div>
      {module.available && module.components.length ? (
        <div className="comp-list">
          {module.components.map((c) => (
            <div key={c.key} className="comp-row">
              <div className="comp-top">
                <span>{c.label}</span>
                <strong>{c.display}</strong>
              </div>
              <Bar value={c.score} max={c.max} />
              {c.note && <small className="comp-note">{c.note}</small>}
            </div>
          ))}
        </div>
      ) : (
        <p className="empty-text">{module.notes?.[0] || empty}</p>
      )}
    </div>
  )
}

function Trend({ history, currentId }) {
  const data = history.map((h, i) => ({ n: i + 1, score: h.overall, topic: h.topic, id: h.id }))
  if (data.length < 2) {
    return <p className="empty-text">Complete a second attempt to see your progress over time.</p>
  }
  const prev = data[data.length - 2]
  const cur = data.find((d) => d.id === currentId) || data[data.length - 1]
  const delta = cur.score - prev.score
  return (
    <>
      <p className="trend-delta">
        {delta === 0 ? 'Same as your previous attempt.' : `${delta > 0 ? '+' : ''}${delta} points compared with your previous attempt.`}
      </p>
      <div className="trend-chart">
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis dataKey="n" tick={{ fill: '#9ba1ac', fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis domain={[0, 100]} tick={{ fill: '#9ba1ac', fontSize: 11 }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ background: '#1c2029', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 10, color: '#f2f3f5' }}
              formatter={(v) => [v, 'Score']}
              labelFormatter={(n) => `Attempt ${n}`}
            />
            <Line type="monotone" dataKey="score" stroke="#d4ff4d" strokeWidth={2} dot={{ r: 3, fill: '#d4ff4d' }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </>
  )
}

export default function Results({ result: r, session, onRestart }) {
  const [history, setHistory] = useState(loadHistory)
  const [deleted, setDeleted] = useState(false)
  const [delError, setDelError] = useState('')

  if (r.status === 'no_speech') {
    return (
      <section className="results-layout">
        <div className="panel">
          <div className="panel-head">
            <h2>We couldn't hear you</h2>
            <p>{r.tips?.[0]?.text}</p>
          </div>
          <button type="button" className="primary-btn" onClick={onRestart}>Try again →</button>
        </div>
      </section>
    )
  }

  const eraseData = async () => {
    setDelError('')
    try {
      if (session) await deleteSession(session.session_id, session.token)
      setDeleted(true)
    } catch (e) {
      setDelError(e.message)
    }
  }
  const eraseHistory = () => {
    clearHistory()
    setHistory([])
  }

  const rel = r.reliability
  const tone = scoreTone(r.overall)
  const w = r.weights || {}

  return (
    <section className="results-layout" id="report">
      <div className="results-top">
        <div className="panel result-hero">
          <div className="result-main">
            <ScoreRing score={r.overall} />
            <div className="result-copy">
              <div className={`score-pill ${tone}`}>{r.label}</div>
              <h2>Overall interview performance</h2>
              <p>{scoreMessage(r.overall)}</p>
            </div>
          </div>
          <div className="feedback-box">
            <span>/ Coach summary</span>
            <p>{r.content.summary || 'No written summary was available for this attempt.'}</p>
          </div>
          <div className={`rel-badge rel-${rel.level}`}>
            <strong>{rel.level === 'high' ? 'High confidence result' : rel.level === 'medium' ? 'Medium confidence result' : 'Low confidence result'}</strong>
            {rel.notes.length > 0 && (
              <ul>
                {rel.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="panel action-panel">
          <div className="panel-head">
            <h3>Next attempt</h3>
            <p>Fix the top quick win, then answer the same question again. Most gains happen between attempts 2 and 3.</p>
          </div>
          <button className="primary-btn" type="button" onClick={onRestart}>Practice again →</button>
          <div className="btn-row">
            <button type="button" className="ghost-btn" onClick={() => download('interview-report.json', JSON.stringify(r, null, 2))}>Download JSON</button>
            <button type="button" className="ghost-btn" onClick={() => window.print()}>Print / save PDF</button>
          </div>
        </div>
      </div>

      <div className="score-grid">
        <ScoreCard title="Voice" value={r.audio.score} weight={w.audio} note={r.audio.notes?.[0]} />
        <ScoreCard title="Presence" value={r.expression.score} weight={w.expression} note={r.expression.notes?.[0]} />
        <ScoreCard title="Answer quality" value={r.content.score} weight={w.content} />
      </div>

      {r.tips.length > 0 && (
        <div className="panel">
          <div className="panel-head">
            <h3>Quick wins</h3>
            <p>Sorted by how many points each fix could add to your total.</p>
          </div>
          <div className="improvement-list">
            {r.tips.map((t) => (
              <div key={t.title + t.text} className="improvement-card tip-card">
                <div className="tip-head">
                  <strong>{t.title}</strong>
                  <span className="tip-gain">+{t.potential_gain} pts</span>
                </div>
                <p>{t.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {r.content.available && (
        <div className="panel">
          <div className="panel-head">
            <h3>Answer quality{r.content.llm_used ? '' : ' (rule-based estimate)'}</h3>
            <p>
              {r.content.llm_used
                ? 'Graded on five criteria. Each score comes with evidence from your answer.'
                : 'Add an LLM API key on the server for a full rubric evaluation.'}
            </p>
          </div>
          {r.content.rubric.length > 0 && (
            <div className="rubric-list">
              {r.content.rubric.map((it) => (
                <div key={it.key} className="rubric-row">
                  <div className="comp-top">
                    <span>{it.label}</span>
                    <strong>{it.score}/10</strong>
                  </div>
                  <Bar value={it.score} max={10} />
                  {it.reason && <small className="comp-note">{it.reason}</small>}
                </div>
              ))}
            </div>
          )}
          <div className="insight-grid inner">
            <div>
              <h4 className="mini-title">What worked</h4>
              <ul className="tips-list">
                {r.content.strengths.length ? r.content.strengths.map((s) => <li key={s}>{s}</li>) : <li>No standout strengths were detected yet.</li>}
              </ul>
            </div>
            <div>
              <h4 className="mini-title">What to change</h4>
              <ul className="tips-list">
                {r.content.improvements.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      <div className="details-grid two">
        <Components title="Voice details" module={r.audio} empty="No audio details." />
        <Components title="Presence details" module={r.expression} empty="Camera data was not available." />
      </div>

      <div className="panel transcript-panel">
        <div className="panel-head">
          <h3>Transcript</h3>
          <p>
            {r.word_count} words
            {r.transcript_confidence != null ? ` · recognition confidence ${Math.round(r.transcript_confidence * 100)}%` : ''}. Filler words are highlighted.
          </p>
        </div>
        {r.transcript ? <Transcript text={r.transcript} spans={r.filler_spans} /> : <div className="transcript-box">Transcript not stored for this session.</div>}
        {r.fillers.length > 0 && (
          <div className="chip-row">
            {r.fillers.map((f) => (
              <span key={f.word} className="mini-chip">{f.word} × {f.count}</span>
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>Your progress</h3>
          <p>Kept only in this browser.</p>
        </div>
        <Trend history={history} currentId={session?.session_id} />
        {history.length > 0 && (
          <button type="button" className="link-btn" onClick={eraseHistory}>Clear local history</button>
        )}
      </div>

      <div className="panel privacy-panel no-print">
        <div className="panel-head">
          <h3>Your data</h3>
          <p>Audio is never stored. The report (scores and transcript) is kept on the server for a limited time so you can reload it.</p>
        </div>
        {deleted ? (
          <p className="muted">This report was erased from the server.</p>
        ) : (
          <button type="button" className="ghost-btn danger" onClick={eraseData}>Erase this report from the server</button>
        )}
        {delError && <div className="error-box" role="alert">{delError}</div>}
        <p className="muted tiny">Analysis time: {(r.timings_ms?.total ?? 0) / 1000}s after you finished.</p>
      </div>
    </section>
  )
}
