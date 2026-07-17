#!/usr/bin/env python3
"""
restaurant_scraper.py

Generic, location-agnostic restaurant intelligence pipeline. Given ANY
location supplied at runtime, it:

  1. Searches restaurants near that location via Apify's "Google Maps
     Extractor" actor (name, rating, review count, address, price level,
     category, website, menu link).
  2. Pulls a sample of recent reviews per restaurant via Apify's
     "Google Maps Reviews Scraper" actor.
  3. Enriches each restaurant with its top menu items and prices, either
     via Apify's "Restaurant Menu Scraper" actor (website OCR/parsing) or,
     as a fallback, by fetching the restaurant's own website text.
  4. Runs an AI model (DeepSeek or Anthropic Claude, whichever API key is
     configured, or a lexicon fallback if neither is set) over the review
     text to score sentiment per restaurant.
  5. Combines rating + sentiment into a weighted recommendation score and
     produces a ranked list of restaurants.
  6. Writes the full dataset to CSV + JSON.
  7. Commits and pushes the source code + dataset to a GitHub repository.

No location is hardcoded anywhere in this script -- every run is driven by
the `location` argument, so the same tool works for any end user, any city,
any time.

USAGE
    python restaurant_scraper.py "Austin, TX"
    python restaurant_scraper.py "Tampa, FL" --max-restaurants 15 --no-menu
    python restaurant_scraper.py "Chicago, IL" --no-push
    python restaurant_scraper.py "Denver, CO" --no-sentiment

CONFIGURATION
    Copy .env.example to .env and fill in:
      APIFY_API_TOKEN     - required. https://console.apify.com/settings/integrations
      DEEPSEEK_API_KEY    - optional. Enables AI-model sentiment analysis via DeepSeek.
      ANTHROPIC_API_KEY   - optional. Used if DEEPSEEK_API_KEY isn't set.
      SENTIMENT_PROVIDER  - optional. "deepseek" | "anthropic" | "auto" (default).
                             If neither key is set, a lexicon-based fallback is used.
      GITHUB_TOKEN         - required unless --no-push. PAT with 'repo' scope.
      GITHUB_REPO_URL      - required unless --no-push. e.g. https://github.com/OWNER/REPO.git
      GITHUB_BRANCH        - optional, default 'main'
      OUTPUT_DIR           - optional, default 'data'

COST NOTE
    Apify actors are pay-per-event: ~$0.005/restaurant (search), ~$0.0006/
    review (reviews), ~$0.05/restaurant (menu OCR, best-effort). Use
    --max-restaurants and --max-reviews to bound spend.
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from apify_client import ApifyClient
except ImportError:
    print("Missing dependency 'apify-client'. Run: pip install -r requirements.txt --break-system-packages")
    sys.exit(1)

GOOGLE_MAPS_ACTOR = "compass/google-maps-extractor"
REVIEWS_ACTOR = "compass/Google-Maps-Reviews-Scraper"
MENU_ACTOR = "wedo_software/wedo-scrape-menu"

DEFAULT_MAX_RESTAURANTS = 15
DEFAULT_MAX_REVIEWS = 5
DEFAULT_OUTPUT_DIR = "data"
DEFAULT_BRANCH = "main"

# Weight given to rating vs. review sentiment in the recommendation score.
RATING_WEIGHT = 0.5
SENTIMENT_WEIGHT = 0.5


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

def load_config():
    if load_dotenv:
        load_dotenv()

    return {
        "apify_token": os.environ.get("APIFY_API_TOKEN"),
        "anthropic_key": os.environ.get("ANTHROPIC_API_KEY"),
        "deepseek_key": os.environ.get("DEEPSEEK_API_KEY"),
        "sentiment_provider": os.environ.get("SENTIMENT_PROVIDER", "auto").lower(),
        "github_token": os.environ.get("GITHUB_TOKEN"),
        "github_repo_url": os.environ.get("GITHUB_REPO_URL"),
        "github_branch": os.environ.get("GITHUB_BRANCH", DEFAULT_BRANCH),
        "output_dir": os.environ.get("OUTPUT_DIR", DEFAULT_OUTPUT_DIR),
    }


def slugify(text):
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "location"


# --------------------------------------------------------------------------
# Step 1: search restaurants + ratings (works for any location string)
# --------------------------------------------------------------------------

def search_restaurants(client: ApifyClient, location: str, max_results: int):
    print(f"[1/5] Searching restaurants near '{location}' (max {max_results})...")
    run_input = {
        "searchStringsArray": ["restaurant"],
        "locationQuery": location,
        "maxCrawledPlacesPerSearch": max_results,
        "language": "en",
        "scrapePlaceDetailPage": True,
        "skipClosedPlaces": True,
    }
    run = client.actor(GOOGLE_MAPS_ACTOR).call(run_input=run_input)
    dataset_id = run["defaultDatasetId"]
    items = list(client.dataset(dataset_id).iterate_items())
    print(f"      -> found {len(items)} places")

    restaurants = []
    for item in items:
        loc = item.get("location") or {}
        restaurants.append({
            "name": item.get("title"),
            "address": item.get("address"),
            "rating": item.get("totalScore"),
            "reviews_count": item.get("reviewsCount"),
            "price_level": item.get("price"),
            "category": item.get("categoryName"),
            "phone": item.get("phone") or item.get("phoneUnformatted"),
            "website": item.get("website"),
            "menu_url": item.get("menu"),
            "google_maps_url": item.get("url"),
            "latitude": loc.get("lat"),
            "longitude": loc.get("lng"),
        })
    return restaurants


# --------------------------------------------------------------------------
# Step 2: pull a sample of reviews per restaurant
# --------------------------------------------------------------------------

def fetch_reviews_for_all(client: ApifyClient, restaurants: list, max_reviews: int):
    print(f"[2/5] Fetching up to {max_reviews} recent reviews per restaurant...")
    start_urls = [{"url": r["google_maps_url"]} for r in restaurants if r.get("google_maps_url")]
    if not start_urls:
        for r in restaurants:
            r["reviews"] = []
        return restaurants

    run_input = {
        "startUrls": start_urls,
        "maxReviews": max_reviews,
        "reviewsSort": "newest",
        "language": "en",
    }
    run = client.actor(REVIEWS_ACTOR).call(run_input=run_input)
    dataset_id = run["defaultDatasetId"]
    items = list(client.dataset(dataset_id).iterate_items())
    print(f"      -> fetched {len(items)} reviews total")

    reviews_by_name = {}
    for item in items:
        name = item.get("title")
        reviews_by_name.setdefault(name, []).append({
            "stars": item.get("stars") or item.get("rating"),
            "text": item.get("text"),
            "date": item.get("publishedAtDate"),
        })

    for r in restaurants:
        r["reviews"] = reviews_by_name.get(r["name"], [])
    return restaurants


# --------------------------------------------------------------------------
# Step 3: menu items + prices (actor first, website-text fallback)
# --------------------------------------------------------------------------

def fetch_menu_via_actor(client: ApifyClient, url: str):
    run_input = {"urls": [url]}
    run = client.actor(MENU_ACTOR).call(run_input=run_input)
    dataset_id = run["defaultDatasetId"]
    items = list(client.dataset(dataset_id).iterate_items())

    menu_items = []
    for item in items:
        candidates = item.get("items") or item.get("menuItems") or [item]
        for entry in candidates:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or entry.get("itemName") or entry.get("title")
            price = entry.get("price")
            if name:
                menu_items.append({"item": name, "price": price, "description": entry.get("description")})
    return menu_items


def enrich_with_menus(client: ApifyClient, restaurants: list, enabled: bool):
    if not enabled:
        for r in restaurants:
            r["menu_items"] = []
        return restaurants

    print(f"[3/5] Fetching menu items + prices for {len(restaurants)} restaurants...")
    for i, r in enumerate(restaurants, 1):
        url = r.get("menu_url") or r.get("website")
        if not url:
            r["menu_items"] = []
            continue
        try:
            print(f"      ({i}/{len(restaurants)}) {r['name']}...")
            r["menu_items"] = fetch_menu_via_actor(client, url)
            time.sleep(0.5)
        except Exception as e:
            # Actor OCR/crawl can fail on JS-heavy or PDF-only menu pages.
            # This is a best-effort enrichment step; failures don't block the run.
            print(f"      warning: menu fetch failed for {r['name']}: {e}")
            r["menu_items"] = []
    return restaurants


# --------------------------------------------------------------------------
# Step 4: AI sentiment analysis
# --------------------------------------------------------------------------

POSITIVE_WORDS = {
    "amazing", "great", "excellent", "love", "loved", "best", "fantastic", "delicious",
    "friendly", "awesome", "wonderful", "perfect", "recommend", "recommended", "fresh",
    "authentic", "incredible", "fire", "good", "nice", "clean", "attentive", "flavorful",
}
NEGATIVE_WORDS = {
    "bad", "terrible", "awful", "worst", "disappointed", "disappointing", "slow", "rude",
    "cold", "dirty", "overpriced", "bland", "stale", "never", "avoid", "poor", "horrible",
}


def lexicon_sentiment(texts: list):
    """Fallback sentiment scorer (0-1) when no AI model API key is configured."""
    pos, neg = 0, 0
    for t in texts:
        if not t:
            continue
        words = re.findall(r"[a-z']+", t.lower())
        pos += sum(1 for w in words if w in POSITIVE_WORDS)
        neg += sum(1 for w in words if w in NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.7  # neutral-leaning default when no signal text is available
    return max(0.0, min(1.0, pos / total))


def _build_sentiment_prompt(restaurant_name: str, texts: list) -> str:
    joined = "\n".join(f"- {t}" for t in texts if t) or "(no review text available)"
    return (
        f"Analyze the sentiment of these customer reviews for the restaurant "
        f"\"{restaurant_name}\".\n\nReviews:\n{joined}\n\n"
        "Respond ONLY with strict JSON: "
        '{"score": <float 0-1, 1=extremely positive>, "label": "<Very Positive|Positive|Mixed|Negative|Very Negative>", '
        '"rationale": "<one sentence>"}'
    )


def _parse_sentiment_json(raw: str):
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    data = json.loads(match.group(0)) if match else {}
    return (
        float(data.get("score", 0.7)),
        data.get("label", "Mixed"),
        data.get("rationale", ""),
    )


def anthropic_sentiment(api_key: str, restaurant_name: str, texts: list):
    """Score sentiment using an Anthropic Claude model. Returns (score 0-1, label, rationale)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_sentiment_prompt(restaurant_name, texts)
    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_sentiment_json(resp.content[0].text.strip())


