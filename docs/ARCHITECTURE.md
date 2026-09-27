# Architecture Documentation

## 1. Overview

The system is a modular, layered web crawler. Each layer has a single responsibility and depends only on the layer below it, which makes the codebase testable in isolation and easy to extend (e.g., swapping the export backend or adding a new fetch strategy) without touching unrelated code.

```
┌─────────────────────────────────────────────────────────────┐
│                         cli.py / main.py                      │
│              (entry points: argument parsing, I/O)            │
└───────────────────────────┬─────────────────────────────────┘
                             │
┌───────────────────────────▼─────────────────────────────────┐
│                    crawler.py (Crawler /                      │
│                        AsyncCrawler)                           │
│   Orchestrates: fetch → parse → queue internal links → repeat │
│   Owns: visited-set, stats, robots.txt gate, retry/backoff    │
└──────────┬───────────────────────────────┬────────────────────┘
           │                               │
┌──────────▼──────────┐        ┌───────────▼────────────┐
│    parser.py         │        │      utils.py           │
│  HTML → PageData      │        │  logging, retry, URL    │
│  (title, headings,    │        │  normalization, robots  │
│   paragraphs, links,  │        │  checker                │
│   images, metadata)   │        │                          │
└──────────┬────────────┘        └──────────────────────────┘
           │
┌──────────▼────────────┐        ┌──────────────────────────┐
│    exporter.py          │        │       search.py           │
│  List[PageData] →        │        │  KeywordSearch,            │
│  JSON / CSV / SQLite     │        │  SitemapGenerator           │
└───────────────────────────┘      └──────────────────────────┘
```

`config.py` sits orthogonally to all of the above: it is the single source of truth for run parameters, loaded once from `.env` into an immutable `Config` dataclass and passed by reference into `Crawler`/`AsyncCrawler`.

## 2. Data Flow

1. **Configuration load** — `Config.from_env()` reads `.env`, validates values (e.g. `max_depth >= 0`), and creates the output/log directories.
2. **Seed enqueue** — each seed URL is enqueued at depth 0.
3. **Fetch** — `Crawler`/`AsyncCrawler` pulls a URL off the queue, checks `robots.txt` via `RobotsChecker`, then fetches the page (with retry/backoff on transient network errors).
4. **Parse** — the raw HTML is handed to `Parser.parse()`, which returns a `PageData` object: title, meta description/keywords, headings by level, paragraph text, all links (split into internal/external), images, and a computed word count.
5. **Queue expansion** — for every internal link found (deduplicated against the `visited` set, filtered to the seed's domain, filtered by `robots.txt`), a new `(url, depth+1)` item is enqueued — but only up to `max_depth`.
6. **Loop** — steps 3–5 repeat breadth-first until the queue is empty or `max_pages` is reached.
7. **Export** — the accumulated `List[PageData]` is passed to `Exporter.export()`, which writes one file per requested format.
8. **Post-processing (optional)** — `KeywordSearch` and `SitemapGenerator` operate on the same `PageData` records (loaded back from a JSON export) to provide search, frequency analysis, and sitemap generation without needing to re-crawl.

## 3. Key Design Decisions

### 3.1 Sync vs. Async, sharing one pipeline
Both `Crawler` (requests, single-threaded, breadth-first) and `AsyncCrawler` (aiohttp, `asyncio.Semaphore`-bounded concurrency, level-by-level batched fetches) subclass `BaseCrawler`, which owns everything that must behave identically regardless of transport: the visited-set, domain-allowlist check, robots.txt gate, and `CrawlStats`. This means correctness logic (what counts as "should I crawl this URL?") is written once (`_should_queue`) and cannot drift between the two implementations.

### 3.2 Fail-safe error handling
A failed fetch or a non-HTML response does not raise out of the crawl loop — it produces a `PageData` with `error` set and `pages_failed` incremented, and the crawl continues. This mirrors real-world crawling, where a handful of broken links or timeouts should never abort a multi-hundred-page run. Errors are still fully visible: they're in the exported JSON/CSV (`error` column) and summarized in `CrawlStats`.

### 3.3 Politeness by construction, not by convention
`RobotsChecker` is consulted both when a URL is dequeued (belt) and when a new link is considered for enqueueing (suspenders), so disallowed paths never even enter the queue. Per-host `Crawl-delay` directives are honored in addition to the configured `REQUEST_DELAY`, taking whichever is larger.

### 3.4 Retry strategy
The `retry()` decorator (used by the sync crawler) and the equivalent loop in `AsyncCrawler._fetch` both implement exponential backoff (`backoff ** attempt` seconds) and are scoped to network-level exceptions only — HTTP 4xx/5xx responses raised via `raise_for_status()` are retried the same as connection errors, since transient 5xx errors are common on real sites, but the final failure is still surfaced as a normal `PageData.error` rather than crashing the process.

### 3.5 Export formats are additive, not exclusive
`Exporter.export()` accepts a list of formats and writes each independently from the same in-memory `List[PageData]`, so `--formats json csv sqlite` costs one crawl but produces three artifacts — useful for feeding JSON to `search`/`sitemap` while also handing a CSV to a non-technical stakeholder and a SQLite file to a BI tool.

## 4. Data Schema (`PageData`)

| Field | Type | Description |
|---|---|---|
| `url` | str | Canonical (fragment-stripped) URL |
| `status_code` | int \| None | HTTP status, if the fetch succeeded |
| `title` | str | `<title>` text |
| `meta_description` / `meta_keywords` | str | From `<meta name="...">` |
| `headings` | dict[str, list[str]] | `{"h1": [...], "h2": [...], ...}` |
| `paragraphs` | list[str] | All non-empty `<p>` text |
| `links` / `internal_links` / `external_links` | list[str] | Deduplicated, absolute URLs |
| `images` | list[str] | Absolute image URLs |
| `word_count` | int | Word count of title + headings + paragraphs |
| `depth` | int | BFS depth from the nearest seed |
| `fetched_at` | str | ISO-8601 UTC timestamp |
| `error` | str \| None | Present only if the fetch/parse failed |

## 5. Extensibility Points

- **New export format**: add a `_export_<format>()` method to `Exporter` and register it in `export()`.
- **New extraction field** (e.g. structured data / JSON-LD): extend `PageData` and add a `_extract_*` method to `Parser`.
- **Different fetch backend** (e.g. `httpx`): implement a new class extending `BaseCrawler`; the queueing/robots/stats logic is reused automatically.
- **Persistence beyond SQLite** (e.g. Postgres): swap the connection logic inside `_export_sqlite`, or add a new exporter method following the same pattern.

## 6. Known Limitations

- JavaScript-rendered pages are not executed (no headless browser); only server-rendered HTML is parsed. A future iteration could add a Playwright-based fetch path behind the same `BaseCrawler` interface.
- The in-memory `KeywordSearch` is appropriate for the crawl sizes this engine targets (hundreds–low thousands of pages); a much larger corpus would benefit from an inverted index (e.g. via SQLite FTS5, which the SQLite exporter already lays groundwork for).
- Politeness is per-run, not persisted across runs — a fresh process re-checks `robots.txt` rather than caching it long-term.
