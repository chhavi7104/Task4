"""
crawler.py
==========
Core crawling engine. Two implementations are provided:

* `Crawler`      - synchronous, requests-based, breadth-first crawl.
* `AsyncCrawler`  - asyncio + aiohttp based, concurrent crawl for
                    higher throughput on I/O-bound workloads.

Both share the same visited-link tracking, robots.txt respect,
depth-limiting, retry/backoff and statistics collection, and both
produce a list of `PageData` objects ready for export.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Set

import requests
from requests.exceptions import RequestException

try:
    import aiohttp
except ImportError:  # pragma: no cover - aiohttp is a hard requirement but degrade gracefully
    aiohttp = None

from .config import Config
from .parser import Parser, PageData
from .utils import (
    setup_logger,
    retry,
    normalize_url,
    is_same_domain,
    is_crawlable_scheme,
    get_domain,
    RobotsChecker,
)


@dataclass
class CrawlStats:
    """Aggregate statistics for a single crawl run."""

    pages_visited: int = 0
    pages_failed: int = 0
    pages_skipped_robots: int = 0
    duplicate_urls_skipped: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    @property
    def elapsed_seconds(self) -> float:
        end = self.end_time or time.time()
        return round(end - self.start_time, 2)

    def to_dict(self) -> dict:
        return {
            "pages_visited": self.pages_visited,
            "pages_failed": self.pages_failed,
            "pages_skipped_robots": self.pages_skipped_robots,
            "duplicate_urls_skipped": self.duplicate_urls_skipped,
            "elapsed_seconds": self.elapsed_seconds,
        }


class BaseCrawler:
    """Shared setup for both synchronous and asynchronous crawlers."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = setup_logger("crawler", config.log_file, config.log_level)
        self.parser = Parser()
        self.robots = RobotsChecker(config.user_agent, config.respect_robots_txt)
        self.visited: Set[str] = set()
        self.stats = CrawlStats()
        self.pages: List[PageData] = []
        self._root_domains = {get_domain(u) for u in config.seed_urls}

    def _allowed_domain(self, url: str) -> bool:
        return any(is_same_domain(url, domain) for domain in self._root_domains)

    def _should_queue(self, url: str) -> bool:
        if not is_crawlable_scheme(url):
            return False
        if url in self.visited:
            self.stats.duplicate_urls_skipped += 1
            return False
        if not self._allowed_domain(url):
            return False
        if not self.robots.can_fetch(url):
            self.logger.info("Blocked by robots.txt: %s", url)
            self.stats.pages_skipped_robots += 1
            return False
        return True


class Crawler(BaseCrawler):
    """Synchronous, breadth-first web crawler built on `requests`."""

    def __init__(self, config: Config):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})

    @retry(max_retries=3, backoff=1.5, exceptions=(RequestException,))
    def _fetch(self, url: str) -> requests.Response:
        response = self.session.get(url, timeout=self.config.request_timeout)
        response.raise_for_status()
        return response

    def crawl(self) -> List[PageData]:
        """Run a full breadth-first crawl starting from the configured seed URLs."""
        self.logger.info(
            "Starting synchronous crawl | seeds=%s | max_depth=%s | max_pages=%s",
            self.config.seed_urls, self.config.max_depth, self.config.max_pages,
        )
        self.stats = CrawlStats()
        queue: deque = deque((url, 0) for url in self.config.seed_urls)

        while queue and self.stats.pages_visited < self.config.max_pages:
            url, depth = queue.popleft()
            if url in self.visited:
                self.stats.duplicate_urls_skipped += 1
                continue
            if not self.robots.can_fetch(url):
                self.stats.pages_skipped_robots += 1
                continue

            self.visited.add(url)
            page = self._crawl_one(url, depth)
            self.pages.append(page)

            if page.error is None:
                self.stats.pages_visited += 1
                if depth < self.config.max_depth:
                    for link in page.internal_links:
                        if self._should_queue(link):
                            queue.append((link, depth + 1))
            else:
                self.stats.pages_failed += 1

            time.sleep(max(
                self.config.request_delay,
                self.robots.crawl_delay(url) or 0.0,
            ))

        self.stats.end_time = time.time()
        self.logger.info("Crawl finished: %s", self.stats.to_dict())
        return self.pages

    def _crawl_one(self, url: str, depth: int) -> PageData:
        try:
            response = self._fetch(url)
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                self.logger.debug("Skipping non-HTML content at %s (%s)", url, content_type)
                return PageData(url=url, status_code=response.status_code, depth=depth,
                                 fetched_at=datetime.now(timezone.utc).isoformat(),
                                 error=f"Non-HTML content-type: {content_type}")
            page = self.parser.parse(url, response.text, depth)
            page.status_code = response.status_code
            page.fetched_at = datetime.now(timezone.utc).isoformat()
            self.logger.info("Fetched [%s] depth=%s %s", response.status_code, depth, url)
            return page
        except RequestException as exc:
            self.logger.warning("Failed to fetch %s: %s", url, exc)
            return PageData(
                url=url, depth=depth,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                error=str(exc),
            )


