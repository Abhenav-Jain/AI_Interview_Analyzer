import { useCallback, useEffect, useRef, useState } from 'react'
import { createSession, getSession, wsUrl } from '../lib/api'
import { createFaceTracker } from '../lib/faceTracker'
import { saveAttempt } from '../lib/history'

const CAL_SECONDS = 3
const SAMPLE_MS = 100
const AUDIO = { channelCount: 1, echoCancellation: true, noiseSuppression: false, autoGainControl: false }
const VIDEO = { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 30 }, facingMode: 'user' }

function mediaError(e) {
  if (!window.isSecureContext || !navigator.mediaDevices) {
    return 'Camera and microphone only work on HTTPS or localhost. Open the app over a secure connection.'
  }
  switch (e?.name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return 'Microphone access was blocked. Click the lock icon in the address bar, allow the microphone, and try again.'
    case 'NotFoundError':
      return 'No microphone was found. Plug one in or check your system sound settings.'
    case 'NotReadableError':
      return 'Your microphone is being used by another app. Close it and try again.'
    default:
      return e?.message || 'Could not access your microphone.'
  }
}

export function useInterview() {
  const [phase, setPhase] = useState('idle') // idle | preparing | calibrating | recording | processing | done | error
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [partial, setPartial] = useState('')
  const [stage, setStage] = useState({ stage: null, progress: 0 })
  const [elapsed, setElapsed] = useState(0)
  const [level, setLevel] = useState(0)
  const [faceVisible, setFaceVisible] = useState(null)
  const [camera, setCamera] = useState('off') // off | on | unavailable
  const [stream, setStream] = useState(null)
  const [prepNote, setPrepNote] = useState('')
  const [countdown, setCountdown] = useState(0)
  const [session, setSession] = useState(null) // {session_id, token, topic, duration}
  const r = useRef({})

  const teardown = useCallback(() => {
    const s = r.current
    ;[s.faceTimer, s.flushTimer, s.tickTimer, s.pollTimer, s.calTimer].forEach((t) => t && clearInterval(t))
    s.faceTimer = s.flushTimer = s.tickTimer = s.pollTimer = s.calTimer = null
    try { s.node?.port && (s.node.port.onmessage = null) } catch { /* already closed */ }
    try { s.node?.disconnect() } catch { /* ignore */ }
    try { s.ctx?.close() } catch { /* ignore */ }
    s.media?.getTracks().forEach((t) => t.stop())
    try { s.tracker?.close() } catch { /* ignore */ }
    if (s.video) {
      s.video.srcObject = null
      s.video = null
    }
    if (s.ws && s.ws.readyState <= 1) {
      s.ws.onclose = null
      try { s.ws.close() } catch { /* ignore */ }
    }
    r.current = { phase: 'idle' }
    setStream(null)
  }, [])

  useEffect(() => teardown, [teardown])

  const fail = useCallback(
    (message) => {
      teardown()
      r.current.phase = 'error'
      setError(message)
      setPhase('error')
    },
    [teardown],
  )

  const finalize = useCallback(
    (res, sess) => {
      if (r.current.phase === 'done') return
      const info = sess || r.current.session
      const keep = { phase: 'done', session: info }
      teardown()
      r.current = keep
      setResult(res)
      setPhase('done')
      if (info) saveAttempt(info.session_id, info.topic, res)
    },
    [teardown],
  )

  const pollForResult = useCallback(() => {
    const s = r.current
    const sess = s.session
    if (!sess || s.pollTimer) return
    let tries = 0
    s.pollTimer = setInterval(async () => {
      tries += 1
      try {
        const row = await getSession(sess.session_id, sess.token)
        if (row.status === 'done' && row.result) {
          clearInterval(r.current.pollTimer)
          finalize(row.result, sess)
        } else if (row.status === 'failed' || row.status === 'aborted') {
          fail(row.error || 'The analysis failed. Please try again.')
        }
      } catch { /* keep trying until the limit */ }
      if (tries >= 40) fail('The analysis is taking too long. Please try again.')
    }, 1500)
  }, [fail, finalize])

  const handleMessage = useCallback(
    (ev) => {
      let m
      try { m = JSON.parse(ev.data) } catch { return }
      if (m.type === 'partial') setPartial(m.text)
      else if (m.type === 'stage') setStage({ stage: m.stage, progress: m.progress })
      else if (m.type === 'result') finalize(m.data)
      else if (m.type === 'error') fail(m.message)
    },
    [fail, finalize],
  )

  const beginProcessing = useCallback(() => {
    const s = r.current
    if (s.phase !== 'recording') return
    s.phase = 'processing'
    ;[s.faceTimer, s.flushTimer, s.tickTimer].forEach((t) => t && clearInterval(t))
    // Ask the audio worklet for its buffered tail, give it a moment to arrive, then close the stream.
    try { s.node?.port.postMessage('flush') } catch { /* node already gone */ }
    setFaceVisible(null)
    setLevel(0)
    setStage({ stage: 'transcribing', progress: 30 })
    setPhase('processing')
    setTimeout(() => {
      const c = r.current
      if (c !== s) return // user reset in the meantime
      s.recording = false
      if (s.batch?.length && s.ws?.readyState === 1) s.ws.send(JSON.stringify({ type: 'face', samples: s.batch.splice(0) }))
      if (s.ws?.readyState === 1) s.ws.send(JSON.stringify({ type: 'end' }))
      try { s.node?.disconnect() } catch { /* ignore */ }
      s.media?.getTracks().forEach((t) => t.stop())
      setStream(null)
      // If the socket drops before the result arrives, fall back to polling the REST endpoint.
      if (s.ws) s.ws.onclose = () => r.current.phase === 'processing' && pollForResult()
    }, 150)
  }, [pollForResult])

  const stop = useCallback(() => beginProcessing(), [beginProcessing])

  const start = useCallback(
    async (topic, duration) => {
      teardown()
      setError('')
      setResult(null)
      setPartial('')
      setElapsed(0)
      setLevel(0)
      setStage({ stage: null, progress: 0 })
      setCamera('off')
      setFaceVisible(null)
      r.current = { phase: 'preparing' }
      setPhase('preparing')

      try {
        setPrepNote('Creating your session…')
        const sess = await createSession(topic, duration)
        const info = { ...sess, topic: sess.topic || topic }
        r.current.session = info
        setSession(info)

        // ---- permissions --------------------------------------------------
        setPrepNote('Waiting for microphone and camera permission…')
        if (!navigator.mediaDevices?.getUserMedia) throw Object.assign(new Error(), { name: 'SecurityError' })
        let media
        let hasVideo = true
        try {
          media = await navigator.mediaDevices.getUserMedia({ audio: AUDIO, video: VIDEO })
        } catch {
          try {
            media = await navigator.mediaDevices.getUserMedia({ audio: AUDIO })
            hasVideo = false
          } catch (e2) {
            throw new Error(mediaError(e2))
          }
        }
        r.current.media = media
        if (r.current.phase !== 'preparing') return

        // ---- face tracking (optional) ------------------------------------
        let tracker = null
        let video = null
        if (hasVideo) {
          setPrepNote('Loading face tracking…')
          try {
            tracker = await createFaceTracker()
            video = document.createElement('video')
            video.muted = true
            video.playsInline = true
            video.srcObject = new MediaStream(media.getVideoTracks())
            await video.play()
            r.current.tracker = tracker
            r.current.video = video
            setStream(new MediaStream(media.getVideoTracks()))
            setCamera('on')
          } catch (e) {
            console.warn('Face tracking unavailable:', e)
            media.getVideoTracks().forEach((t) => t.stop())
            tracker = null
            setCamera('unavailable')
          }
        } else {
          setCamera('unavailable')
        }

        // ---- websocket ----------------------------------------------------
        setPrepNote('Connecting…')
        const ws = new WebSocket(wsUrl(sess.session_id, sess.token))
        ws.binaryType = 'arraybuffer'
        r.current.ws = ws
        await new Promise((resolve, reject) => {
          ws.onmessage = (ev) => {
            const m = JSON.parse(ev.data)
            if (m.type === 'ready') resolve()
            else if (m.type === 'error') reject(new Error(m.message))
          }
          ws.onerror = () => reject(new Error('Could not open a connection to the server.'))
          ws.onclose = () => reject(new Error('The server closed the connection.'))
        })
        ws.onmessage = handleMessage
        ws.onclose = () => {
          const p = r.current.phase
          if (p === 'recording' || p === 'calibrating') fail('Connection lost while recording. Your answer was not saved. Please try again.')
        }

        // ---- audio capture ------------------------------------------------
        const ctx = new AudioContext()
        await ctx.audioWorklet.addModule('/pcm-worklet.js')
        const src = ctx.createMediaStreamSource(new MediaStream(media.getAudioTracks()))
        const node = new AudioWorkletNode(ctx, 'pcm-capture')
        const mute = ctx.createGain()
        mute.gain.value = 0 // keep the graph alive without playing the mic back
        src.connect(node)
        node.connect(mute)
        mute.connect(ctx.destination)
        r.current.ctx = ctx
        r.current.node = node
        node.port.onmessage = (e) => {
          const lv = Math.min(1, e.data.rms * 6)
          setLevel((prev) => (Math.abs(prev - lv) > 0.03 ? lv : prev))
          if (r.current.recording && ws.readyState === 1) ws.send(e.data.pcm)
        }

        // ---- calibration: look into the lens ------------------------------
        const sampleFace = (tSec) => {
          const v = r.current.video
          if (!tracker || !v || v.readyState < 2) return null
          try { return tracker.sample(v, tSec) } catch { return null }
        }
        if (tracker) {
          r.current.phase = 'calibrating'
          setPhase('calibrating')
          const cal = []
          const t0 = performance.now()
          await new Promise((resolve) => {
            r.current.calTimer = setInterval(() => {
              const t = (performance.now() - t0) / 1000
              const smp = sampleFace(t)
              if (smp) cal.push(smp)
              setCountdown(Math.max(0, Math.ceil(CAL_SECONDS - t)))
              if (t >= CAL_SECONDS) {
                clearInterval(r.current.calTimer)
                resolve()
              }
            }, SAMPLE_MS)
          })
          if (r.current.phase !== 'calibrating') return
          if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'calibration', samples: cal.slice(0, 200) }))
        }

        // ---- record -------------------------------------------------------
        const s = r.current
        s.phase = 'recording'
        s.recording = true
        s.batch = []
        setPhase('recording')
        ws.send(JSON.stringify({ type: 'start' }))
        const tStart = performance.now()

        if (tracker) {
          let lastVisible = null
          s.faceTimer = setInterval(() => {
            const smp = sampleFace((performance.now() - tStart) / 1000)
            if (!smp) return
            s.batch.push(smp)
            const vis = !!smp.v
            if (vis !== lastVisible) {
              lastVisible = vis
              setFaceVisible(vis)
            }
          }, SAMPLE_MS)
          s.flushTimer = setInterval(() => {
            if (s.batch.length && ws.readyState === 1) ws.send(JSON.stringify({ type: 'face', samples: s.batch.splice(0, 200) }))
          }, 1000)
        }
        s.tickTimer = setInterval(() => {
          const el = (performance.now() - tStart) / 1000
          setElapsed(Math.min(el, duration))
          if (el >= duration) beginProcessing()
        }, 200)
      } catch (e) {
        fail(e?.message || 'Something went wrong while starting the interview.')
      }
    },
    [beginProcessing, fail, handleMessage, teardown],
  )

  const reset = useCallback(() => {
    teardown()
    setPhase('idle')
    setResult(null)
    setError('')
    setSession(null)
  }, [teardown])

  return { phase, error, result, partial, stage, elapsed, level, faceVisible, camera, stream, prepNote, countdown, session, start, stop, reset }
}