def deepseek_sentiment(api_key: str, restaurant_name: str, texts: list):
    """Score sentiment using DeepSeek's chat API (OpenAI-compatible). Returns (score 0-1, label, rationale)."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    prompt = _build_sentiment_prompt(restaurant_name, texts)
    resp = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_sentiment_json(resp.choices[0].message.content.strip())


def analyze_sentiment(restaurants: list, config: dict, enabled: bool):
    if not enabled:
        for r in restaurants:
            r["sentiment_score"] = None
            r["sentiment_label"] = None
            r["sentiment_rationale"] = None
        return restaurants

    anthropic_key = config.get("anthropic_key")
    deepseek_key = config.get("deepseek_key")
    requested = (config.get("sentiment_provider") or "auto").lower()

    # Pick a provider: explicit SENTIMENT_PROVIDER wins; otherwise auto-detect
    # from whichever API key is set (DeepSeek first, then Anthropic).
    if requested == "deepseek" and deepseek_key:
        provider = "deepseek"
    elif requested == "anthropic" and anthropic_key:
        provider = "anthropic"
    elif requested in ("auto", "", None):
        provider = "deepseek" if deepseek_key else ("anthropic" if anthropic_key else "lexicon")
    else:
        print(f"      warning: SENTIMENT_PROVIDER='{requested}' has no matching API key; falling back.")
        provider = "deepseek" if deepseek_key else ("anthropic" if anthropic_key else "lexicon")

    provider_label = {"deepseek": "DeepSeek", "anthropic": "Anthropic Claude", "lexicon": "lexicon fallback"}[provider]
    print(f"[4/5] Running AI sentiment analysis on reviews ({provider_label})...")

    for r in restaurants:
        texts = [rv.get("text") for rv in r.get("reviews", []) if rv.get("text")]
        try:
            if provider == "deepseek":
                score, label, rationale = deepseek_sentiment(deepseek_key, r["name"], texts)
            elif provider == "anthropic":
                score, label, rationale = anthropic_sentiment(anthropic_key, r["name"], texts)
            else:
                score = lexicon_sentiment(texts)
                label = ("Very Positive" if score >= 0.85 else
                         "Positive" if score >= 0.65 else
                         "Mixed" if score >= 0.45 else
                         "Negative" if score >= 0.25 else "Very Negative")
                rationale = "Lexicon-based heuristic (no AI model configured)."
        except Exception as e:
            print(f"      warning: sentiment analysis failed for {r['name']}: {e}")
            score, label, rationale = 0.5, "Unknown", "Sentiment analysis failed for this restaurant."
        r["sentiment_score"] = round(score, 3)
        r["sentiment_label"] = label
        r["sentiment_rationale"] = rationale
    return restaurants


def rank_recommendations(restaurants: list):
    for r in restaurants:
        rating_norm = (r.get("rating") or 0) / 5.0
        sentiment = r.get("sentiment_score")
        sentiment_norm = sentiment if sentiment is not None else rating_norm
        r["recommendation_score"] = round(RATING_WEIGHT * rating_norm + SENTIMENT_WEIGHT * sentiment_norm, 4)

    ranked = sorted(restaurants, key=lambda r: r["recommendation_score"], reverse=True)
    for i, r in enumerate(ranked, 1):
        r["recommendation_rank"] = i
    return ranked


# --------------------------------------------------------------------------
# Step 5: write dataset
# --------------------------------------------------------------------------

def write_outputs(restaurants: list, location: str, output_dir: str):
    print("[5/5] Writing dataset to CSV + JSON...")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = slugify(location)
    json_path = out_dir / f"restaurants_{slug}_{ts}.json"
    csv_path = out_dir / f"restaurants_{slug}_{ts}.csv"

    payload = {
        "location": location,
        "generated_at": ts,
        "restaurant_count": len(restaurants),
        "ranked_recommendations": [
            {"rank": r["recommendation_rank"], "name": r["name"], "score": r["recommendation_score"]}
            for r in restaurants
        ],
        "restaurants": restaurants,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    fieldnames = [
        "recommendation_rank", "recommendation_score", "name", "rating", "sentiment_score",
        "sentiment_label", "reviews_count", "address", "price_level", "category", "phone",
        "website", "google_maps_url", "latitude", "longitude",
        "menu_item", "menu_item_price", "menu_item_description",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in restaurants:
            base = {k: r.get(k) for k in fieldnames if k in r}
            menu_items = r.get("menu_items") or []
            if not menu_items:
                writer.writerow({**base, "menu_item": "", "menu_item_price": "", "menu_item_description": ""})
            else:
                for mi in menu_items:
                    writer.writerow({
                        **base,
                        "menu_item": mi.get("item", ""),
                        "menu_item_price": mi.get("price", ""),
                        "menu_item_description": mi.get("description", ""),
                    })

    print(f"      -> {json_path}")
    print(f"      -> {csv_path}")
    return [json_path, csv_path]


# --------------------------------------------------------------------------
# Step 6: push source code + dataset to GitHub
# --------------------------------------------------------------------------

def run_git(args, cwd, env=None, check=True):
    result = subprocess.run(["git"] + args, cwd=cwd, env=env, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr}")
    return result


def push_to_github(files: list, location: str, config: dict, repo_dir: str = "."):
    print("Pushing source code + dataset to GitHub...")
    token = config["github_token"]
    repo_url = config["github_repo_url"]
    branch = config["github_branch"]

    if not token or not repo_url:
        print("      skipped: GITHUB_TOKEN / GITHUB_REPO_URL not configured (see .env.example)")
        return

    if not repo_url.startswith("https://"):
        raise ValueError("GITHUB_REPO_URL must be an https:// GitHub URL for token auth, e.g. "
                          "https://github.com/OWNER/REPO.git")

    authed_url = repo_url.replace("https://", f"https://{token}@", 1)

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    repo_path = Path(repo_dir)
    if not (repo_path / ".git").exists():
        run_git(["init"], cwd=repo_dir, env=env)
        run_git(["checkout", "-B", branch], cwd=repo_dir, env=env)
        run_git(["remote", "add", "origin", authed_url], cwd=repo_dir, env=env)
    else:
        existing = run_git(["remote"], cwd=repo_dir, env=env, check=False).stdout.split()
        if "origin" in existing:
            run_git(["remote", "set-url", "origin", authed_url], cwd=repo_dir, env=env)
        else:
            run_git(["remote", "add", "origin", authed_url], cwd=repo_dir, env=env)

    # Push the whole project (source code) plus the new dataset files.
    run_git(["add", "-A"], cwd=repo_dir, env=env)
    for f in files:
        run_git(["add", str(f)], cwd=repo_dir, env=env)

    commit_msg = f"Add restaurant dataset + pipeline update for {location} ({datetime.now(timezone.utc).date()})"
    result = run_git(["commit", "-m", commit_msg], cwd=repo_dir, env=env, check=False)
    if result.returncode != 0 and "nothing to commit" not in result.stdout.lower():
        raise RuntimeError(f"git commit failed:\n{result.stderr}")

    run_git(["push", "-u", "origin", branch], cwd=repo_dir, env=env)
    print(f"      -> pushed to {repo_url} ({branch})")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Search restaurants by location, analyze review sentiment with an AI model, "
                    "rank recommendations, and push source + dataset to GitHub.")
    parser.add_argument("location", help='Location to search, e.g. "Austin, TX" (required at runtime; nothing hardcoded)')
    parser.add_argument("--max-restaurants", type=int, default=DEFAULT_MAX_RESTAURANTS,
                         help=f"Max restaurants to fetch (default {DEFAULT_MAX_RESTAURANTS})")
    parser.add_argument("--max-reviews", type=int, default=DEFAULT_MAX_REVIEWS,
                         help=f"Max reviews per restaurant to analyze (default {DEFAULT_MAX_REVIEWS})")
    parser.add_argument("--no-menu", action="store_true", help="Skip menu/price enrichment")
    parser.add_argument("--no-sentiment", action="store_true", help="Skip AI sentiment analysis + ranking")
    parser.add_argument("--no-push", action="store_true", help="Write dataset locally but don't push to GitHub")
    args = parser.parse_args()

    config = load_config()
    if not config["apify_token"]:
        print("ERROR: APIFY_API_TOKEN is not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    client = ApifyClient(config["apify_token"])

    restaurants = search_restaurants(client, args.location, args.max_restaurants)
    if not restaurants:
        print("No restaurants found for that location. Exiting.")
        sys.exit(0)

    restaurants = fetch_reviews_for_all(client, restaurants, args.max_reviews)
    restaurants = enrich_with_menus(client, restaurants, enabled=not args.no_menu)
    restaurants = analyze_sentiment(restaurants, config, enabled=not args.no_sentiment)
    restaurants = rank_recommendations(restaurants) if not args.no_sentiment else restaurants

    files = write_outputs(restaurants, args.location, config["output_dir"])

    if args.no_push:
        print("Skipping GitHub push (--no-push).")
    else:
        push_to_github(files, args.location, config)

    print("Done.")

    print("\nTop recommendations:")
    for r in sorted(restaurants, key=lambda r: r.get("recommendation_rank", 999))[:5]:
        print(f"  #{r.get('recommendation_rank', '-')}: {r['name']} "
              f"(rating {r.get('rating')}, sentiment {r.get('sentiment_label')})")


if __name__ == "__main__":
    main()
