import pandas as pd
from app import analytics_module


def test_prepare_interaction_trends_handles_mixed_timestamps():
    df = pd.DataFrame(
        {
            "timestamp": [
                "2026-05-19T10:00:00Z",
                "2026-05-19 15:30:00+00:00",
                "invalid timestamp",
                None,
                "2026-05-20T09:15:00Z",
            ],
            "sentiment": ["positive", "negative", "neutral", "positive", "positive"],
            "compound": [0.8, -0.4, 0.0, 0.2, 0.5],
        }
    )

    trends = analytics_module.prepare_interaction_trends(df)

    assert list(trends.columns) == ["date", "interactions", "avg_compound", "positive", "negative", "neutral"]
    assert len(trends) == 2
    assert trends.iloc[0]["interactions"] == 2
    assert trends.iloc[1]["interactions"] == 1
    assert abs(float(trends.iloc[0]["avg_compound"]) - 0.2) < 1e-9
    assert abs(float(trends.iloc[1]["avg_compound"]) - 0.5) < 1e-9


def test_prepare_interaction_trends_returns_empty_frame_when_no_valid_timestamps():
    df = pd.DataFrame({"timestamp": ["bad", None], "sentiment": ["positive", "negative"], "compound": [0.1, -0.1]})

    trends = analytics_module.prepare_interaction_trends(df)

    assert trends.empty
    assert list(trends.columns) == ["date", "interactions", "avg_compound", "positive", "negative", "neutral"]
