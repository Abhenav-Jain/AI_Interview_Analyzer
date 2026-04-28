"""
expression_module.py — Improved
---------------------------------
Changes:
- DeepFace called every 15 frames (was 5) — 3x faster
- Eye contact detection added via MediaPipe iris landmarks
- Blink detection added
- Better score logic with eye contact as factor
"""

import cv2
import mediapipe as mp
import numpy as np
import time
from collections import deque
from deepface import DeepFace

SHOW_WINDOW = False


def run_expression_analysis(duration: int = 30):
    """
    Returns: (score: int, metrics: dict)
    """

    # ── MediaPipe setup ───────────────────────────────────────────────────────
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh    = mp_face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,        # needed for iris
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("❌ Camera not accessible")
        return 0, {
        "avg_smile": 0,
        "smile_variance": 0,
        "avg_movement": 0,
        "emotion_stability": 0,
        "eye_contact": 0,
        "blink_rate": 0,
        }

    # ── Buffers ───────────────────────────────────────────────────────────────
    SMOOTH        = 8
    smile_buf     = deque(maxlen=SMOOTH)
    movement_buf  = deque(maxlen=SMOOTH)

    smile_vals    = []
    movement_vals = []
    emotion_list  = []

    # Eye contact: iris vs eye corners
    eye_contact_frames = 0
    total_face_frames  = 0

    # Blink detection
    blink_count   = 0
    eye_open_prev = True

    prev_landmarks = None
    frame_count    = 0
    start_time     = time.time()

    def px(lm, w, h):
        return np.array([lm.x * w, lm.y * h])

    def ear(landmarks, indices, w, h):
        """Eye Aspect Ratio — used for blink detection."""
        pts = [px(landmarks[i], w, h) for i in indices]
        v1  = np.linalg.norm(pts[1] - pts[5])
        v2  = np.linalg.norm(pts[2] - pts[4])
        hor = np.linalg.norm(pts[0] - pts[3])
        return (v1 + v2) / (2.0 * hor + 1e-6)

    # MediaPipe eye landmark indices
    LEFT_EYE  = [362, 385, 387, 263, 373, 380]
    RIGHT_EYE = [33,  160, 158, 133, 153, 144]
    # Iris center indices (refine_landmarks=True)
    LEFT_IRIS  = 468
    RIGHT_IRIS = 473

    print("📷 Camera started...")

    while time.time() - start_time < duration:
        ret, frame = cap.read()
        if not ret:
            break

        frame   = cv2.resize(frame, (640, 480))
        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)
        frame_count += 1

        if results.multi_face_landmarks:
            face      = results.multi_face_landmarks[0]
            lms       = face.landmark
            h, w, _   = frame.shape
            total_face_frames += 1

            # ── Smile ratio ───────────────────────────────────────────────────
            face_w     = np.linalg.norm(px(lms[234], w, h) - px(lms[454], w, h)) + 1e-6
            mouth_w    = np.linalg.norm(px(lms[61],  w, h) - px(lms[291], w, h))
            smile_r    = mouth_w / face_w
            smile_buf.append(smile_r)
            smile_vals.append(float(np.mean(smile_buf)))

            # ── Head movement ─────────────────────────────────────────────────
            cur_lms = np.array([(lm.x, lm.y) for lm in lms])
            if prev_landmarks is not None:
                mv = np.mean(np.linalg.norm(cur_lms - prev_landmarks, axis=1))
                movement_buf.append(mv)
                movement_vals.append(float(np.mean(movement_buf)))
            prev_landmarks = cur_lms

            # ── Eye contact (iris position relative to eye corners) ───────────
            try:
                nose_tip = px(lms[1], w, h)
                left_iris  = px(lms[LEFT_IRIS],  w, h)
                right_iris = px(lms[RIGHT_IRIS], w, h)

                left_inner  = px(lms[133], w, h)
                left_outer  = px(lms[33],  w, h)
                right_inner = px(lms[362], w, h)
                right_outer = px(lms[263], w, h)

                def iris_ratio(iris, inner, outer):
                    total = np.linalg.norm(outer - inner) + 1e-6
                    dist  = np.linalg.norm(iris - inner)
                    return dist / total

                lr = iris_ratio(left_iris,  left_inner,  left_outer)
                rr = iris_ratio(right_iris, right_inner, right_outer)
                avg_ratio = (lr + rr) / 2

                # Centered iris ratio ≈ 0.4–0.6 means looking at camera
                if 0.38 <= avg_ratio <= 0.62:
                    eye_contact_frames += 1
            except Exception:
                pass

            # ── Blink detection ───────────────────────────────────────────────
            try:
                left_ear  = ear(lms, LEFT_EYE,  w, h)
                right_ear = ear(lms, RIGHT_EYE, w, h)
                avg_ear   = (left_ear + right_ear) / 2
                eye_open  = avg_ear > 0.2
                if eye_open_prev and not eye_open:
                    blink_count += 1
                eye_open_prev = eye_open
            except Exception:
                pass

            # ── DeepFace emotion (every 30 frames for speed) ─────────────────
            if frame_count % 30 == 0:
                try:
                    res     = DeepFace.analyze(frame, actions=["emotion"],
                                               enforce_detection=False,
                                               detector_backend="opencv")
                    emotion = res[0]["dominant_emotion"]
                    emotion_list.append(emotion)
                except Exception:
                    pass
                  

        if SHOW_WINDOW:
            cv2.imshow("AI Interview Analyzer", frame)

        if time.time() - start_time > duration:
            break
        if SHOW_WINDOW and cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    if SHOW_WINDOW:
        cv2.destroyAllWindows()

    # ── Aggregates ────────────────────────────────────────────────────────────
    avg_smile      = float(np.mean(smile_vals))    if smile_vals    else 0.0
    smile_var      = float(np.var(smile_vals))     if smile_vals    else 0.0
    avg_movement   = float(np.mean(movement_vals)) if movement_vals else 0.0

    emotion_changes  = sum(1 for i in range(1, len(emotion_list))
                           if emotion_list[i] != emotion_list[i-1])
    emotion_stability = 1 - (emotion_changes / (len(emotion_list) + 1e-6))
    emotion_stability = max(0.0, min(1.0, float(emotion_stability)))

    eye_contact_ratio = (eye_contact_frames / total_face_frames
                         if total_face_frames > 0 else 0.0)

    # Blink rate: normal = 12-20 blinks/min
    blink_rate = blink_count / (duration / 60.0)

    # ── Scoring ───────────────────────────────────────────────────────────────
    score = 0

    # 1. Smile (natural range 0.30-0.38) — max 20pts
    if 0.28 <= avg_smile <= 0.42:
        score += 20
    elif avg_smile < 0.25:
        score += 5
    else:
        score += 12

    # 2. Smile consistency — max 15pts
    if smile_var < 0.0003:
        score += 15
    elif smile_var < 0.001:
        score += 10
    elif smile_var < 0.002:
        score += 5
    else:
        score += 0

    # 3. Head movement (natural engagement) — max 20pts
    if 0.003 <= avg_movement <= 0.012:
        score += 20
    elif avg_movement < 0.002:
        score += 5   # too still = nervous
    elif avg_movement <= 0.020:
        score += 12
    else:
        score += 3   # too much movement = distracted

    # 4. Emotion stability — max 18pts
    score += int(emotion_stability * 18)

    # 5. Eye contact — max 15pts (NEW)
    if eye_contact_ratio >= 0.7:
        score += 15
    elif eye_contact_ratio >= 0.5:
        score += 10
    elif eye_contact_ratio >= 0.3:
        score += 5
    else:
        score += 0

    # 6. Blink rate (10-25/min is natural) — max 10pts (NEW)
    if 10 <= blink_rate <= 25:
        score += 10
    elif 6 <= blink_rate < 10 or 25 < blink_rate <= 35:
        score += 5
    else:
        score += 0

    score = max(0, min(100, score))

    metrics = {
        "avg_smile":         round(avg_smile,         3),
        "smile_variance":    round(smile_var,          5),
        "avg_movement":      round(avg_movement,       5),
        "emotion_stability": round(emotion_stability,  3),
        "eye_contact":       round(eye_contact_ratio,  2),
        "blink_rate":        round(blink_rate,         1),
    }

    print(f"\n📷 Expression Score: {score}/100")
    return score, metrics
