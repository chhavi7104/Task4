"""Unit tests for crawler_pkg.parser.Parser"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler_pkg.parser import Parser, PageData  # noqa: E402

SAMPLE_HTML = """
<html>
<head>
    <title>Test Page Title</title>
    <meta name="description" content="A test page description.">
    <meta name="keywords" content="test, crawler, python">
</head>
<body>
    <h1>Main Heading</h1>
    <h2>Sub Heading One</h2>
    <h2>Sub Heading Two</h2>
    <p>This is the first paragraph with some content.</p>
    <p>This is the second paragraph, also with content.</p>
    <a href="/internal-page">Internal Link</a>
    <a href="https://external.com/page">External Link</a>
    <a href="#section">Fragment link (ignored)</a>
    <a href="javascript:void(0)">JS link (ignored)</a>
    <img src="/images/photo.jpg" alt="A photo">
    <img src="https://cdn.example.com/logo.png" alt="Logo">
</body>
</html>
"""


def test_parse_extracts_title():
    parser = Parser()
    page = parser.parse("https://example.com/", SAMPLE_HTML)
    assert page.title == "Test Page Title"


def test_parse_extracts_meta():
    parser = Parser()
    page = parser.parse("https://example.com/", SAMPLE_HTML)
    assert page.meta_description == "A test page description."
    assert "python" in page.meta_keywords


def test_parse_extracts_headings():
    parser = Parser()
    page = parser.parse("https://example.com/", SAMPLE_HTML)
    assert page.headings["h1"] == ["Main Heading"]
    assert page.headings["h2"] == ["Sub Heading One", "Sub Heading Two"]


def test_parse_extracts_paragraphs():
    parser = Parser()
    page = parser.parse("https://example.com/", SAMPLE_HTML)
    assert len(page.paragraphs) == 2
    assert "first paragraph" in page.paragraphs[0]


def test_parse_classifies_internal_and_external_links():
    parser = Parser()
    page = parser.parse("https://example.com/", SAMPLE_HTML)
    assert "https://example.com/internal-page" in page.internal_links
    assert "https://external.com/page" in page.external_links
    # fragment-only and javascript: links must be excluded
    assert not any("javascript" in link for link in page.links)
    assert not any(link.endswith("#section") for link in page.links)


def test_parse_extracts_images_as_absolute_urls():
    parser = Parser()
    page = parser.parse("https://example.com/", SAMPLE_HTML)
    assert "https://example.com/images/photo.jpg" in page.images
    assert "https://cdn.example.com/logo.png" in page.images


def test_parse_computes_word_count():
    parser = Parser()
    page = parser.parse("https://example.com/", SAMPLE_HTML)
    assert page.word_count > 0


def test_page_data_full_text_combines_fields():
    page = PageData(
        url="https://example.com",
        title="Hello",
        headings={"h1": ["World"]},
        paragraphs=["Some content here."],
    )
    text = page.full_text()
    assert "Hello" in text
    assert "World" in text
    assert "Some content here." in text


def test_parse_handles_empty_html_gracefully():
    parser = Parser()
    page = parser.parse("https://example.com/", "<html></html>")
    assert page.title == ""
    assert page.paragraphs == []
    assert page.links == []
