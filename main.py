"""
main.py
=======
Minimal programmatic entry point (as an alternative to the CLI) for
running a crawl directly, e.g. `python main.py`. Reads configuration
from `.env` and prints a summary. For the full-featured interface with
subcommands (search/analyze/sitemap), use `cli.py`.
"""

from __future__ import annotations

import asyncio

from crawler_pkg import Config, Crawler, AsyncCrawler, Exporter


def run() -> None:
    config = Config.from_env()

    if config.use_async:
        crawler = AsyncCrawler(config)
        pages = asyncio.run(crawler.crawl())
    else:
        crawler = Crawler(config)
        pages = crawler.crawl()

    exporter = Exporter(config.output_dir)
    outputs = exporter.export(pages, config.export_formats)

    print("Crawl complete.")
    print("Stats:", crawler.stats.to_dict())
    print("Exports:", outputs)


if __name__ == "__main__":
    run()
