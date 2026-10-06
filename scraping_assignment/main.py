"""Entry point: ``python main.py`` runs the full scraping pipeline."""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from output_writer import write_dataset_csv, write_summary_report
from pipeline import run_pipeline
from scrapers import BooksScraper, HttpClient, QuotesScraper
from scrapers.base_scraper import MAX_PAGES, REQUEST_DELAY_SECONDS

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_LOG_FILE = BASE_DIR / "logs" / "scraper.log"
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

logger = logging.getLogger("main")


def configure_logging(log_file: Path) -> None:
    """Log to console and to ``log_file`` (overwritten each run), in UTC."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)
    formatter.converter = time.gmtime
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, mode="w", encoding="utf-8"),
    ]
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    for handler in handlers:
        handler.setFormatter(formatter)
        root.addHandler(handler)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-source web scraping & consolidation pipeline")
    parser.add_argument("--fetch-descriptions", action="store_true",
                        help="Also open every book detail page for its description (~1000 extra requests)")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES,
                        help=f"Safety cap on pages per source (default {MAX_PAGES})")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY_SECONDS,
                        help=f"Seconds between requests (default {REQUEST_DELAY_SECONDS})")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_FILE)
    parser.add_argument("--books-url", default=None, help="Override start URL (testing / local mirrors)")
    parser.add_argument("--quotes-url", default=None, help="Override start URL (testing / local mirrors)")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_file)
    logger.info("Pipeline started")

    client = HttpClient(delay=args.delay)
    scrapers = [
        BooksScraper(client, args.books_url, args.max_pages, args.fetch_descriptions),
        QuotesScraper(client, args.quotes_url, args.max_pages),
    ]
    try:
        result = run_pipeline(scrapers)
    finally:
        client.close()

    write_dataset_csv(result.records, args.output_dir / "final_dataset.csv")
    write_summary_report(result.report, args.output_dir / "summary_report.json")

    for name, stats in result.report["sources"].items():
        logger.info("Summary [%s]: %s", name, stats)
    logger.info(
        "Pipeline finished: %d final records in %.2fs (counts reconcile: %s)",
        result.report["final_record_count"], result.report["duration_seconds"],
        result.report["counts_reconcile"],
    )
    if result.report["final_record_count"] == 0:
        logger.error("No records were produced - check the log for request failures")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
