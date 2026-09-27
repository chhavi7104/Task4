"""Unit tests for crawler_pkg.exporter and crawler_pkg.search"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler_pkg.parser import PageData  # noqa: E402
from crawler_pkg.exporter import Exporter  # noqa: E402
from crawler_pkg.search import KeywordSearch, SitemapGenerator  # noqa: E402


def _sample_pages():
    return [
        PageData(
            url="https://example.com/",
            status_code=200,
            title="Home",
            headings={"h1": ["Welcome"]},
            paragraphs=["Python web crawling is fun.", "Python is great for automation."],
            links=["https://example.com/about"],
            internal_links=["https://example.com/about"],
            external_links=[],
            images=[],
            word_count=10,
            depth=0,
            fetched_at="2026-01-01T00:00:00+00:00",
        ),
        PageData(
            url="https://example.com/about",
            status_code=200,
            title="About",
            headings={"h1": ["About Us"]},
            paragraphs=["We build crawlers and data tools."],
            links=[],
            internal_links=[],
            external_links=[],
            images=[],
            word_count=8,
            depth=1,
            fetched_at="2026-01-01T00:00:05+00:00",
        ),
        PageData(
            url="https://example.com/broken",
            error="404 Not Found",
            depth=1,
        ),
    ]


def test_export_json_creates_valid_file(tmp_path):
    exporter = Exporter(output_dir=str(tmp_path))
    outputs = exporter.export(_sample_pages(), formats=["json"], run_id="test1")

    json_path = Path(outputs["json"])
    assert json_path.exists()

    with open(json_path) as f:
        data = json.load(f)
    assert data["page_count"] == 3
    assert data["pages"][0]["url"] == "https://example.com/"


def test_export_csv_creates_file_with_rows(tmp_path):
    exporter = Exporter(output_dir=str(tmp_path))
    outputs = exporter.export(_sample_pages(), formats=["csv"], run_id="test2")

    csv_path = Path(outputs["csv"])
    assert csv_path.exists()
    content = csv_path.read_text()
    assert "example.com" in content
    # header + 3 data rows
    assert len(content.strip().splitlines()) == 4


def test_export_sqlite_inserts_rows(tmp_path):
    exporter = Exporter(output_dir=str(tmp_path))
    outputs = exporter.export(_sample_pages(), formats=["sqlite"], run_id="test3")

    db_path = Path(outputs["sqlite"])
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    conn.close()
    assert count == 3


def test_keyword_search_finds_and_ranks_matches():
    searcher = KeywordSearch(_sample_pages())
    results = searcher.search("python")
    assert len(results) == 1
    assert results[0].url == "https://example.com/"
    assert results[0].score == 2  # "Python" appears twice on the home page


def test_keyword_search_no_match_returns_empty():
    searcher = KeywordSearch(_sample_pages())
    results = searcher.search("nonexistentterm")
    assert results == []


def test_keyword_frequency_excludes_stopwords():
    searcher = KeywordSearch(_sample_pages())
    freq = searcher.keyword_frequency(top_n=10)
    assert "the" not in freq
    assert "python" in freq


def test_sitemap_generator_skips_errored_pages(tmp_path):
    generator = SitemapGenerator(_sample_pages())
    output_path = tmp_path / "sitemap.xml"
    generator.generate(str(output_path))

    content = output_path.read_text()
    assert "example.com/" in content
    assert "example.com/about" in content
    assert "broken" not in content
