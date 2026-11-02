import { useEffect, useState } from 'react'
import './App.css'
import './Extra.css'
import Live, { Processing } from './components/Live'
import Results from './components/Results'
import Setup from './components/Setup'
import { useInterview } from './hooks/useInterview'
import { getConfig, getReady } from './lib/api'

const DEFAULT_TOPIC = 'General interview'

function useServer() {
  const [config, setConfig] = useState(null)
  const [ready, setReady] = useState(false)
  const [offline, setOffline] = useState(false)

  useEffect(() => {
    let alive = true
    let timer
    const tick = async () => {
      try {
        if (!config) {
          const c = await getConfig()
          if (alive) setConfig(c)
        }
        const ok = await getReady()
        if (alive) {
          setReady(ok)
          setOffline(false)
          if (!ok) timer = setTimeout(tick, 2000)
        }
      } catch {
        if (alive) {
          setOffline(true)
          timer = setTimeout(tick, 4000)
        }
      }
    }
    tick()
    return () => {
      alive = false
      clearTimeout(timer)
    }
  }, [config])

  return { config, ready, offline }
}

export default function App() {
  const iv = useInterview()
  const { config, ready, offline } = useServer()
  const [topic, setTopic] = useState('')
  const [duration, setDuration] = useState(60)

  // derived, not stored: keeps the chosen length inside what the server allows
  const effectiveDuration = config ? Math.min(Math.max(duration, config.min_duration), config.max_duration) : duration

  const activeTopic = topic.trim() || DEFAULT_TOPIC
  const setup = iv.phase === 'idle' || iv.phase === 'error'
  const live = ['preparing', 'calibrating', 'recording'].includes(iv.phase)

  return (
    <div className="app-shell">
      <main className="app-container">
        <section className="hero-card no-print">
          <div className="hero-copy">
            <span className="eyebrow">/ AI-powered interview workspace</span>
            <h1>
              Practice the interview. <em style={{ color: 'var(--primary)', fontStyle: 'italic' }}>Read the room.</em>
            </h1>
            <p>
              An honest second opinion on every answer: your voice, your presence and your words, scored with the reasons shown, so you walk
              into the real thing already warmed up.
            </p>
          </div>
          <div className="hero-badge">
            <span>● Active question</span>
            <strong>{live || iv.phase === 'processing' || iv.phase === 'done' ? iv.session?.topic || activeTopic : activeTopic}</strong>
          </div>
        </section>

        {offline && setup && (
          <div className="error-box" role="alert">
            Cannot reach the server. Make sure the backend is running, then this page will reconnect automatically.
          </div>
        )}

        {setup && (
          <Setup
            topic={topic}
            setTopic={setTopic}
            duration={effectiveDuration}
            setDuration={setDuration}
            config={config}
            ready={ready && !offline}
            error={iv.error}
            onStart={() => iv.start(activeTopic, effectiveDuration)}
          />
        )}

        {live && (
          <Live
            phase={iv.phase}
            topic={iv.session?.topic || activeTopic}
            duration={iv.session?.duration || effectiveDuration}
            elapsed={iv.elapsed}
            level={iv.level}
            partial={iv.partial}
            stream={iv.stream}
            camera={iv.camera}
            faceVisible={iv.faceVisible}
            countdown={iv.countdown}
            prepNote={iv.prepNote}
            onStop={iv.stop}
          />
        )}

        {iv.phase === 'processing' && <Processing stage={iv.stage} />}

        {iv.phase === 'done' && iv.result && <Results result={iv.result} session={iv.session} onRestart={iv.reset} />}
      </main>
    </div>
  )
}
