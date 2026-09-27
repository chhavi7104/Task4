"""
utils.py
========
Cross-cutting utilities shared by the rest of the package:

* Logging setup (console + rotating file handler)
* A `retry` decorator with exponential backoff for network calls
* robots.txt fetching/parsing via `RobotsChecker`
* URL helpers (normalization, same-domain checks)
"""

from __future__ import annotations

import functools
import logging
import time
from logging.handlers import RotatingFileHandler
from typing import Callable, TypeVar
from urllib.parse import urljoin, urldefrag, urlparse
from urllib.robotparser import RobotFileParser

T = TypeVar("T")


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def setup_logger(name: str, log_file: str, level: str = "INFO") -> logging.Logger:
    """
    Configure and return a logger that writes to both the console and a
    rotating log file. Safe to call multiple times (handlers aren't
    duplicated).
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if logger.handlers:
        return logger  # already configured

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # If the log directory is unwritable, fall back to console-only.
        logger.warning("Could not open log file %s; logging to console only.", log_file)

    return logger


# --------------------------------------------------------------------------- #
# Retry decorator
# --------------------------------------------------------------------------- #
def retry(max_retries: int = 3, backoff: float = 1.5, exceptions: tuple = (Exception,)):
    """
    Decorator factory that retries a function on failure with
    exponential backoff. Re-raises the last exception if all attempts
    are exhausted.

    Usage:
        @retry(max_retries=3, backoff=1.5, exceptions=(requests.RequestException,))
        def fetch(url): ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:  # noqa: PERF203
                    last_exc = exc
                    if attempt < max_retries:
                        sleep_time = backoff ** attempt
                        logging.getLogger("crawler").debug(
                            "Retry %s/%s for %s after error: %s (sleeping %.1fs)",
                            attempt, max_retries, func.__name__, exc, sleep_time,
                        )
                        time.sleep(sleep_time)
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


# --------------------------------------------------------------------------- #
# URL helpers
# --------------------------------------------------------------------------- #
def normalize_url(base_url: str, link: str) -> str:
    """Resolve a possibly-relative link against a base URL and strip fragments."""
    absolute = urljoin(base_url, link.strip())
    absolute, _frag = urldefrag(absolute)
    return absolute


def is_same_domain(url: str, root_domain: str) -> bool:
    """Return True if `url`'s netloc matches (or is a subdomain of) root_domain."""
    netloc = urlparse(url).netloc.lower()
    root = root_domain.lower()
    return netloc == root or netloc.endswith(f".{root}")


def get_domain(url: str) -> str:
    """Extract the network location (domain) portion of a URL."""
    return urlparse(url).netloc.lower()


def is_crawlable_scheme(url: str) -> bool:
    """Only allow http/https URLs to be queued for crawling."""
    return urlparse(url).scheme in ("http", "https")


# --------------------------------------------------------------------------- #
# robots.txt
# --------------------------------------------------------------------------- #
class RobotsChecker:
    """
    Fetches and caches robots.txt files per-domain and answers whether
    a given URL/user-agent combination is allowed to be fetched.
    Fails open (allows crawling) if robots.txt cannot be retrieved,
    which mirrors typical crawler behavior for missing robots files.
    """

    def __init__(self, user_agent: str, enabled: bool = True):
        self.user_agent = user_agent
        self.enabled = enabled
        self._parsers: dict[str, RobotFileParser] = {}

    def _get_parser(self, url: str) -> RobotFileParser | None:
        domain = get_domain(url)
        if domain in self._parsers:
            return self._parsers[domain]

        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            parser.read()
        except Exception:
            # No robots.txt or unreachable -> treat as "allow all".
            parser = None
        self._parsers[domain] = parser
        return parser

    def can_fetch(self, url: str) -> bool:
        if not self.enabled:
            return True
        parser = self._get_parser(url)
        if parser is None:
            return True
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def crawl_delay(self, url: str) -> float | None:
        """Return the crawl-delay directive for this domain, if any."""
        if not self.enabled:
            return None
        parser = self._get_parser(url)
        if parser is None:
            return None
        try:
            delay = parser.crawl_delay(self.user_agent)
            return float(delay) if delay is not None else None
        except Exception:
            return None
