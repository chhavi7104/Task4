"""
exporter.py
===========
Handles persisting crawled `PageData` records to disk in multiple
formats: JSON (full structured dump), CSV (flattened, spreadsheet
friendly), and SQLite (queryable relational store).
"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .parser import PageData


class Exporter:
    """Writes a collection of PageData records to one or more formats."""

    def __init__(self, output_dir: str = "exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    def export(self, pages: List[PageData], formats: List[str], run_id: str | None = None) -> dict:
        """
        Export `pages` in each requested format. Returns a dict mapping
        format name -> output file path (as a string) for reporting.
        """
        run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        results = {}

        if "json" in formats:
            results["json"] = str(self._export_json(pages, run_id))
        if "csv" in formats:
            results["csv"] = str(self._export_csv(pages, run_id))
        if "sqlite" in formats:
            results["sqlite"] = str(self._export_sqlite(pages, run_id))

        return results

    # ------------------------------------------------------------------ #
    def _export_json(self, pages: List[PageData], run_id: str) -> Path:
        path = self.output_dir / f"crawl_{run_id}.json"
        payload = {
            "run_id": run_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "page_count": len(pages),
            "pages": [p.to_dict() for p in pages],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return path

    def _export_csv(self, pages: List[PageData], run_id: str) -> Path:
        path = self.output_dir / f"crawl_{run_id}.csv"
        fieldnames = [
            "url", "status_code", "title", "meta_description", "meta_keywords",
            "depth", "word_count", "num_headings", "num_paragraphs",
            "num_links", "num_internal_links", "num_external_links",
            "num_images", "fetched_at", "error",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for p in pages:
                writer.writerow({
                    "url": p.url,
                    "status_code": p.status_code,
                    "title": p.title,
                    "meta_description": p.meta_description,
                    "meta_keywords": p.meta_keywords,
                    "depth": p.depth,
                    "word_count": p.word_count,
                    "num_headings": sum(len(v) for v in p.headings.values()),
                    "num_paragraphs": len(p.paragraphs),
                    "num_links": len(p.links),
                    "num_internal_links": len(p.internal_links),
                    "num_external_links": len(p.external_links),
                    "num_images": len(p.images),
                    "fetched_at": p.fetched_at,
                    "error": p.error or "",
                })
        return path

    def _export_sqlite(self, pages: List[PageData], run_id: str) -> Path:
        path = self.output_dir / "crawler_data.db"
        conn = sqlite3.connect(path)
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    status_code INTEGER,
                    title TEXT,
                    meta_description TEXT,
                    meta_keywords TEXT,
                    depth INTEGER,
                    word_count INTEGER,
                    paragraphs TEXT,
                    headings TEXT,
                    links TEXT,
                    images TEXT,
                    fetched_at TEXT,
                    error TEXT
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url)
            """)
            for p in pages:
                cur.execute(
                    """
                    INSERT INTO pages (
                        run_id, url, status_code, title, meta_description,
                        meta_keywords, depth, word_count, paragraphs, headings,
                        links, images, fetched_at, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id, p.url, p.status_code, p.title, p.meta_description,
                        p.meta_keywords, p.depth, p.word_count,
                        json.dumps(p.paragraphs, ensure_ascii=False),
                        json.dumps(p.headings, ensure_ascii=False),
                        json.dumps(p.links, ensure_ascii=False),
                        json.dumps(p.images, ensure_ascii=False),
                        p.fetched_at, p.error,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
        return path
