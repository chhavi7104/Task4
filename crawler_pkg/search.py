"""
search.py
=========
Keyword search and frequency analysis over a collection of crawled
`PageData` records, plus an XML sitemap generator built from the same
data.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Dict
from xml.etree.ElementTree import Element, SubElement, ElementTree

from .parser import PageData

_WORD_RE = re.compile(r"[A-Za-z0-9']+")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be",
    "been", "being", "to", "of", "in", "on", "at", "for", "with", "as",
    "by", "this", "that", "it", "its", "from", "we", "you", "your", "our",
    "i", "he", "she", "they", "them", "his", "her", "their", "not", "have",
    "has", "had", "do", "does", "did", "will", "would", "can", "could",
    "should", "may", "might", "if", "so", "up", "out", "about", "into",
}


@dataclass
class SearchResult:
    url: str
    title: str
    score: int
    snippet: str


class KeywordSearch:
    """Simple in-memory keyword search over a crawled page set."""

    def __init__(self, pages: List[PageData]):
        self.pages = pages

    def search(self, keyword: str, limit: int = 10) -> List[SearchResult]:
        """
        Rank pages by how many times `keyword` (case-insensitive, whole
        word) appears across title/headings/paragraphs. Returns the
        top `limit` matches with a short context snippet.
        """
        keyword_lower = keyword.lower()
        pattern = re.compile(rf"\b{re.escape(keyword_lower)}\b")
        results: List[SearchResult] = []

        for page in self.pages:
            text = page.full_text()
            occurrences = len(pattern.findall(text.lower()))
            if occurrences > 0:
                results.append(SearchResult(
                    url=page.url,
                    title=page.title,
                    score=occurrences,
                    snippet=self._make_snippet(text, keyword_lower),
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    @staticmethod
    def _make_snippet(text: str, keyword: str, context_chars: int = 60) -> str:
        idx = text.lower().find(keyword)
        if idx == -1:
            return text[:120].strip() + ("..." if len(text) > 120 else "")
        start = max(0, idx - context_chars)
        end = min(len(text), idx + len(keyword) + context_chars)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        return f"{prefix}{text[start:end].strip()}{suffix}"

    def keyword_frequency(self, top_n: int = 25) -> Dict[str, int]:
        """
        Compute overall keyword frequency across all crawled pages,
        excluding common English stopwords. Returns the top `top_n`
        terms as an ordered dict (most frequent first).
        """
        counter: Counter = Counter()
        for page in self.pages:
            words = _WORD_RE.findall(page.full_text().lower())
            counter.update(w for w in words if w not in _STOPWORDS and len(w) > 2)
        return dict(counter.most_common(top_n))


class SitemapGenerator:
    """Builds a standard XML sitemap (sitemap.org schema) from crawl results."""

    NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"

    def __init__(self, pages: List[PageData]):
        self.pages = pages

    def generate(self, output_path: str) -> str:
        urlset = Element("urlset", xmlns=self.NAMESPACE)
        for page in self.pages:
            if page.error is not None:
                continue
            url_el = SubElement(urlset, "url")
            loc = SubElement(url_el, "loc")
            loc.text = page.url
            if page.fetched_at:
                lastmod = SubElement(url_el, "lastmod")
                lastmod.text = page.fetched_at.split("T")[0]

        tree = ElementTree(urlset)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        return output_path
