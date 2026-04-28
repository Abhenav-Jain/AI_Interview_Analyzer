import re
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"


def tokenize(text):
    return re.findall(r'\b\w+\b', text.lower())


def basic_fallback_score(text):
    words = tokenize(text)

    length_score = min(100, len(words) * 2)

    filler_penalty = sum(word in ["um", "uh", "like"] for word in words) * 5
    final = max(0, length_score - filler_penalty)

    return final


def call_mistral(answer):
    if not MISTRAL_API_KEY:
        print("❌ No API Key found")
        return None

    prompt = f"""
You are an expert interview evaluator.

Evaluate the following answer based on:
- Relevance & depth
- Communication clarity
- Technical keyword usage
- Filler words

Return ONLY valid JSON:
{{
  "score": number (0-100),
  "feedback": "short feedback",
  "confidence": number (0-100)
}}

Answer:
\"\"\"{answer}\"\"\"
"""

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "mistral-small",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    try:
        response = requests.post(
            MISTRAL_URL,
            headers=headers,
            json=data,
            timeout=10   # ⏱ important
        )

        if response.status_code != 200:
            print("❌ API Error:", response.text)
            return None

        res = response.json()
        content = res["choices"][0]["message"]["content"]

        # 🧠 SAFE JSON EXTRACTION
        start = content.find("{")
        end = content.rfind("}") + 1
        json_str = content[start:end]

        parsed = json.loads(json_str)

        return parsed

    except Exception as e:
        print("⚠️ Mistral failed:", e)
        return None


def run_nlp_analysis(answer):

    print("\n🔍 NLP Analysis Started...")

    if not answer or len(answer.strip()) == 0:
        return 0, {
            "Filler Words": 0,
            "Keyword Matches": 0,
            "Sentiment Score": 0,
            "Clarity Score": 0,
            "Confidence Score": 0
        }, "No answer detected."

    # 🔥 Try Mistral
    mistral_result = call_mistral(answer)

    if mistral_result:
        score = int(mistral_result.get("score", 50))
        confidence = int(mistral_result.get("confidence", 50))
        feedback = mistral_result.get("feedback", "Good answer")

        metrics = {
            "Filler Words": "-",
            "Keyword Matches": "-",
            "Sentiment Score": "-",
            "Clarity Score": "-",
            "Confidence Score": confidence
        }

        print("✅ Mistral NLP Analysis Completed")
        return score, metrics, feedback

    # 🧠 Fallback
    fallback_score = basic_fallback_score(answer)

    metrics = {
        "Filler Words": "-",
        "Keyword Matches": "-",
        "Sentiment Score": fallback_score,
        "Clarity Score": fallback_score,
        "Confidence Score": fallback_score
    }

    print("⚠️ Fallback NLP used")

    return fallback_score, metrics, "Basic evaluation applied. Improve clarity."