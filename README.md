# 🕷️ Web Crawler & Data Extraction Engine

A scalable, production-quality Python web crawler that downloads webpages, extracts human-readable information, follows internal links up to a configurable depth, and exports structured datasets to JSON, CSV, and SQLite. Built for Task 4 (Week 4) with clean, modular OOP architecture.

## ✨ Features

| Category | Details |
|---|---|
| **Fetching** | `requests` (sync) or `aiohttp` (async, concurrent) with configurable timeout |
| **Parsing** | `BeautifulSoup` + `lxml` — titles, h1–h6 headings, paragraphs, links, images, meta description/keywords |
| **Crawling** | Breadth-first internal-link following, configurable max depth & max pages, duplicate-URL tracking |
| **Politeness** | `robots.txt` respected via `urllib.robotparser`, configurable per-request delay, honors `Crawl-delay` |
| **Resilience** | Retry decorator with exponential backoff, per-page error capture (crawl never dies on one bad page) |
| **Export** | JSON (full structured dump), CSV (flattened/spreadsheet-ready), SQLite (queryable) |
| **Search** | In-memory keyword search with ranked results + snippets, keyword-frequency analysis |
| **Extras** | XML sitemap generation, rich CLI, rotating file + console logging |

## 📁 Project Structure

```
webcrawler/
├── crawler_pkg/            # Core package (modular, OOP, type-hinted)
│   ├── __init__.py         # Public API surface
│   ├── config.py           # .env-driven Config dataclass
│   ├── utils.py             # logging, retry decorator, robots.txt, URL helpers
│   ├── parser.py            # HTML → PageData extraction
│   ├── crawler.py           # Crawler (sync) & AsyncCrawler (asyncio/aiohttp)
│   ├── exporter.py          # JSON / CSV / SQLite export
│   └── search.py            # KeywordSearch + SitemapGenerator
├── cli.py                   # Rich-powered CLI (crawl / search / analyze / sitemap)
├── main.py                  # Minimal programmatic entry point
├── tests/                   # pytest unit tests (27 tests, parser/utils/exporter/search)
├── sample_data/             # Real sample JSON & CSV from a live crawl
├── docs/ARCHITECTURE.md     # Design & data-flow documentation
├── .github/workflows/ci.yml # GitHub Actions CI (lint + test)
├── Dockerfile                # Container build
├── .env.example              # All configurable settings
└── requirements.txt
```

## 🚀 Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/<yourname>/webcrawler.git
cd webcrawler

# 2. Create a virtual environment (Python 3.11+)
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# edit .env: set SEED_URLS, MAX_DEPTH, MAX_PAGES, etc.

# 5. Run a crawl
python cli.py crawl
```

## 🖥️ CLI Usage

```bash
# Crawl using .env defaults
python cli.py crawl

# Override seeds / depth / pages / mode from the command line
python cli.py crawl --url https://example.com --depth 3 --max-pages 50 --sync

# Choose specific export formats
python cli.py crawl --url https://example.com --formats json csv

# Keyword search over a previous crawl's JSON export
python cli.py search --input exports/crawl_20260101_120000.json --keyword python

# Keyword frequency analysis (top N terms, stopwords excluded)
python cli.py analyze --input exports/crawl_20260101_120000.json --top 15

# Generate an XML sitemap from a previous crawl
python cli.py sitemap --input exports/crawl_20260101_120000.json --output exports/sitemap.xml
```

Or run the minimal programmatic entry point, which reads everything from `.env`:

```bash
python main.py
```

## ⚙️ Configuration (`.env`)

All behavior is controlled via environment variables (see `.env.example` for the full, documented list): seed URLs, crawl depth/page caps, request delay & timeout, retry count/backoff, robots.txt enforcement, user agent, sync vs. async mode, concurrency, output directory, export formats, and logging.

## 🧪 Testing

```bash
pip install -r requirements.txt
pytest tests/ -v
```

27 unit tests cover HTML parsing edge cases, URL normalization, the retry decorator, robots.txt domain matching, JSON/CSV/SQLite export correctness, keyword search ranking, and sitemap generation.

## 🐳 Docker

```bash
docker build -t webcrawler .
docker run --rm -v $(pwd)/exports:/app/exports -v $(pwd)/.env:/app/.env webcrawler
```

## 📊 Sample Output

`sample_data/sample_output.json` and `sample_data/sample_output.csv` contain real output from a live crawl (6 pages, depth 1) run during development — not fabricated data. See `docs/ARCHITECTURE.md` for the full data schema.

## 🧱 Design Principles

- **Separation of concerns**: fetching (`crawler.py`), parsing (`parser.py`), persistence (`exporter.py`), and analysis (`search.py`) are independent, independently testable modules.
- **Fail-safe by default**: a single page's network error or malformed HTML is captured on that page's record (`PageData.error`) and never crashes the run.
- **Config over code**: every tunable (depth, delay, retries, formats...) lives in `.env`, not hardcoded.
- **Sync AND async**: the same `PageData`/`Exporter`/`Parser` pipeline backs both a simple synchronous crawler (easy to read/debug) and a concurrent `asyncio` crawler (throughput), so you can pick per run.

## 📄 License

MIT — see `LICENSE`.

## 🔗 Deliverables Checklist

- [x] Complete source code (this repo)
- [x] `README.md` (this file)
- [x] `requirements.txt`
- [x] `docs/ARCHITECTURE.md`
- [x] Sample JSON & CSV exports (`sample_data/`)
- [ ] 2–5 minute demo video (record locally after cloning — see "Quick Start")
- [ ] LinkedIn project post (share your repo link + a short write-up)
