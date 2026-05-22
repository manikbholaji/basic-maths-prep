import csv
import pandas as pd
from app import analytics_module


def test_reprocess_sentiments_tmp(tmp_path):
    tmpfile = tmp_path / "tmp_conversations.csv"
    headers = ["timestamp", "user", "role", "message", "sentiment", "compound"]
    rows = [
        ["2025-01-01T00:00:00Z", "u1", "user", "I love this course", "", 0.0],
        ["2025-01-01T00:01:00Z", "u2", "user", "I hate the exam", "", 0.0],
        ["2025-01-01T00:02:00Z", "u3", "user", "It is a book", "", 0.0],
    ]
    with open(tmpfile, "w", encoding="utf-8", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    res = analytics_module.reprocess_sentiments(file_path=str(tmpfile))
    assert res.get("processed") == 3

    df = pd.read_csv(tmpfile)
    assert df.loc[0, "sentiment"] == "positive"
    assert df.loc[1, "sentiment"] == "negative"
    assert df.loc[2, "sentiment"] == "neutral"
