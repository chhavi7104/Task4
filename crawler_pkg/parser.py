"""
parser.py
=========
HTML parsing and information extraction. Wraps BeautifulSoup (with the
`lxml` parser for speed) to pull out structured, human-readable data
from a raw HTML document: title, headings, paragraphs, links, images,
and metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .utils import normalize_url, is_crawlable_scheme


@dataclass
class PageData:
    """Structured representation of a single crawled page."""

    url: str
    status_code: Optional[int] = None
    title: str = ""
    meta_description: str = ""
    meta_keywords: str = ""
    headings: Dict[str, List[str]] = field(default_factory=dict)
    paragraphs: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    internal_links: List[str] = field(default_factory=list)
    external_links: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    word_count: int = 0
    depth: int = 0
    fetched_at: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def full_text(self) -> str:
        """Concatenate title, headings, and paragraphs for keyword search."""
        heading_text = " ".join(h for values in self.headings.values() for h in values)
        return " ".join([self.title, heading_text, " ".join(self.paragraphs)])


class Parser:
    """
    Stateless HTML parser. Given raw HTML and the URL it was fetched
    from, extracts a `PageData` object.
    """

    HEADING_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6"]

    def __init__(self, parser_backend: str = "lxml"):
        self.parser_backend = parser_backend

    def parse(self, url: str, html: str, depth: int = 0) -> PageData:
        soup = BeautifulSoup(html, self.parser_backend)
        domain = urlparse(url).netloc.lower()

        page = PageData(url=url, depth=depth)

        page.title = self._extract_title(soup)
        page.meta_description = self._extract_meta(soup, "description")
        page.meta_keywords = self._extract_meta(soup, "keywords")
        page.headings = self._extract_headings(soup)
        page.paragraphs = self._extract_paragraphs(soup)

        links, internal, external = self._extract_links(soup, url, domain)
        page.links = links
        page.internal_links = internal
        page.external_links = external

        page.images = self._extract_images(soup, url)
        page.word_count = len(page.full_text().split())

        return page

    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        return ""

    @staticmethod
    def _extract_meta(soup: BeautifulSoup, name: str) -> str:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
        return ""

    def _extract_headings(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        headings: Dict[str, List[str]] = {}
        for tag_name in self.HEADING_TAGS:
            texts = [
                el.get_text(strip=True)
                for el in soup.find_all(tag_name)
                if el.get_text(strip=True)
            ]
            if texts:
                headings[tag_name] = texts
        return headings

    @staticmethod
    def _extract_paragraphs(soup: BeautifulSoup) -> List[str]:
        return [
            p.get_text(strip=True)
            for p in soup.find_all("p")
            if p.get_text(strip=True)
        ]

    @staticmethod
    def _extract_links(soup: BeautifulSoup, base_url: str, domain: str):
        all_links, internal, external = [], [], []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue
            absolute = normalize_url(base_url, href)
            if not is_crawlable_scheme(absolute):
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            all_links.append(absolute)
            if urlparse(absolute).netloc.lower() == domain:
                internal.append(absolute)
            else:
                external.append(absolute)
        return all_links, internal, external

    @staticmethod
    def _extract_images(soup: BeautifulSoup, base_url: str) -> List[str]:
        images = []
        seen = set()
        for img in soup.find_all("img", src=True):
            src = img["src"].strip()
            if not src:
                continue
            absolute = normalize_url(base_url, src)
            if absolute not in seen:
                seen.add(absolute)
                images.append(absolute)
        return images
