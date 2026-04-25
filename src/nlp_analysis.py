import re
from textblob import TextBlob

# Expected technical keywords
KEYWORDS = [
    "python",
    "machine learning",
    "data",
    "algorithm",
    "project",
    "experience",
    "model",
    "analysis"
]

# Common filler words
FILLER_WORDS = ["um", "uh", "like", "you know", "basically", "actually"]


def count_filler_words(text):
    text = text.lower()
    count = 0

    for word in FILLER_WORDS:
        count += text.count(word)

    return count


def keyword_score(text):
    text = text.lower()
    score = 0

    for word in KEYWORDS:
        if word in text:
            score += 1

    return score


def sentiment_score(text):
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity

    score = int((polarity + 1) * 50)
    return score


def sentence_clarity(text):

    sentences = re.split(r'[.!?]', text)
    sentences = [s for s in sentences if len(s.strip()) > 0]

    if len(sentences) == 0:
        return 0

    avg_length = sum(len(s.split()) for s in sentences) / len(sentences)

    if avg_length < 5:
        return 40
    elif avg_length < 12:
        return 70
    else:
        return 90


def run_nlp_analysis(answer):

    print("\n NLP Analysis Started...")

    filler = count_filler_words(answer)
    keyword = keyword_score(answer)
    sentiment = sentiment_score(answer)
    clarity = sentence_clarity(answer)

    filler_penalty = max(0, 20 - filler * 3)

    keyword_score_final = min(20, keyword * 5)

    final_score = int(
        sentiment * 0.4 +
        clarity * 0.3 +
        keyword_score_final * 2 +
        filler_penalty
    ) // 2

    metrics = {
        "Filler Words": filler,
        "Keyword Matches": keyword,
        "Sentiment Score": sentiment,
        "Clarity Score": clarity
    }

    print(" NLP Analysis Completed")

    return final_score, metrics