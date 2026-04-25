import cv2
import mediapipe as mp
import numpy as np
import time
from collections import deque
from deepface import DeepFace

def run_expression_analysis(duration=30):

    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    cap = cv2.VideoCapture(0)

    SMOOTHING = 8
    smile_buffer = deque(maxlen=SMOOTHING)
    movement_buffer = deque(maxlen=SMOOTHING)

    smile_values = []
    movement_values = []
    emotion_list = []

    prev_landmarks = None
    frame_count = 0
    start_time = time.time()

    def get_pixel(lm, w, h):
        return np.array([lm.x * w, lm.y * h])

    print("📷 Camera started...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.resize(frame, (640, 480))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        frame_count += 1

        if results.multi_face_landmarks:
            face = results.multi_face_landmarks[0]
            landmarks = face.landmark
            h, w, _ = frame.shape

            face_width = np.linalg.norm(
                get_pixel(landmarks[234], w, h) -
                get_pixel(landmarks[454], w, h)
            ) + 1e-6

            mouth_width = np.linalg.norm(
                get_pixel(landmarks[61], w, h) -
                get_pixel(landmarks[291], w, h)
            )

            smile_ratio = mouth_width / face_width
            smile_buffer.append(smile_ratio)
            smile_values.append(np.mean(smile_buffer))

            current_landmarks = np.array([(lm.x, lm.y) for lm in landmarks])

            if prev_landmarks is not None:
                movement = np.mean(
                    np.linalg.norm(current_landmarks - prev_landmarks, axis=1)
                )
                movement_buffer.append(movement)
                movement_values.append(np.mean(movement_buffer))

            prev_landmarks = current_landmarks

            if frame_count % 5 == 0:
                try:
                    emotion_result = DeepFace.analyze(
                        frame,
                        actions=['emotion'],
                        enforce_detection=False,
                        detector_backend='opencv'
                    )
                    emotion = emotion_result[0]['dominant_emotion']
                    emotion_list.append(emotion)
                except:
                    pass

        cv2.imshow("AI Interview Analyzer", frame)

        if time.time() - start_time > duration:
            break

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    avg_smile = np.mean(smile_values) if smile_values else 0
    smile_variance = np.var(smile_values) if smile_values else 0
    avg_movement = np.mean(movement_values) if movement_values else 0

    emotion_changes = sum(
        1 for i in range(1, len(emotion_list))
        if emotion_list[i] != emotion_list[i-1]
    )

    emotion_stability = 1 - (emotion_changes / (len(emotion_list)+1e-6))

    score = 50

    if 0.30 <= avg_smile <= 0.38:
        score += 15
    elif avg_smile < 0.28:
        score -= 10

    if smile_variance < 0.0005:
        score += 10
    elif smile_variance > 0.002:
        score -= 10

    if 0.003 <= avg_movement <= 0.012:
        score += 15
    elif avg_movement < 0.002:
        score -= 15

    score += emotion_stability * 20

    score = max(0, min(int(score), 100))

    metrics = {
        "avg_smile": round(avg_smile, 3),
        "smile_variance": round(smile_variance, 5),
        "avg_movement": round(avg_movement, 5),
        "emotion_stability": round(emotion_stability, 3)
    }

    return score, metrics
