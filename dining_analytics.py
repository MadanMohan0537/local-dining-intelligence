import json
from pathlib import Path

import pandas as pd


def load_dataset(path: str | Path) -> tuple[dict, pd.DataFrame]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    restaurants = payload.get("restaurants", [])
    if not restaurants:
        raise ValueError("Dataset contains no restaurants")
    frame = pd.json_normalize(restaurants)
    for col in ("rating", "reviews_count", "sentiment_score", "recommendation_score", "latitude", "longitude"):
        if col not in frame:
            frame[col] = None
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["category"] = frame.get("category", pd.Series(dtype=str)).fillna("Other")
    frame["price_level"] = frame.get("price_level", pd.Series(dtype=str)).fillna("Unknown")
    return payload, frame


def latest_dataset(data_dir: str | Path = "data") -> Path:
    files = sorted(Path(data_dir).glob("restaurants_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError("No restaurant JSON dataset found")
    return files[0]


def market_summary(frame: pd.DataFrame) -> dict:
    return {
        "restaurants": int(len(frame)),
        "average_rating": round(float(frame["rating"].mean()), 2),
        "total_reviews": int(frame["reviews_count"].fillna(0).sum()),
        "average_sentiment": round(float(frame["sentiment_score"].mean()), 2),
        "categories": int(frame["category"].nunique()),
    }


def category_opportunities(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.groupby("category", dropna=False).agg(
        competitors=("name", "count"),
        average_rating=("rating", "mean"),
        total_reviews=("reviews_count", "sum"),
        average_sentiment=("sentiment_score", "mean"),
    ).reset_index()
    demand = grouped["total_reviews"] / max(float(grouped["total_reviews"].max()), 1)
    scarcity = 1 - (grouped["competitors"] - 1) / max(float(grouped["competitors"].max()), 1)
    quality_gap = 1 - grouped["average_rating"].fillna(0) / 5
    grouped["opportunity_score"] = (100 * (.45 * demand + .35 * scarcity + .20 * quality_gap)).round(1)
    return grouped.sort_values("opportunity_score", ascending=False)


def ranked_restaurants(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    rating = result["rating"].fillna(0) / 5
    sentiment = result["sentiment_score"].fillna(rating)
    confidence = (result["reviews_count"].fillna(0).clip(upper=500) / 500)
    result["intelligence_score"] = (100 * (.45 * rating + .40 * sentiment + .15 * confidence)).round(1)
    return result.sort_values(["intelligence_score", "reviews_count"], ascending=False)

