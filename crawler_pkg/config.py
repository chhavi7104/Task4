"""
config.py
=========
Centralized configuration management for the Web Crawler & Data
Extraction Engine. Loads values from a `.env` file (via python-dotenv)
with sensible defaults, and exposes them as a typed, immutable
`Config` dataclass so the rest of the application never touches
`os.environ` directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv


def _str_to_bool(value: str) -> bool:
    """Convert common truthy/falsy string representations to bool."""
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _split_csv(value: str) -> List[str]:
    """Split a comma-separated environment value into a clean list."""
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Config:
    """
    Immutable configuration object for a crawl run.

    All fields have defaults so the crawler can run out-of-the-box,
    but every value can be overridden via a `.env` file or by passing
    explicit keyword arguments (e.g. from the CLI).
    """

    seed_urls: List[str] = field(default_factory=lambda: ["https://example.com"])
    max_depth: int = 2
    max_pages: int = 100
    request_delay: float = 1.0
    request_timeout: int = 10
    max_retries: int = 3
    retry_backoff: float = 1.5
    respect_robots_txt: bool = True
    user_agent: str = "EduCrawlerBot/1.0 (+https://github.com/yourname/webcrawler)"
    use_async: bool = True
    concurrency: int = 5
    output_dir: str = "exports"
    export_formats: List[str] = field(default_factory=lambda: ["json", "csv", "sqlite"])
    log_file: str = "logs/crawler.log"
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if self.max_depth < 0:
            raise ValueError("max_depth must be >= 0")
        if self.max_pages <= 0:
            raise ValueError("max_pages must be > 0")
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be > 0")
        if self.concurrency <= 0:
            raise ValueError("concurrency must be > 0")
        if not self.seed_urls:
            raise ValueError("At least one seed URL is required")

    @classmethod
    def from_env(cls, env_path: str | None = None, **overrides) -> "Config":
        """
        Build a Config from environment variables (optionally loaded
        from a specific .env file), with `overrides` taking highest
        priority (used by the CLI for --flag style overrides).
        """
        if env_path:
            load_dotenv(env_path, override=True)
        else:
            # Look for a .env in CWD or project root; silently no-op if absent.
            load_dotenv(override=False)

        values = dict(
            seed_urls=_split_csv(os.getenv("SEED_URLS", "https://example.com")),
            max_depth=int(os.getenv("MAX_DEPTH", 2)),
            max_pages=int(os.getenv("MAX_PAGES", 100)),
            request_delay=float(os.getenv("REQUEST_DELAY", 1.0)),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", 10)),
            max_retries=int(os.getenv("MAX_RETRIES", 3)),
            retry_backoff=float(os.getenv("RETRY_BACKOFF", 1.5)),
            respect_robots_txt=_str_to_bool(os.getenv("RESPECT_ROBOTS_TXT", "true")),
            user_agent=os.getenv(
                "USER_AGENT",
                "EduCrawlerBot/1.0 (+https://github.com/yourname/webcrawler)",
            ),
            use_async=_str_to_bool(os.getenv("USE_ASYNC", "true")),
            concurrency=int(os.getenv("CONCURRENCY", 5)),
            output_dir=os.getenv("OUTPUT_DIR", "exports"),
            export_formats=_split_csv(os.getenv("EXPORT_FORMATS", "json,csv,sqlite")),
            log_file=os.getenv("LOG_FILE", "logs/crawler.log"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
        values.update(overrides)

        Path(values["output_dir"]).mkdir(parents=True, exist_ok=True)
        Path(values["log_file"]).parent.mkdir(parents=True, exist_ok=True)

        return cls(**values)
