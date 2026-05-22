from app import sentiment


def test_analyze_sentiment_positive():
    r = sentiment.analyze_sentiment("I love this service, it's great!")
    assert isinstance(r, dict)
    assert r["label"] == "positive"
    assert r["compound"] > 0


def test_analyze_sentiment_negative():
    r = sentiment.analyze_sentiment("This is terrible and I hate it")
    assert r["label"] == "negative"
    assert r["compound"] < 0


def test_analyze_sentiment_neutral():
    r = sentiment.analyze_sentiment("It is a book.")
    assert r["label"] == "neutral"
    assert -0.05 <= r["compound"] <= 0.05
