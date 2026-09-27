"""
crawler_pkg
===========
Modular web crawler & data extraction engine.

Public API:
    Config          - configuration loader (config.py)
    Crawler         - synchronous crawler (crawler.py)
    AsyncCrawler    - asynchronous crawler (crawler.py)
    Parser          - HTML parser (parser.py)
    PageData        - structured page record (parser.py)
    Exporter        - JSON/CSV/SQLite export (exporter.py)
    KeywordSearch   - keyword search & frequency analysis (search.py)
    SitemapGenerator- XML sitemap builder (search.py)
"""

from .config import Config
from .crawler import Crawler, AsyncCrawler, CrawlStats
from .parser import Parser, PageData
from .exporter import Exporter
from .search import KeywordSearch, SitemapGenerator

__all__ = [
    "Config",
    "Crawler",
    "AsyncCrawler",
    "CrawlStats",
    "Parser",
    "PageData",
    "Exporter",
    "KeywordSearch",
    "SitemapGenerator",
]

__version__ = "1.0.0"
