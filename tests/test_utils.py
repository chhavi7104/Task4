"""Unit tests for crawler_pkg.utils"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler_pkg.utils import (  # noqa: E402
    normalize_url,
    is_same_domain,
    get_domain,
    is_crawlable_scheme,
    retry,
)


def test_normalize_url_resolves_relative_paths():
    assert normalize_url("https://example.com/blog/", "../about") == "https://example.com/about"


def test_normalize_url_strips_fragments():
    result = normalize_url("https://example.com", "/page#section-2")
    assert result == "https://example.com/page"


def test_normalize_url_handles_absolute_links():
    result = normalize_url("https://example.com", "https://other.com/x")
    assert result == "https://other.com/x"


def test_is_same_domain_matches_exact_domain():
    assert is_same_domain("https://example.com/page", "example.com") is True


def test_is_same_domain_matches_subdomain():
    assert is_same_domain("https://blog.example.com/page", "example.com") is True


def test_is_same_domain_rejects_other_domain():
    assert is_same_domain("https://other.com/page", "example.com") is False


def test_get_domain_extracts_netloc():
    assert get_domain("https://example.com/path?x=1") == "example.com"


def test_is_crawlable_scheme_accepts_http_https():
    assert is_crawlable_scheme("http://example.com") is True
    assert is_crawlable_scheme("https://example.com") is True


def test_is_crawlable_scheme_rejects_other_schemes():
    assert is_crawlable_scheme("mailto:test@example.com") is False
    assert is_crawlable_scheme("javascript:void(0)") is False
    assert is_crawlable_scheme("ftp://example.com") is False


def test_retry_succeeds_after_transient_failures():
    calls = {"count": 0}

    @retry(max_retries=3, backoff=0.01, exceptions=(ValueError,))
    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise ValueError("transient failure")
        return "ok"

    assert flaky() == "ok"
    assert calls["count"] == 3


def test_retry_raises_after_exhausting_attempts():
    @retry(max_retries=2, backoff=0.01, exceptions=(ValueError,))
    def always_fails():
        raise ValueError("permanent failure")

    with pytest.raises(ValueError):
        always_fails()
