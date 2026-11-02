// Same-origin by default (Docker serves UI + API together; Vite proxies in dev).
// Set VITE_API_URL only if the API lives on another origin.
const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
const API_KEY = import.meta.env.VITE_API_KEY

async function request(path, { method = 'GET', body, headers = {} } = {}) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...headers },
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new Error('Cannot reach the server. Check your connection and that the backend is running.')
  }
  if (!res.ok) {
    let detail = ''
    try {
      const j = await res.json()
      detail = typeof j.detail === 'string' ? j.detail : ''
    } catch { /* non-JSON error body */ }
    const err = new Error(detail || `Request failed (${res.status})`)
    err.status = res.status
    throw err
  }
  return res.status === 204 ? null : res.json()
}

export const getConfig = () => request('/api/config')
export const getReady = async () => {
  try {
    const r = await fetch(`${BASE}/api/ready`)
    return r.ok
  } catch {
    return false
  }
}
export const createSession = (topic, duration) =>
  request('/api/sessions', {
    method: 'POST',
    body: { topic, duration },
    headers: API_KEY ? { 'X-API-Key': API_KEY } : {},
  })
export const getSession = (id, token) => request(`/api/sessions/${id}`, { headers: { 'X-Session-Token': token } })
export const deleteSession = (id, token) =>
  request(`/api/sessions/${id}`, { method: 'DELETE', headers: { 'X-Session-Token': token } })

export function wsUrl(id, token) {
  const u = BASE ? new URL(BASE) : new URL(window.location.href)
  const proto = u.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${u.host}/api/ws/sessions/${id}?token=${encodeURIComponent(token)}`
}
