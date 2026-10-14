from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

POSITIVE_THRESHOLD = 0.05
NEGATIVE_THRESHOLD = -0.05

# Created once and reused. It loads the word dictionary when first imported.
_analyzer = SentimentIntensityAnalyzer()


def vader_score(text: str) -> float:
    """Return VADER's compound score for a text, from -1.0 to +1.0."""
    if not text or not text.strip():
        return 0.0
    return _analyzer.polarity_scores(text)["compound"]


def vader_label(score: float) -> str:
    """Turn a compound score into positive, neutral or negative."""
    if score >= POSITIVE_THRESHOLD:
        return "positive"
    if score <= NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"