// AudioWorklet: captures the mic, resamples to 16 kHz mono and posts Int16 PCM
// chunks (~256 ms) to the main thread. Runs off the UI thread, so the page never
// stutters while recording (v1 recorded on the server with sounddevice).
class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super()
    this.step = sampleRate / 16000 // input samples per output sample
    this.pos = 0 // fractional read position in current block
    this.prev = 0
    this.out = new Int16Array(4096)
    this.n = 0
    this.sumSq = 0
    this.cnt = 0
    // 'flush' from the main thread: send whatever is buffered so the last word is never cut off
    this.port.onmessage = (e) => {
      if (e.data === 'flush' && this.n > 0) {
        const rms = Math.sqrt(this.sumSq / Math.max(this.cnt, 1))
        const tail = this.out.slice(0, this.n)
        this.port.postMessage({ pcm: tail.buffer, rms }, [tail.buffer])
        this.n = 0
      }
    }
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0]
    if (!ch || ch.length === 0) return true
    for (let i = 0; i < ch.length; i++) {
      this.sumSq += ch[i] * ch[i]
    }
    this.cnt += ch.length

    let pos = this.pos
    while (pos < ch.length) {
      const i = Math.floor(pos)
      const frac = pos - i
      const a = i < 0 ? this.prev : ch[i]
      const b = i + 1 < ch.length ? ch[i + 1] : a
      const s = Math.max(-1, Math.min(1, a + (b - a) * frac))
      this.out[this.n++] = s < 0 ? s * 32768 : s * 32767
      if (this.n === this.out.length) {
        const rms = Math.sqrt(this.sumSq / Math.max(this.cnt, 1))
        this.port.postMessage({ pcm: this.out.buffer, rms }, [this.out.buffer])
        this.out = new Int16Array(4096)
        this.n = 0
        this.sumSq = 0
        this.cnt = 0
      }
      pos += this.step
    }
    this.pos = pos - ch.length
    this.prev = ch[ch.length - 1]
    return true
  }
}
registerProcessor('pcm-capture', PcmCapture)
