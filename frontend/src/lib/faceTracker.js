// MediaPipe Face Landmarker, running fully in the browser. Video never leaves the
// device: we only turn each frame into a handful of numbers (smile, blink, head
// pose, gaze) and send those.
const WASM_PATH = '/mediapipe/wasm'
const MODEL_PATH = '/mediapipe/face_landmarker.task'

const wrapPitch = (p) => {
  while (p > 90) p -= 180
  while (p < -90) p += 180
  return p
}
const avg = (a, b) => ((a ?? 0) + (b ?? 0)) / 2

export async function createFaceTracker() {
  const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision')
  const fileset = await FilesetResolver.forVisionTasks(WASM_PATH)
  const make = (delegate) =>
    FaceLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: MODEL_PATH, delegate },
      runningMode: 'VIDEO',
      numFaces: 1,
      outputFaceBlendshapes: true,
      outputFacialTransformationMatrixes: true,
    })
  let landmarker
  try {
    landmarker = await make('GPU')
  } catch {
    landmarker = await make('CPU')
  }

  let lastTs = 0
  return {
    /** Returns one compact sample for the current video frame. */
    sample(video, tSec) {
      const ts = Math.max(performance.now(), lastTs + 1) // must be strictly increasing
      lastTs = ts
      const res = landmarker.detectForVideo(video, ts)
      if (!res.faceLandmarks?.length) return { t: tSec, v: 0 }

      const bs = {}
      for (const c of res.faceBlendshapes?.[0]?.categories ?? []) bs[c.categoryName] = c.score

      let yw = 0
      let pt = 0
      const m = res.facialTransformationMatrixes?.[0]?.data // 4x4, column-major
      if (m) {
        const r = (i, j) => m[j * 4 + i]
        yw = (Math.atan2(-r(2, 0), Math.hypot(r(0, 0), r(1, 0))) * 180) / Math.PI
        pt = wrapPitch((Math.atan2(r(2, 1), r(2, 2)) * 180) / Math.PI)
      }
      // + = looking to the person's right / up. Only offsets from calibration matter.
      const gx = (bs.eyeLookInLeft - bs.eyeLookOutLeft + (bs.eyeLookOutRight - bs.eyeLookInRight)) / 2 || 0
      const gy = (bs.eyeLookUpLeft + bs.eyeLookUpRight - bs.eyeLookDownLeft - bs.eyeLookDownRight) / 2 || 0
      const round = (x, d = 3) => Number((Number.isFinite(x) ? x : 0).toFixed(d))
      return {
        t: round(tSec, 2),
        v: 1,
        sm: round(avg(bs.mouthSmileLeft, bs.mouthSmileRight)),
        bl: round(avg(bs.eyeBlinkLeft, bs.eyeBlinkRight)),
        yw: round(yw, 1),
        pt: round(pt, 1),
        gx: round(gx),
        gy: round(gy),
      }
    },
    close() {
      landmarker.close()
    },
  }
}
