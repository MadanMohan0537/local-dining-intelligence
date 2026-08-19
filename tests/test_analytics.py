import json

from demo_data import demo_restaurants
from dining_analytics import category_opportunities, load_dataset, market_summary, ranked_restaurants


def test_market_analytics(tmp_path):
    path = tmp_path / "sample.json"
    data = demo_restaurants()
    path.write_text(json.dumps({"location":"Demo","restaurants":data}), encoding="utf-8")
    _, frame = load_dataset(path)
    summary = market_summary(frame)
    ranked = ranked_restaurants(frame)
    opportunities = category_opportunities(frame)
    assert summary["restaurants"] == len(data)
    assert ranked["intelligence_score"].is_monotonic_decreasing
    assert opportunities["opportunity_score"].between(0, 100).all()

