import threading
import time

from audio_module import run_audio_analysis
from expression_module import run_expression_analysis
from nlp_analysis import run_nlp_analysis

# ── Weights (UPDATED) ─────────────────────────────────────────
W_AUDIO = 0.35
W_EXPRESSION = 0.35
W_NLP = 0.30   

DURATION = 25
TOPIC = "General Interview"


def run_analysis(duration: int = DURATION, topic: str = TOPIC):

    results = {
        "audio_score": 0, "audio_metrics": {}, "transcript": "",
        "expression_score": 0, "expression_metrics": {},
        "nlp_score": 0, "nlp_metrics": {},
        "nlp_feedback": "",   # 🔥 NEW
        "final_score": 0,
        "errors": [],
    }

    # ── AUDIO THREAD ─────────────────────────────────────────
    def _audio():
        try:
            s, m, t = run_audio_analysis(duration)
            results["audio_score"] = s
            results["audio_metrics"] = m
            results["transcript"] = t
            print("🔊 Audio Analysis Completed")
        except Exception as e:
            results["errors"].append(f"Audio: {e}")

    # ── EXPRESSION THREAD ────────────────────────────────────
    def _expression():
        try:
            s, m = run_expression_analysis(duration)
            results["expression_score"] = s
            results["expression_metrics"] = m
            print("📷 Expression Analysis Completed")
        except Exception as e:
            results["errors"].append(f"Expression: {e}")

    print("\n🔊 Audio Analysis Started...")
    print("📷 Expression Analysis Started...")

    t1 = threading.Thread(target=_audio, daemon=True)
    t2 = threading.Thread(target=_expression, daemon=True)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # ── NLP PHASE (FIXED) ────────────────────────────────────
    print("\n🧠 NLP Analysis Started...")

    try:
        s, m, feedback = run_nlp_analysis(results["transcript"])
        results["nlp_score"] = s
        results["nlp_metrics"] = m
        results["nlp_feedback"] = feedback
        print("🧠 NLP Analysis Completed")
    except Exception as e:
        results["errors"].append(f"NLP: {e}")

    # ── FINAL SCORE ─────────────────────────────────────────
    results["final_score"] = int(
        W_AUDIO * results["audio_score"] +
        W_EXPRESSION * results["expression_score"] +
        W_NLP * results["nlp_score"]
    )

    return results


def print_report(results: dict, total_time: float):

    final = results["final_score"]

    print("\n" + "="*42)
    print("  FINAL INTERVIEW PERFORMANCE REPORT")
    print("="*42)

    for module, score_key, metrics_key in [
        ("🔊 AUDIO", "audio_score", "audio_metrics"),
        ("📷 EXPRESSION", "expression_score", "expression_metrics"),
        ("🧠 NLP", "nlp_score", "nlp_metrics"),
    ]:
        print(f"\n{module} ANALYSIS")
        print(f"  Score: {results[score_key]}/100")
        for k, v in results[metrics_key].items():
            print(f"  {k}: {v}")

    # 🔥 AI FEEDBACK (NEW FEATURE)
    if results.get("nlp_feedback"):
        print("\n💬 AI FEEDBACK:")
        print(f"  {results['nlp_feedback']}")

    print(f"\n{'─'*42}")
    print(f"  FINAL SCORE: {final}/100")

    if final >= 85:
        print("  🏆 Outstanding Performance!")
    elif final >= 70:
        print("  👍 Strong Performance")
    elif final >= 55:
        print("  ⚠ Decent — needs improvement")
    else:
        print("  ⚠ Significant improvement required")

    if results["errors"]:
        print(f"\n⚠ Errors: {', '.join(results['errors'])}")

    print(f"\n⏱ Total time: {total_time}s")
    print("="*42)


if __name__ == "__main__":
    print("\n" + "="*42)
    print("  AI INTERVIEW ANALYZER STARTED")
    print("="*42)

    t0 = time.time()
    results = run_analysis(duration=DURATION, topic=TOPIC)
    print_report(results, round(time.time() - t0, 2))