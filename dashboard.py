import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from demo_data import demo_restaurants
from dining_analytics import category_opportunities, latest_dataset, load_dataset, market_summary, ranked_restaurants

st.set_page_config(page_title="Local Dining Intelligence", page_icon="🍽️", layout="wide")
st.title("🍽️ Local Dining Intelligence")
st.caption("Restaurant discovery, customer sentiment, competitive benchmarking, and market-gap analysis")


def ensure_demo() -> Path:
    out = Path("data/demo_restaurants.json")
    if not out.exists():
        out.parent.mkdir(exist_ok=True)
        restaurants = demo_restaurants()
        out.write_text(json.dumps({"location":"Boston, MA (Demo)","search_term":"restaurant","generated_at":datetime.now(timezone.utc).isoformat(),"restaurant_count":len(restaurants),"restaurants":restaurants}, indent=2), encoding="utf-8")
    return out


mode = st.sidebar.radio("Data source", ["Latest saved dataset", "Built-in demo"], index=1)
uploaded = st.sidebar.file_uploader("Or upload an exported JSON dataset", type="json")
if uploaded:
    temp = Path("data/.uploaded.json")
    temp.parent.mkdir(exist_ok=True)
    temp.write_bytes(uploaded.getvalue())
    path = temp
elif mode == "Built-in demo":
    path = ensure_demo()
else:
    try:
        path = latest_dataset()
    except FileNotFoundError:
        st.warning("No scraped dataset exists yet, so the demo dataset is displayed.")
        path = ensure_demo()

payload, frame = load_dataset(path)
summary = market_summary(frame)
ranked = ranked_restaurants(frame)
opportunities = category_opportunities(frame)
st.subheader(payload.get("location", "Selected market"))

cols = st.columns(5)
cols[0].metric("Restaurants", summary["restaurants"])
cols[1].metric("Average rating", summary["average_rating"])
cols[2].metric("Customer reviews", f"{summary['total_reviews']:,}")
cols[3].metric("Sentiment", summary["average_sentiment"])
cols[4].metric("Categories", summary["categories"])

tabs = st.tabs(["Market Overview", "Restaurant Rankings", "Opportunity Finder", "Map & Compare"])
with tabs[0]:
    left, right = st.columns(2)
    with left:
        st.plotly_chart(px.scatter(ranked, x="reviews_count", y="rating", size="intelligence_score", color="category", hover_name="name", title="Quality vs. market traction"), use_container_width=True)
    with right:
        price = frame.groupby("price_level").size().reset_index(name="restaurants")
        st.plotly_chart(px.bar(price, x="price_level", y="restaurants", title="Competitive mix by price tier"), use_container_width=True)

with tabs[1]:
    show = [c for c in ["name","category","price_level","rating","reviews_count","sentiment_label","sentiment_score","intelligence_score","address"] if c in ranked]
    st.dataframe(ranked[show], use_container_width=True, hide_index=True)

with tabs[2]:
    st.write("A higher score combines customer demand, lower category saturation, and visible quality gaps. It is a directional research signal, not a revenue forecast.")
    st.dataframe(opportunities, use_container_width=True, hide_index=True)
    st.plotly_chart(px.bar(opportunities, x="category", y="opportunity_score", color="average_rating", title="Category opportunity signals"), use_container_width=True)

with tabs[3]:
    map_frame = frame.dropna(subset=["latitude", "longitude"])
    if not map_frame.empty:
        st.map(map_frame.rename(columns={"latitude":"lat", "longitude":"lon"})[["lat","lon"]])
    choices = st.multiselect("Compare restaurants", ranked["name"].tolist(), default=ranked["name"].head(2).tolist(), max_selections=4)
    if choices:
        compare = ranked[ranked["name"].isin(choices)]
        st.dataframe(compare[["name","rating","reviews_count","sentiment_score","intelligence_score","price_level","category"]], use_container_width=True, hide_index=True)

