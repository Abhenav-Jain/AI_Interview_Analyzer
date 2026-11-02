import { TopicSelector } from './ui'

const PRESETS = [30, 60, 90, 120]

export default function Setup({ topic, setTopic, duration, setDuration, config, ready, error, onStart }) {
  const options = PRESETS.filter((d) => !config || (d >= config.min_duration && d <= config.max_duration))
  return (
    <section className="setup-grid">
      <div className="panel panel-lg">
        <div className="panel-head">
          <h2>Interview setup</h2>
          <p>Pick a question and how long you want to answer, then start.</p>
        </div>

        <div className="form-stack">
          <div className="field-block">
            <label className="field-label">/ Interview question</label>
            <TopicSelector topic={topic} setTopic={setTopic} />
          </div>

          <div className="field-block">
            <label className="field-label">/ Answer length</label>
            <div className="duration-row">
              {options.map((d) => (
                <button
                  key={d}
                  type="button"
                  className={`chip ${duration === d ? 'active' : ''}`}
                  onClick={() => setDuration(d)}
                  aria-pressed={duration === d}
                >
                  {d}s
                </button>
              ))}
            </div>
            <p className="hint">Real interview answers usually run 60 to 120 seconds. You can stop early.</p>
          </div>

          <button type="button" className="primary-btn" onClick={onStart} disabled={!ready}>
            {ready ? 'Start interview →' : 'Warming up the speech model…'}
          </button>
          {error && (
            <div className="error-box" role="alert">
              {error}
            </div>
          )}
        </div>
      </div>

      <div className="panel panel-lg">
        <div className="panel-head">
          <h2>What you'll get</h2>
          <p>Three independent analyses, each explained with the reason behind the score.</p>
        </div>
        <div className="feature-list">
          <Feature title="Voice" text="Pace, fillers, pauses, pitch variety and recording quality, measured on your actual speaking time." icon={<path d="M4 10a6 6 0 0 0 12 0M10 16v3M7 3h6v7a3 3 0 0 1-6 0z" strokeLinecap="round" />} />
          <Feature title="Presence" text="Eye contact calibrated to your own camera position, head movement, composure and warmth." icon={<><circle cx="10" cy="10" r="7" /><circle cx="7.5" cy="8.5" r="0.8" fill="currentColor" /><circle cx="12.5" cy="8.5" r="0.8" fill="currentColor" /><path d="M7.5 12.5c1 1 4 1 5 0" strokeLinecap="round" /></>} />
          <Feature title="Answer quality" text="Relevance, structure, evidence and depth, graded against a rubric with quotes from your answer." icon={<><path d="M4 5h12M4 10h12M4 15h8" strokeLinecap="round" /><circle cx="15" cy="15" r="1.5" fill="currentColor" /></>} />
        </div>
        <p className="privacy-note">
          Your video never leaves this device; only small numbers such as head angle and smile level are sent. Audio is analysed in memory and
          never saved. You can erase your result from the report page.
        </p>
      </div>
    </section>
  )
}

function Feature({ title, text, icon }) {
  return (
    <div className="feature-card">
      <div className="feature-icon">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">{icon}</svg>
      </div>
      <div>
        <strong>{title}</strong>
        <p>{text}</p>
      </div>
    </div>
  )
}
