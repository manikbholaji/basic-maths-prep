import os
import csv
from datetime import datetime
import pandas as pd
import json
import threading
import time

from app import sentiment as sentiment_module

DATA_DIR = "data"
LOG_FILE = os.path.join(DATA_DIR, "conversations.csv")
os.makedirs(DATA_DIR, exist_ok=True)


def _ensure_log():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "user", "role", "message", "sentiment", "compound"])


def log_interaction(user, role, message, sentiment_label=None, compound=0.0, file_path: str = None):
    """Append an interaction to the CSV log.

    If `sentiment_label` is not provided, runs the sentiment analyzer automatically.
    """
    _ensure_log()
    # Automatically compute sentiment if not provided
    if (sentiment_label is None or sentiment_label == "") and message:
        try:
            s = sentiment_module.analyze_sentiment(message)
            sentiment_label = s.get("label")
            compound = s.get("compound", 0.0)
        except Exception:
            sentiment_label = sentiment_label or ""
            compound = compound or 0.0

    target = file_path or LOG_FILE
    # Ensure directory exists if a custom file_path used
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "a", encoding="utf-8", newline='') as f:
        writer = csv.writer(f)
        writer.writerow([datetime.utcnow().isoformat() + "Z", user, role, message, sentiment_label or "", compound])


def load_interactions(file_path: str = None):
    _ensure_log()
    target = file_path or LOG_FILE
    return pd.read_csv(target)


def prepare_interaction_trends(df=None):
    """Build a robust daily trends table for the analytics dashboard.

    Returns a dataframe with columns:
    - date
    - interactions
    - avg_compound
    - positive
    - negative
    - neutral
    """
    if df is None:
        df = load_interactions()

    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "interactions", "avg_compound", "positive", "negative", "neutral"])

    working = df.copy()
    if "timestamp" not in working.columns:
        return pd.DataFrame(columns=["date", "interactions", "avg_compound", "positive", "negative", "neutral"])

    working["ts"] = pd.to_datetime(working["timestamp"], errors="coerce", utc=True, format="mixed")
    working = working.dropna(subset=["ts"])
    if working.empty:
        return pd.DataFrame(columns=["date", "interactions", "avg_compound", "positive", "negative", "neutral"])

    if "compound" not in working.columns:
        working["compound"] = 0.0
    working["compound"] = pd.to_numeric(working["compound"], errors="coerce").fillna(0.0)

    if "sentiment" not in working.columns:
        working["sentiment"] = "unknown"
    working["sentiment"] = working["sentiment"].fillna("unknown").astype(str).str.lower()

    working["date"] = working["ts"].dt.tz_convert(None).dt.normalize()

    grouped = working.groupby("date", as_index=False).agg(
        interactions=("timestamp", "count"),
        avg_compound=("compound", "mean"),
    )

    sentiment_counts = (
        working.pivot_table(index="date", columns="sentiment", values="timestamp", aggfunc="count", fill_value=0)
        .reset_index()
    )

    trends = grouped.merge(sentiment_counts, on="date", how="left")
    for label in ["positive", "negative", "neutral"]:
        if label not in trends.columns:
            trends[label] = 0

    trends = trends.sort_values("date").reset_index(drop=True)
    trends["date"] = pd.to_datetime(trends["date"]).dt.date
    ordered_columns = ["date", "interactions", "avg_compound", "positive", "negative", "neutral"]
    for column in ordered_columns:
        if column not in trends.columns:
            trends[column] = 0 if column != "date" else pd.NaT
    return trends[ordered_columns]


def reprocess_sentiments(file_path: str = None, sentiment_fn=None, progress_callback=None):
    """Re-run sentiment analysis for all rows in the log and overwrite sentiment columns.

    Returns the number of rows processed and a simple breakdown.
    """
    target = file_path or LOG_FILE
    if sentiment_fn is None:
        sentiment_fn = sentiment_module.analyze_sentiment

    if not os.path.exists(target):
        return {"processed": 0}

    df = pd.read_csv(target)
    if "message" not in df.columns:
        return {"processed": 0}

    # Ensure sentiment column can accept string labels and compound is numeric
    if "sentiment" in df.columns and df["sentiment"].dtype != object:
        df["sentiment"] = df["sentiment"].astype(object)
    if "compound" in df.columns:
        df["compound"] = pd.to_numeric(df["compound"], errors="coerce").fillna(0.0)
    else:
        df["compound"] = 0.0

    processed = 0
    labels = {"positive": 0, "negative": 0, "neutral": 0, "unknown": 0}
    for idx, row in df.iterrows():
        try:
            msg = row.get("message") or ""
            s = sentiment_fn(msg)
            label = s.get("label") if isinstance(s, dict) else None
            compound = s.get("compound") if isinstance(s, dict) else 0.0
            df.at[idx, "sentiment"] = label or ""
            df.at[idx, "compound"] = compound if compound is not None else 0.0
            if label in labels:
                labels[label] += 1
            else:
                labels["unknown"] += 1
            processed += 1
            if progress_callback:
                try:
                    progress_callback(processed, len(df))
                except Exception:
                    pass
        except Exception:
            labels["unknown"] += 1

    # Overwrite the file
    df.to_csv(target, index=False, encoding='utf-8')

    # Write metadata about this reprocess run
    meta = {
        "last_run": datetime.utcnow().isoformat() + "Z",
        "processed": processed,
        "by_label": labels,
        "file": os.path.abspath(target),
    }
    try:
        meta_path = os.path.join(DATA_DIR, "reprocess_meta.json")
        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump(meta, mf)
    except Exception:
        pass

    return {"processed": processed, "by_label": labels}


def _run_reprocess_background(target, sentiment_fn=None):
    # internal helper to run reprocess and update metadata progressively
    meta_path = os.path.join(DATA_DIR, "reprocess_meta.json")
    try:
        # mark in-progress
        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump({"in_progress": True, "last_run": None, "processed": 0, "by_label": {}}, mf)
    except Exception:
        pass

    # run the actual reprocess
    res = reprocess_sentiments(file_path=target, sentiment_fn=sentiment_fn)

    # ensure meta written by reprocess_sentiments (it writes final meta)
    return res


def start_reprocess_background(file_path: str = None, sentiment_fn=None):
    """Start a background thread to run reprocessing. Returns the Thread object."""
    t = threading.Thread(target=_run_reprocess_background, args=(file_path, sentiment_fn), daemon=True)
    t.start()
    return t


def get_reprocess_meta():
    meta_path = os.path.join(DATA_DIR, "reprocess_meta.json")
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as mf:
            return json.load(mf)
    except Exception:
        return None


def simple_stats(df=None):
    if df is None:
        df = load_interactions()
    total = len(df)
    by_sent = df["sentiment"].value_counts().to_dict() if "sentiment" in df.columns else {}
    user_counts = df["user"].value_counts().head(10).to_dict()
    return {"total": total, "by_sentiment": by_sent, "top_users": user_counts}


if __name__ == "__main__":
    # demo
    log_interaction("student1", "user", "I need course advice")
    print(load_interactions().tail())
    print(simple_stats())
