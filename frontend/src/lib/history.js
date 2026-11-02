// Practice history lives only in this browser (localStorage). The server never
// lists sessions, so one user can never see another user's attempts.
const KEY = 'aia.history.v2'

export function loadHistory() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || '[]')
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

export function saveAttempt(id, topic, r) {
  if (!r || r.overall == null) return loadHistory()
  const entry = {
    id,
    at: Date.now(),
    topic,
    overall: r.overall,
    audio: r.audio?.score ?? null,
    expression: r.expression?.score ?? null,
    content: r.content?.score ?? null,
  }
  const next = [...loadHistory().filter((h) => h.id !== id), entry].slice(-50)
  try {
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch { /* storage full or blocked: history is a nicety, not a requirement */ }
  return next
}

export function clearHistory() {
  try {
    localStorage.removeItem(KEY)
  } catch { /* ignore */ }
}
