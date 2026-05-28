import re
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

# ── Constants ────────────────────────────────────────────────────────────────
FILLER_WORDS = {
    "um", "uh", "umm", "uhh", "like", "you know", "basically",
    "actually", "literally", "sort of", "kind of", "i mean",
    "well", "right", "okay", "ok", "hmm"
}

INTERVIEW_KEYWORDS = {
    "experience", "project", "team", "challenge", "solution", "learned",
    "improved", "developed", "designed", "implemented", "managed", "led",
    "responsible", "achieved", "delivered", "collaborated", "analyzed",
    "skill", "result", "impact", "goal", "strategy", "approach", "decision",
    "problem", "process", "system", "data", "performance", "growth",
    "hobby", "interest", "passion", "background", "education", "study",
    "career", "work", "company", "role", "position"
}

POSITIVE_WORDS = {
    "good", "great", "excellent", "successful", "achieved", "improved",
    "happy", "proud", "confident", "best", "strong", "effective", "positive",
    "love", "enjoy", "passionate", "excited", "accomplished", "outstanding",
    "interesting", "fun", "amazing", "wonderful", "fantastic"
}

NEGATIVE_WORDS = {
    "bad", "poor", "failed", "difficult", "struggle", "hate", "worst",
    "weak", "wrong", "problem", "issue", "concern", "worried", "anxious",
    "confused", "frustrated", "disappointed", "stuck"
}


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def tokenize(text):
    return re.findall(r'\b\w+\b', text.lower())


def count_filler_words(text):
    text_lower = text.lower()
    count = 0
    for filler in FILLER_WORDS:
        count += len(re.findall(r'\b' + re.escape(filler) + r'\b', text_lower))
    return count


def count_keyword_matches(text):
    words = set(tokenize(text))
    matches = words & INTERVIEW_KEYWORDS
    return len(matches)


def calc_sentiment_score(text):
    words = tokenize(text)
    if not words:
        return 50

    pos = sum(1 for w in words if w in POSITIVE_WORDS)
    neg = sum(1 for w in words if w in NEGATIVE_WORDS)

    net = pos - neg
    score = 50 + (net * 5)
    return max(0, min(100, score))


def calc_clarity_score(text):
    words = tokenize(text)
    if not words:
        return 0

    sentences = [s for s in re.split(r'[.!?]+', text) if s.strip()]
    if sentences:
        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
        length_score = max(0, 100 - abs(avg_len - 14) * 4)
    else:
        # No sentence breaks (common with Vosk output) — score from word count
        length_score = min(100, len(words) * 1.5)

    filler_density = count_filler_words(text) / max(len(words), 1)
    filler_score = max(0, 100 - filler_density * 400)

    diversity = len(set(words)) / len(words)
    diversity_score = diversity * 100

    clarity = (length_score * 0.4) + (filler_score * 0.4) + (diversity_score * 0.2)
    return int(max(0, min(100, clarity)))


def basic_fallback_score(text):
    words = tokenize(text)
    length_score = min(100, len(words) * 2)
    filler_penalty = count_filler_words(text) * 5
    return max(0, length_score - filler_penalty)


# ═════════════════════════════════════════════════════════════════════════════
# Mistral — topic-aware and balanced
# ═════════════════════════════════════════════════════════════════════════════

def call_mistral(answer, topic="General Interview"):
    if not MISTRAL_API_KEY:
        print("❌ No API Key found")
        return None

    prompt = f"""You are a supportive but fair interview coach. Evaluate the candidate's answer to the interview question below.

INTERVIEW QUESTION/TOPIC:
"{topic}"

CANDIDATE'S SPOKEN ANSWER (transcribed from audio, may contain transcription errors):
\"\"\"{answer}\"\"\"

EVALUATION GUIDELINES:
- The answer is transcribed by an automatic speech-to-text system. IGNORE small grammar/transcription errors — focus on the actual content the candidate tried to communicate.
- Score generously when the candidate is clearly attempting to address the topic, even if imperfectly.
- Score 70+ if they address the topic with reasonable structure and clarity.
- Score 50-70 if they address the topic but lack depth or have some rambling.
- Score below 50 only if the answer is completely off-topic, very short, or incoherent.
- Confidence reflects how strongly the answer demonstrates the candidate's clarity of thought.

FEEDBACK STYLE:
- Start with 1 strength you noticed
- Then mention 1-2 specific improvements
- Be encouraging, not harsh
- Keep it under 60 words

Return ONLY valid JSON in this exact format:
{{
  "score": <number 0-100>,
  "feedback": "<your balanced feedback>",
  "confidence": <number 0-100>
}}
"""

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "mistral-small",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4
    }

    try:
        response = requests.post(
            MISTRAL_URL,
            headers=headers,
            json=data,
            timeout=15
        )

        if response.status_code != 200:
            print("❌ API Error:", response.text)
            return None

        res = response.json()
        content = res["choices"][0]["message"]["content"]

        start = content.find("{")
        end = content.rfind("}") + 1
        json_str = content[start:end]
        parsed = json.loads(json_str)

        return parsed

    except Exception as e:
        print("⚠️ Mistral failed:", e)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Main entry point — now accepts topic parameter
# ═════════════════════════════════════════════════════════════════════════════

def run_nlp_analysis(answer, topic="General Interview"):
    print(f"\n🔍 NLP Analysis Started... (topic: {topic})")

    if not answer or len(answer.strip()) == 0:
        return 0, {
            "Filler Words": 0,
            "Keyword Matches": 0,
            "Sentiment Score": 0,
            "Clarity Score": 0,
            "Confidence Score": 0
        }, "No answer detected. Please make sure your microphone is working."

    filler_count   = count_filler_words(answer)
    keyword_count  = count_keyword_matches(answer)
    sentiment      = calc_sentiment_score(answer)
    clarity        = calc_clarity_score(answer)

    mistral_result = call_mistral(answer, topic=topic)

    if mistral_result:
        score      = int(mistral_result.get("score", 50))
        confidence = int(mistral_result.get("confidence", 50))
        feedback   = mistral_result.get("feedback", "Good answer.")
        print(f"✅ Mistral NLP Analysis Completed (score={score})")
    else:
        score      = basic_fallback_score(answer)
        confidence = clarity
        feedback   = "Basic evaluation applied (LLM unavailable). Focus on clarity and reducing filler words."
        print("⚠️ Fallback NLP used")

    metrics = {
        "Filler Words":     filler_count,
        "Keyword Matches":  keyword_count,
        "Sentiment Score":  sentiment,
        "Clarity Score":    clarity,
        "Confidence Score": confidence
    }

    return score, metrics, feedback


if __name__ == "__main__":
    sample = (
        "So I am a final year engineering student and I love coding. "
        "In my free time I play chess and watch tech videos. "
        "I have built a few projects including this AI interview analyzer."
    )
    s, m, fb = run_nlp_analysis(sample, topic="Tell me about yourself")
    print("\nScore:", s)
    print("Metrics:", json.dumps(m, indent=2))
    print("Feedback:", fb)