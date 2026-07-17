# Restaurant Intelligence → GitHub Automation

A generic tool — not tied to any one city. Every run asks the customer
which location they want (or accepts one as an argument), then:

1. Searches restaurants near that location via Apify's **Google Maps
   Extractor** actor and pulls name, rating, review count, address, price
   level, category, and menu link.
2. Pulls a sample of recent reviews per restaurant via Apify's **Google
   Maps Reviews Scraper** actor.
3. Enriches each restaurant with its top menu items and prices, via
   Apify's **Restaurant Menu Scraper** actor and/or the restaurant's own
   website (best-effort — some sites are JS-rendered or link a PDF menu
   and can't be machine-parsed every time).
4. Runs an **AI model** — DeepSeek or Anthropic Claude, whichever API key
   is configured (DeepSeek takes priority if both are set; override with
   `SENTIMENT_PROVIDER`), or a lexicon-based fallback if neither key is
   set — over the review text to score sentiment per restaurant.
5. Combines rating + sentiment into a weighted **recommendation score**
   and produces a ranked list.
6. Writes the full dataset to `data/` as both CSV and JSON.
7. Commits and pushes the source code + dataset to a GitHub repository.

No example dataset ships in this repo on purpose — `data/` fills up with
whatever locations your customers actually ask for, each run producing its
own timestamped, location-named files (see below).

## Setup

```bash
pip install -r requirements.txt --break-system-packages
cp .env.example .env
```

Fill in `.env`:

| Variable | Required | Notes |
|---|---|---|
| `APIFY_API_TOKEN` | yes | From [Apify Console > Settings > Integrations](https://console.apify.com/settings/integrations) |
| `DEEPSEEK_API_KEY` | no | Enables AI-model sentiment scoring via DeepSeek (`deepseek-chat`). Takes priority over Anthropic if both are set. |
| `ANTHROPIC_API_KEY` | no | Enables AI-model sentiment scoring via Claude. Used if no DeepSeek key is set. |
| `SENTIMENT_PROVIDER` | no | `anthropic`, `deepseek`, or `auto` (default) to force a provider. |
| `GITHUB_TOKEN` | for push | [Create a PAT](https://github.com/settings/tokens) with `repo` scope |
| `GITHUB_REPO_URL` | for push | HTTPS URL of an **empty** repo you've already created on GitHub, e.g. `https://github.com/yourname/restaurant-data.git` |
| `GITHUB_BRANCH` | no | Defaults to `main` |
| `OUTPUT_DIR` | no | Defaults to `data` |

The `.env` file is git-ignored, so your tokens never get committed.

## Usage

```bash
# Interactive: prompts "Which location should I search for restaurants in?"
python restaurant_scraper.py

# Or pass the customer's location directly (e.g. from another system)
python restaurant_scraper.py "Austin, TX"

# Bound cost / speed: fewer restaurants, fewer reviews, skip menu enrichment
python restaurant_scraper.py "Austin, TX" --max-restaurants 10 --max-reviews 3 --no-menu

# Skip AI sentiment analysis + ranking
python restaurant_scraper.py "Austin, TX" --no-sentiment

# Dry run: write local files only, don't push
python restaurant_scraper.py "Austin, TX" --no-push
```

The location is never hardcoded — every run is scoped to whatever the
customer asks for, whether typed in interactively or passed as an argument.

Each run produces timestamped files like:

```
data/restaurants_austin-tx_20260716T120000Z.json
data/restaurants_austin-tx_20260716T120000Z.csv
```

and pushes them with a commit message like
`Add restaurant dataset for Austin, TX (2026-07-16)`.

## How the GitHub push works

The script runs plain `git` commands under the hood:

- If the project folder isn't a git repo yet, it runs `git init` and adds
  `origin` pointing at `GITHUB_REPO_URL` (with your token embedded in the
  URL only in-memory — never logged or written to disk).
- Otherwise it refreshes the `origin` URL (in case the token rotated),
  stages the new CSV/JSON files, commits, and pushes.

**Caveat:** git stores the remote URL (including the embedded token) in
plaintext in `.git/config`. Don't commit that file elsewhere or share the
project folder as-is. For a more secure setup, use a git credential helper
or SSH remote instead and drop the token-in-URL approach in
`push_to_github()`.

If this is the first push, make sure git has an identity configured
(`git config --global user.name` / `user.email`), otherwise the commit
step will fail.

## Cost notes

Both Apify actors are pay-per-event:
- ~$0.005 per restaurant found (Google Maps Extractor)
- ~$0.05 per restaurant menu scraped (Restaurant Menu Scraper) — only runs
  when `--no-menu` is *not* passed, and only for restaurants with a website.

Use `--max-restaurants` to bound spend on a given run.

## Automating recurring runs

To run this on a schedule (e.g. daily for a given city), wire it up to a
cron job or CI scheduler that calls:

```bash
python restaurant_scraper.py "Austin, TX" --max-restaurants 20
```
