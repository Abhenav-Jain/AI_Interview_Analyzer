import { useEffect, useRef } from 'react'
import { mmss } from '../lib/format'
import { LevelMeter } from './ui'

export default function Live({ phase, topic, duration, elapsed, level, partial, stream, camera, faceVisible, countdown, prepNote, onStop }) {
  const videoRef = useRef(null)
  useEffect(() => {
    if (videoRef.current) videoRef.current.srcObject = stream
  }, [stream])

  const preparing = phase === 'preparing'
  const calibrating = phase === 'calibrating'
  const pct = Math.min(100, (elapsed / duration) * 100)

  return (
    <section className="live-layout live-split">
      <div className="panel video-panel">
        <div className={`video-wrap ${stream ? '' : 'video-off'}`}>
          {stream ? <video ref={videoRef} autoPlay muted playsInline className="video-el" /> : <div className="video-placeholder">{camera === 'unavailable' ? 'Camera off. Voice and answer will still be scored.' : 'Camera'}</div>}
          {calibrating && (
            <div className="video-overlay">
              <strong>Look straight into the camera</strong>
              <span className="count">{countdown || '…'}</span>
              <small>This sets your own "eye contact" baseline.</small>
            </div>
          )}
          {phase === 'recording' && camera === 'on' && (
            <div className={`face-badge ${faceVisible === false ? 'bad' : ''}`}>{faceVisible === false ? 'Face not detected' : 'Face detected'}</div>
          )}
        </div>
      </div>

      <div className="panel live-panel">
        <div className="live-status">
          <div className="live-dot" />
          <span>{preparing ? 'Getting ready' : calibrating ? 'Calibrating' : 'Recording'}</span>
        </div>
        <h2 className="live-question">{topic}</h2>

        {preparing ? (
          <p className="muted" aria-live="polite">{prepNote}</p>
        ) : (
          <>
            <div className="timer-row">
              <span className="timer">{mmss(elapsed)}</span>
              <span className="muted">/ {mmss(duration)}</span>
              <LevelMeter level={level} />
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${pct}%` }} />
            </div>

            <div className="partial-box" aria-live="polite">
              <span className="field-label">/ What we are hearing</span>
              <p>{partial || (phase === 'recording' ? 'Start speaking. Your words will appear here as you pause.' : 'Recording starts in a moment.')}</p>
            </div>

            <button type="button" className="primary-btn" onClick={onStop} disabled={phase !== 'recording'}>
              Finish answer
            </button>
          </>
        )}
      </div>
    </section>
  )
}

const STEPS = [
  ['transcribing', 'Transcribing your answer'],
  ['analyzing', 'Evaluating content'],
  ['scoring', 'Calculating your scores'],
]

export function Processing({ stage }) {
  const idx = Math.max(0, STEPS.findIndex(([k]) => k === stage.stage))
  return (
    <section className="live-layout">
      <div className="panel live-panel">
        <div className="live-status">
          <div className="live-dot" />
          <span>Analysing</span>
        </div>
        <h2>Putting your report together</h2>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${stage.progress || 20}%` }} />
        </div>
        <ol className="stage-list" aria-live="polite">
          {STEPS.map(([k, label], i) => (
            <li key={k} className={i < idx ? 'done' : i === idx ? 'now' : ''}>{label}</li>
          ))}
        </ol>
      </div>
    </section>
  )
}
