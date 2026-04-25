import threading
import time

from audio_module import run_audio_analysis
from expression_module import run_expression_analysis
from nlp_analysis import run_nlp_analysis


# =====================================
# GLOBAL VARIABLES
# =====================================

transcript = ""

audio_score = 0
expression_score = 0
nlp_score = 0

audio_metrics = {}
expression_metrics = {}
nlp_metrics = {}

DURATION = 25


# =====================================
# THREAD FUNCTIONS
# =====================================

def run_audio():

    global audio_score, audio_metrics, transcript

    print("\n🔊 Audio Analysis Started...")

    audio_score, audio_metrics, transcript = run_audio_analysis(DURATION)

    print("🔊 Audio Analysis Completed")


def run_video():

    global expression_score, expression_metrics

    print("\n📷 Expression Analysis Started...")

    expression_score, expression_metrics = run_expression_analysis(DURATION)

    print("📷 Expression Analysis Completed")


def run_nlp():

    global nlp_score, nlp_metrics, transcript

    print("\n🧠 NLP Analysis Started...")

    nlp_score, nlp_metrics = run_nlp_analysis(transcript)

    print("🧠 NLP Analysis Completed")


# =====================================
# MAIN EXECUTION
# =====================================

if __name__ == "__main__":

    print("\n==============================")
    print(" AI INTERVIEW ANALYZER STARTED")
    print("==============================\n")

    start_time = time.time()

    # Run audio + video in parallel
    t1 = threading.Thread(target=run_audio)
    t2 = threading.Thread(target=run_video)

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    # Run NLP after transcript available
    run_nlp()

    total_time = round(time.time() - start_time, 2)

    # =====================================
    # FINAL SCORE CALCULATION
    # =====================================

    FINAL_WEIGHT_AUDIO = 0.4
    FINAL_WEIGHT_EXPRESSION = 0.4
    FINAL_WEIGHT_NLP = 0.2

    final_score = int(
        (FINAL_WEIGHT_AUDIO * audio_score) +
        (FINAL_WEIGHT_EXPRESSION * expression_score) +
        (FINAL_WEIGHT_NLP * nlp_score)
    )

    # =====================================
    # FINAL REPORT
    # =====================================

    print("\n======================================")
    print(" FINAL INTERVIEW PERFORMANCE REPORT")
    print("======================================")

    print("\n AUDIO ANALYSIS")
    print("------------------------------")
    print(f"Confidence Score: {audio_score}/100")

    for key, value in audio_metrics.items():
        print(f"{key}: {value}")

    print("\n EXPRESSION ANALYSIS")
    print("------------------------------")
    print(f"Confidence Score: {expression_score}/100")

    for key, value in expression_metrics.items():
        print(f"{key}: {value}")

    print("\n NLP ANALYSIS")
    print("------------------------------")
    print(f"Confidence Score: {nlp_score}/100")

    for key, value in nlp_metrics.items():
        print(f"{key}: {value}")

    print("\n OVERALL INTERVIEW SCORE")
    print("------------------------------")
    print(f"Final Score: {final_score}/100")

    if final_score >= 85:
        print("🏆 Outstanding Interview Performance!")
    elif final_score >= 70:
        print("👍 Strong Performance with minor improvements needed.")
    elif final_score >= 55:
        print("⚠ Decent, but needs structured improvement.")
    else:
        print("⚠ Significant improvement required.")

    print(f"\n⏱ Total Analysis Time: {total_time} seconds")

    print("\n✅ AI Interview Analysis Completed Successfully.")
