# Local Dining Intelligence

[![CI](https://github.com/MadanMohan0537/local-dining-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/MadanMohan0537/local-dining-intelligence/actions/workflows/ci.yml)

**Rank the restaurants in a local market and spot under-served cuisine categories from ratings, review volume, and review sentiment, using a documented formula instead of a black-box score.**

**Live demo:** <https://local-dining-intelligence.madanmohanlearning.workers.dev/>. It serves a **synthetic** six-restaurant Boston dataset. You can upload your own CSV or JSON, and the page scores that file in the browser.

> **CI status:** recorded runs fail at `pytest -q` with `ModuleNotFoundError: No module named 'demo_data'`. The command that passes is `python -m pytest -q`. See [Known CI failure](#known-ci-failure).

## Problem and who it's for

Someone deciding where to open a restaurant, which cuisine to add, or how a venue compares with its neighbors usually ends up scrolling map listings and reviews by hand. The intended users are small restaurant operators, local market researchers, and analysts who want a structured, repeatable first pass with the assumptions visible.

## Approach

Two parts:

1. **Python pipeline.** `restaurant_scraper.py` takes a free-form query such as "Indian restaurants in Frisco, TX", discovers places with Apify's Google Maps extractor, and collects a bounded sample of recent reviews (default 15 restaurants and 5 newest reviews each). Menu enrichment is a separate Apify actor and is best-effort: a failed menu fetch leaves `menu_items` empty. Sentiment is DeepSeek, Anthropic Claude, or a local lexicon fallback when no model key is set. The script then writes timestamped JSON and CSV. `dashboard.py` is a Streamlit app for exploring a saved export or the built-in sample.
2. **Cloudflare Worker dashboard.** `worker/index.js` serves the static page in `public/` plus `GET /health` and `GET /api/demo`. Uploaded files are parsed in the browser and are not sent to the Worker.

Two different scores are in the repo.

The **intelligence score** (0–100) is duplicated in `dining_analytics.py` (what Streamlit displays), `worker/index.js` (`/api/demo`), and the upload scorer in `public/index.html`. The weights match across those three copies:

| Restaurant intelligence score | Weight |
|---|---:|
| Normalized rating (rating / 5) | 45% |
| Review sentiment, or normalized rating when sentiment is missing | 40% |
| Review-volume confidence (review count capped at 500, then divided by 500) | 15% |

| Category opportunity score | Weight |
|---|---:|
| Observed review demand | 45% |
| Lower competitive saturation | 35% |
| Category quality gap (1 − average rating / 5) | 20% |

The scraper's exported **`recommendation_score`** is a different number, on a 0–1 scale: 50% normalized rating and 50% sentiment. Sentiment falls back to normalized rating when it is missing, including when `--no-sentiment` is set. That score does not use review volume.

These are directional research signals, not revenue or profitability forecasts.

## What exists today

Checked against this repository and the live deployment:

- Live Worker: `GET /` returns the dashboard, `GET /health` returns `{"status":"ok","runtime":"cloudflare-workers"}`, and `GET /api/demo` returns the six synthetic Boston restaurants with computed scores, a summary, and the disclaimer `Synthetic demo data; not production market research.` The names match `demo_data.py`.
- Browser upload in `public/index.html`: CSV or JSON (a top-level array, or an object with `restaurants`, `records`, or `data`). Files larger than 5 × 1024 × 1024 bytes are rejected. Analysis uses at most the first 10,000 rows. The page includes a CSV template download.
- `restaurant_scraper.py`: Apify discovery (`compass/google-maps-extractor`), recent reviews (`compass/Google-Maps-Reviews-Scraper`), menu enrichment (`wedo_software/wedo-scrape-menu`), three sentiment providers (DeepSeek, Anthropic Claude, lexicon), `recommendation_score` ranking, and timestamped JSON/CSV export. Flags include `--demo`, `--no-menu`, `--no-sentiment`, `--no-push`, `--max-restaurants`, and `--max-reviews`.
- `--demo` does not call Apify. It always loads the six built-in Boston restaurants, then still runs sentiment (the lexicon, when no model key is set), so exported sentiment can differ from the scores stored in `demo_data.py` and shown on the dashboards. The query is only the location label on that export.
- Streamlit (`dashboard.py`) defaults to **Built-in demo** and reads that sample through `dining_analytics.py`, so it shows the intelligence score rather than `recommendation_score`.
- Example JSON and CSV exports for Boston, MA and Frisco, TX in `data/` (two Boston files, one Frisco file).
- One analytics test, `tests/test_analytics.py` (`test_market_analytics`). `python -m pytest -q` reports `1 passed`.

## How success would be measured

No measured results are committed in this repository.

| Measure | Status |
|---|---|
| Analyst time for a first-pass competitive scan | Not yet measured |
| Agreement between the lexicon fallback and LLM sentiment on the same reviews | Not yet measured |
| Whether "opportunity" categories hold up against independent data (rent, foot traffic, delivery demand) | Not yet measured |

## Limitations

- The live demo uses six synthetic restaurants. It does not run a live search.
- A ranking describes the sample that was collected. Defaults are 15 restaurants and 5 reviews each. The files in `data/` are smaller samples (4 or 6 restaurants). That is not city-wide demand.
- The opportunity score ignores rent, labor, delivery demand, demographics, and foot traffic.
- LLM sentiment is an imperfect signal, so audit a sample of reviews before relying on it.
- Discovery and reviews come from Google Maps through Apify actors. The files in `data/` include restaurant listings, short review excerpts, and Google Maps links. Scraped Google Maps data is subject to the source's terms. Check those terms before redistributing it, and collect only what you need.
- Unless you pass `--no-push`, the scraper runs `git add -A`, commits, and pushes the project and the new dataset to `GITHUB_REPO_URL`. It skips that step when `GITHUB_TOKEN` or `GITHUB_REPO_URL` is unset. Pass `--no-push` unless you mean to publish.
- The intelligence-score weights are copied in three places. They match today; editing one file does not update the others.

## Known CI failure

`.github/workflows/ci.yml` installs `requirements.txt` and runs `pytest -q` on Python 3.11, then `python -m py_compile` on the four Python modules.

Every recorded CI run has failed (10 runs on `main`, latest on 2026-10-04). The earliest and the latest both stop here:

```text
tests/test_analytics.py:3: ModuleNotFoundError: No module named 'demo_data'
```

Bare `pytest` does not put the repository root on `sys.path`, so the test cannot import `demo_data`. `python -m pytest -q` does, and that command passed here (`1 passed` on Python 3.12.3). A `conftest.py`, a `pythonpath = .` pytest setting, or switching the workflow to `python -m pytest` would fix CI. Not fixed here.

## Quick start

Worker dashboard (Node.js 22 or newer; `wrangler` 4.124.0 declares `node >= 22`):

```bash
git clone https://github.com/MadanMohan0537/local-dining-intelligence.git
cd local-dining-intelligence
npm install
npm run check
npm run dev
```

`npm run check` is `node --check worker/index.js`. `npm run dev` is `wrangler dev` and, with this Wrangler version, serves the app at <http://localhost:8787> (`/health` and `/api/demo` included).

Python pipeline and Streamlit dashboard (Python 3.11 or newer; CI and the Dockerfile use 3.11):

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q                # 1 passed; bare pytest cannot import demo_data
streamlit run dashboard.py         # http://localhost:8501, opens on Built-in demo
python restaurant_scraper.py "Boston, MA" --demo --no-push
```

A live search needs `APIFY_API_TOKEN` in `.env` (see `.env.example`). Sentiment keys are optional. Pass `--no-push` unless GitHub publishing is configured and intended:

```bash
python restaurant_scraper.py "Indian restaurants in Frisco, TX" --max-restaurants 15 --max-reviews 5 --no-push
```

## Deployment

The dashboard deploys as a Cloudflare Worker. Config is `wrangler.jsonc`:

| Setting | Value |
|---|---|
| Worker name | `local-dining-intelligence` |
| Entry point | `worker/index.js` |
| Static assets | `public/`, bound as `ASSETS` |
| Routes handled in the Worker before assets | `/api/*`, `/health` |
| Secrets | None. The Worker only reads the `ASSETS` binding. |

Keep the Worker name `local-dining-intelligence`. That name is the host of the live dashboard at <https://local-dining-intelligence.madanmohanlearning.workers.dev/>.

From the repository root, with Wrangler authenticated to the Cloudflare account for this Worker (Node.js 22 or newer):

```bash
npx wrangler deploy
```

Wrangler loads `wrangler.jsonc` from the repo root and deploys that Worker directly.

## License

MIT. See [LICENSE](LICENSE).
