// Copies MediaPipe's WASM runtime into public/ and downloads the face model once.
// Self-hosting both means no third-party CDN is needed at runtime (privacy + offline).
import { access, cp, mkdir, writeFile } from 'node:fs/promises'

const WASM_SRC = 'node_modules/@mediapipe/tasks-vision/wasm'
const OUT = 'public/mediapipe'
const MODEL = `${OUT}/face_landmarker.task`
const MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
const strict = process.env.REQUIRE_FACE_MODEL === '1'

const exists = (p) => access(p).then(() => true, () => false)

try {
  await mkdir(OUT, { recursive: true })
  if (await exists(WASM_SRC)) {
    await cp(WASM_SRC, `${OUT}/wasm`, { recursive: true })
  } else {
    console.warn('[setup-mediapipe] @mediapipe/tasks-vision not installed yet; skipping wasm copy')
  }
  if (!(await exists(MODEL))) {
    console.log('[setup-mediapipe] downloading face_landmarker.task (~4 MB)...')
    const res = await fetch(MODEL_URL)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    await writeFile(MODEL, Buffer.from(await res.arrayBuffer()))
  }
  console.log('[setup-mediapipe] ready')
} catch (err) {
  const msg = `[setup-mediapipe] could not fetch the face model: ${err.message}.\n` +
    `  Download it manually:\n  curl -L -o frontend/${MODEL} ${MODEL_URL}`
  if (strict) {
    console.error(msg)
    process.exit(1)
  }
  console.warn(msg + '\n  (The app still works: expression analysis is simply skipped without it.)')
}