class AsyncCrawler(BaseCrawler):
    """Concurrent web crawler built on `asyncio` + `aiohttp`."""

    def __init__(self, config: Config):
        super().__init__(config)
        if aiohttp is None:
            raise RuntimeError("aiohttp is required for AsyncCrawler; pip install aiohttp")
        self._semaphore = asyncio.Semaphore(config.concurrency)
        self._lock = asyncio.Lock()

    async def _fetch(self, session: "aiohttp.ClientSession", url: str) -> tuple[int, str, str]:
        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                async with self._semaphore:
                    timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
                    async with session.get(url, timeout=timeout) as response:
                        text = await response.text(errors="ignore")
                        content_type = response.headers.get("Content-Type", "")
                        return response.status, text, content_type
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_backoff ** attempt)
        raise last_exc  # type: ignore[misc]

    async def crawl(self) -> List[PageData]:
        self.logger.info(
            "Starting asynchronous crawl | seeds=%s | max_depth=%s | max_pages=%s | concurrency=%s",
            self.config.seed_urls, self.config.max_depth, self.config.max_pages, self.config.concurrency,
        )
        self.stats = CrawlStats()
        headers = {"User-Agent": self.config.user_agent}

        current_level = [(url, 0) for url in self.config.seed_urls]

        async with aiohttp.ClientSession(headers=headers) as session:
            while current_level and self.stats.pages_visited < self.config.max_pages:
                remaining_budget = self.config.max_pages - self.stats.pages_visited
                batch = current_level[:remaining_budget]
                current_level = current_level[remaining_budget:]

                tasks = []
                for url, depth in batch:
                    if url in self.visited:
                        self.stats.duplicate_urls_skipped += 1
                        continue
                    if not self.robots.can_fetch(url):
                        self.stats.pages_skipped_robots += 1
                        continue
                    self.visited.add(url)
                    tasks.append(self._crawl_one(session, url, depth))

                if not tasks:
                    current_level = []
                    continue

                results = await asyncio.gather(*tasks)
                next_level = []
                for page in results:
                    self.pages.append(page)
                    if page.error is None:
                        self.stats.pages_visited += 1
                        if page.depth < self.config.max_depth:
                            for link in page.internal_links:
                                if self._should_queue(link):
                                    next_level.append((link, page.depth + 1))
                    else:
                        self.stats.pages_failed += 1

                current_level = next_level + current_level
                await asyncio.sleep(self.config.request_delay)

        self.stats.end_time = time.time()
        self.logger.info("Async crawl finished: %s", self.stats.to_dict())
        return self.pages

    async def _crawl_one(self, session: "aiohttp.ClientSession", url: str, depth: int) -> PageData:
        try:
            status, text, content_type = await self._fetch(session, url)
            if "text/html" not in content_type:
                return PageData(url=url, status_code=status, depth=depth,
                                 fetched_at=datetime.now(timezone.utc).isoformat(),
                                 error=f"Non-HTML content-type: {content_type}")
            page = self.parser.parse(url, text, depth)
            page.status_code = status
            page.fetched_at = datetime.now(timezone.utc).isoformat()
            self.logger.info("Fetched [%s] depth=%s %s", status, depth, url)
            return page
        except Exception as exc:  # noqa: BLE001 - want to capture all fetch errors as page errors
            self.logger.warning("Failed to fetch %s: %s", url, exc)
            return PageData(
                url=url, depth=depth,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                error=str(exc),
            )
