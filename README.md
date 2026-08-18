# 🍽️ Local Dining Intelligence — Restaurant Analytics & Market Insights

<p align="center">
  <strong>Automated restaurant competitive intelligence pipeline combining Apify Google Maps scraping with LLM sentiment analysis & automated GitHub syncing.</strong>
</p>

<p align="center">
  <a href="#license"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License"></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/Python-3.10%2B-3776ab?style=flat-square" alt="Python"></a>
  <a href="https://apify.com"><img src="https://img.shields.io/badge/Data%20Extraction-Apify-00a878?style=flat-square" alt="Apify"></a>
  <a href="https://deepseek.com"><img src="https://img.shields.io/badge/LLM-DeepSeek%20%2F%20Claude-blueviolet?style=flat-square" alt="LLM"></a>
</p>

---

## 📌 Overview

**Local Dining Intelligence** is a location-agnostic market analysis engine. Given any geographic location, neighborhood, or city, the system orchestrates a multi-step data enrichment pipeline:

1. **Google Maps Venue Discovery:** Extracts restaurant metadata (names, address, price levels, review counts, average ratings, website).
2. **Review & Menu Scraper:** Ingests recent customer reviews and extracts structured menu offerings and pricing via Apify actors.
3. **LLM Aspect Sentiment Engine:** Scores customer sentiment across food quality, service speed, hospitality, ambiance, and price-to-value using **DeepSeek** or **Anthropic Claude**.
4. **Weighted Recommendation Ranking:** Combines composite rating with sentiment signals to calculate a unified recommendation score.
5. **Automated Export & Git Sync:** Generates timestamped JSON and CSV datasets and automatically commits/pushes the data to GitHub.

---

## 🏗️ Data Pipeline

```mermaid
flowchart LR
    A[Target Location] --> B[Apify Google Maps Extractor]
    B --> C[Reviews & Menu Scraper]
    C --> D[LLM Sentiment Analysis<br>DeepSeek / Claude]
    D --> E[Recommendation Scoring Engine]
    E --> F[Timestamped CSV & JSON Exports]
    F --> G[Automated GitHub Push]
```

---

## ✨ Key Features

- **📍 Dynamic Geographic Querying:** Run on any location (e.g. `"Seattle, WA"`, `"Austin, TX"`, `"Brooklyn, NY"`) via interactive prompt or CLI arguments.
- **🧠 Multi-Aspect Sentiment Scoring:** Evaluates food quality, service, ambiance, and price satisfaction separately rather than relying on a flat star rating.
- **⚡ Flexible LLM Provider:** Supports **DeepSeek** (`deepseek-chat`), **Anthropic Claude**, or a built-in lexicon fallback.
- **📊 Dual Format Outputs:** Writes normalized data to both `data/*.json` and `data/*.csv`.
- **🔄 Headless CI/CD Automation:** Built-in git automation to push datasets automatically for scheduled cron jobs.

---

## 🚀 Quick Start

### Prerequisites
- **Python:** 3.10 or higher
- **Apify API Token:** ([Get Apify Token](https://console.apify.com/settings/integrations))
- **AI API Key:** DeepSeek API Key or Anthropic Claude API Key

### Installation

```bash
# Clone the repository
git clone https://github.com/MadanMohan0537/local-dining-intelligence.git
cd local-dining-intelligence

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

Fill in `.env`:
```ini
APIFY_API_TOKEN=your_apify_token_here
DEEPSEEK_API_KEY=your_deepseek_key_here
# Optional: ANTHROPIC_API_KEY, GITHUB_TOKEN, GITHUB_REPO_URL
```

### Usage

```bash
# Interactive run (prompts for location)
python restaurant_scraper.py

# Direct location search
python restaurant_scraper.py "Seattle, WA"

# Bounded search with limit and fast execution
python restaurant_scraper.py "Seattle, WA" --max-restaurants 15 --max-reviews 5 --no-menu

# Dry run (saves files locally, skips git push)
python restaurant_scraper.py "Seattle, WA" --no-push
```

---

## 🛠️ Tech Stack

- **Language:** Python 3.11+
- **Data Gathering:** Apify Client (`apify-client`)
- **AI / NLP:** `openai`, `anthropic`, `python-dotenv`
- **Data Formats:** JSON, CSV, Pandas-compatible structures

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
