"""End-to-end pipeline tests with fake scrapers (no network)."""
import csv

from data_model import BOOKS_SOURCE, OUTPUT_COLUMNS, QUOTES_SOURCE, new_record
from output_writer import write_dataset_csv, write_summary_report
from pipeline import run_pipeline
from scrapers.base_scraper import BaseScraper, ScrapeResult


class StaticScraper(BaseScraper):
    default_start_url = "http://x/"
    record_selector = "x"

    def __init__(self, name, records, parse_errors=0, crash=False):
        self.source_name = name
        self._records, self._parse_errors, self._crash = records, parse_errors, crash

    def parse_record(self, element, page_url):  # pragma: no cover - unused
        raise NotImplementedError

    def scrape(self):
        if self._crash:
            raise RuntimeError("boom")
        return ScrapeResult(records=self._records, pages_fetched=1, parse_errors=self._parse_errors)


def book(title, price="£10.00", rating="Two", url="https://books.toscrape.com/x/index.html"):
    return new_record(BOOKS_SOURCE, name_or_title=title, price=price, rating=rating, source_url=url)


def quote(text, author="Anon"):
    return new_record(QUOTES_SOURCE, name_or_title=f"\u201c{text}\u201d", author=author,
                      tags=["B", "a"], source_url="https://quotes.toscrape.com/")


def test_counts_reconcile_and_reasons_are_reported():
    books = StaticScraper(BOOKS_SOURCE, [
        book("Good"), book(" good "), book("Bad price", price="free"), book(None), book("Bad rating", rating="Seven"),
    ], parse_errors=1)
    quotes = StaticScraper(QUOTES_SOURCE, [quote("One"), quote("Two")])
    result = run_pipeline([books, quotes])

    b = result.report["sources"][BOOKS_SOURCE]
    assert (b["raw_records"], b["cleaned_records"], b["rejected_records"], b["duplicates"], b["final_records"]) == (6, 5, 4, 1, 1)
    assert b["rejection_reasons"] == {"invalid_price": 1, "invalid_rating": 1, "missing_name": 1, "parse_error": 1}
    assert result.report["sources"][QUOTES_SOURCE]["final_records"] == 2
    assert result.report["final_record_count"] == 3 == len(result.records)
    assert result.report["counts_reconcile"] is True


def test_one_crashing_source_does_not_stop_the_other():
    result = run_pipeline([StaticScraper(BOOKS_SOURCE, [], crash=True), StaticScraper(QUOTES_SOURCE, [quote("One")])])
    assert result.report["sources"][BOOKS_SOURCE]["error"] == "RuntimeError: boom"
    assert result.report["final_record_count"] == 1


def test_csv_and_report_output(tmp_path):
    result = run_pipeline([StaticScraper(BOOKS_SOURCE, [book("Good")]), StaticScraper(QUOTES_SOURCE, [quote("One")])])
    csv_path = tmp_path / "out" / "final_dataset.csv"
    write_dataset_csv(result.records, csv_path)
    write_summary_report(result.report, tmp_path / "out" / "summary_report.json")

    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert tuple(reader.fieldnames) == OUTPUT_COLUMNS
    assert {r["source"] for r in rows} == {BOOKS_SOURCE, QUOTES_SOURCE}
    book_row = next(r for r in rows if r["source"] == BOOKS_SOURCE)
    assert book_row["price"] == "10.00" and book_row["rating"] == "2" and book_row["author"] == ""
    quote_row = next(r for r in rows if r["source"] == QUOTES_SOURCE)
    assert quote_row["tags"] == "a;b" and quote_row["name_or_title"] == "One" and quote_row["price"] == ""
    assert (tmp_path / "out" / "summary_report.json").exists()
