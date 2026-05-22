from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

def analyze_sentiment(text):
    if not text:
        return {"compound": 0.0, "label": "neutral"}
    scores = _analyzer.polarity_scores(text)
    compound = scores.get("compound", 0.0)
    if compound >= 0.05:
        label = "positive"
    elif compound <= -0.05:
        label = "negative"
    else:
        label = "neutral"
    return {"compound": compound, "label": label, "scores": scores}

if __name__ == "__main__":
    print(analyze_sentiment("I love this course!"))
