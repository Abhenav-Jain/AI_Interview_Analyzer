export const scoreTone = (s) => (s >= 85 ? 'excellent' : s >= 70 ? 'strong' : s >= 55 ? 'average' : 'weak')

export function scoreMessage(s) {
  if (s >= 85) return 'You are interview-ready. Only minor polish is left.'
  if (s >= 70) return 'A good base. A bit more structure and polish will push you higher.'
  if (s >= 55) return 'You have potential, but clarity and consistency need work.'
  return 'The fundamentals need work before this is interview-ready. Focus on the quick wins below.'
}

export const mmss = (sec) => `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, '0')}`

export function download(filename, text, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
