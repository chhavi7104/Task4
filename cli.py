"""
cli.py
======
Command-line interface for the Web Crawler & Data Extraction Engine.

Examples
--------
Basic crawl using .env defaults:
    python cli.py crawl

Override seeds/depth/pages from the command line:
    python cli.py crawl --url https://example.com --depth 3 --max-pages 50

Run synchronously instead of async:
    python cli.py crawl --sync

Search previously exported JSON for a keyword:
    python cli.py search --input exports/crawl_20260101_120000.json --keyword python

Show top keyword frequencies:
    python cli.py analyze --input exports/crawl_20260101_120000.json --top 15

Generate a sitemap from a previous crawl's JSON export:
    python cli.py sitemap --input exports/crawl_20260101_120000.json --output exports/sitemap.xml
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from crawler_pkg import (
    Config, Crawler, AsyncCrawler, Exporter, KeywordSearch, SitemapGenerator, PageData,
)

console = Console()


def _load_pages_from_json(path: str) -> list[PageData]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    pages = []
    for raw in data.get("pages", []):
        page = PageData(url=raw["url"])
        page.__dict__.update(raw)
        pages.append(page)
    return pages


def _print_stats_table(stats: dict) -> None:
    table = Table(title="Crawl Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    for key, value in stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))
    console.print(table)


def cmd_crawl(args: argparse.Namespace) -> None:
    overrides = {}
    if args.url:
        overrides["seed_urls"] = args.url
    if args.depth is not None:
        overrides["max_depth"] = args.depth
    if args.max_pages is not None:
        overrides["max_pages"] = args.max_pages
    if args.sync:
        overrides["use_async"] = False
    if args.formats:
        overrides["export_formats"] = args.formats

    config = Config.from_env(env_path=args.env, **overrides)

    console.print(f"[bold cyan]Seeds:[/bold cyan] {config.seed_urls}")
    console.print(f"[bold cyan]Max depth:[/bold cyan] {config.max_depth}  "
                   f"[bold cyan]Max pages:[/bold cyan] {config.max_pages}  "
                   f"[bold cyan]Mode:[/bold cyan] {'async' if config.use_async else 'sync'}")

    if config.use_async:
        crawler = AsyncCrawler(config)
        pages = asyncio.run(crawler.crawl())
    else:
        crawler = Crawler(config)
        pages = crawler.crawl()

    exporter = Exporter(config.output_dir)
    outputs = exporter.export(pages, config.export_formats)

    _print_stats_table(crawler.stats.to_dict())

    console.print("\n[bold green]Exports written:[/bold green]")
    for fmt, path in outputs.items():
        console.print(f"  [yellow]{fmt}[/yellow]: {path}")

    failed = [p for p in pages if p.error]
    if failed:
        console.print(f"\n[bold red]{len(failed)} page(s) failed:[/bold red]")
        for p in failed[:10]:
            console.print(f"  - {p.url}: {p.error}")


def cmd_search(args: argparse.Namespace) -> None:
    pages = _load_pages_from_json(args.input)
    searcher = KeywordSearch(pages)
    results = searcher.search(args.keyword, limit=args.limit)

    if not results:
        console.print(f"[yellow]No matches for '{args.keyword}'.[/yellow]")
        return

    table = Table(title=f"Search results for '{args.keyword}'")
    table.add_column("Score", style="green", justify="right")
    table.add_column("Title", style="cyan")
    table.add_column("URL", style="blue")
    table.add_column("Snippet")
    for r in results:
        table.add_row(str(r.score), r.title or "(no title)", r.url, r.snippet)
    console.print(table)


def cmd_analyze(args: argparse.Namespace) -> None:
    pages = _load_pages_from_json(args.input)
    searcher = KeywordSearch(pages)
    freq = searcher.keyword_frequency(top_n=args.top)

    table = Table(title="Keyword Frequency Analysis")
    table.add_column("Keyword", style="cyan")
    table.add_column("Count", style="green", justify="right")
    for word, count in freq.items():
        table.add_row(word, str(count))
    console.print(table)


def cmd_sitemap(args: argparse.Namespace) -> None:
    pages = _load_pages_from_json(args.input)
    generator = SitemapGenerator(pages)
    output_path = generator.generate(args.output)
    console.print(f"[bold green]Sitemap written to:[/bold green] {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="webcrawler",
        description="Web Crawler & Data Extraction Engine - CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_crawl = sub.add_parser("crawl", help="Run a crawl and export results")
    p_crawl.add_argument("--url", action="append", help="Seed URL (repeatable)")
    p_crawl.add_argument("--depth", type=int, help="Max crawl depth")
    p_crawl.add_argument("--max-pages", type=int, help="Max pages to visit")
    p_crawl.add_argument("--sync", action="store_true", help="Force synchronous crawler")
    p_crawl.add_argument("--formats", nargs="+", choices=["json", "csv", "sqlite"],
                          help="Export formats to produce")
    p_crawl.add_argument("--env", help="Path to a specific .env file")
    p_crawl.set_defaults(func=cmd_crawl)

    p_search = sub.add_parser("search", help="Keyword search over a crawl's JSON export")
    p_search.add_argument("--input", required=True, help="Path to crawl JSON export")
    p_search.add_argument("--keyword", required=True, help="Keyword to search for")
    p_search.add_argument("--limit", type=int, default=10, help="Max results to show")
    p_search.set_defaults(func=cmd_search)

    p_analyze = sub.add_parser("analyze", help="Keyword frequency analysis")
    p_analyze.add_argument("--input", required=True, help="Path to crawl JSON export")
    p_analyze.add_argument("--top", type=int, default=25, help="Number of top keywords")
    p_analyze.set_defaults(func=cmd_analyze)

    p_sitemap = sub.add_parser("sitemap", help="Generate an XML sitemap from a crawl JSON export")
    p_sitemap.add_argument("--input", required=True, help="Path to crawl JSON export")
    p_sitemap.add_argument("--output", default="exports/sitemap.xml", help="Output sitemap path")
    p_sitemap.set_defaults(func=cmd_sitemap)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:  # noqa: BLE001 - top-level CLI error boundary
        console.print(f"[bold red]Error:[/bold red] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
