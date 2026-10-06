"""Unit tests for processing.validation (no network)."""
from data_model import BOOKS_SOURCE, QUOTES_SOURCE
from processing.validation import validate_record, validate_records


def book(**overrides):
    record = {
        "source": BOOKS_SOURCE,
        "source_url": "https://books.toscrape.com/catalogue/a_1/index.html",
        "name_or_title": "A Light in the Attic",
        "category": None,
        "price": 51.77,
        "rating": 3,
        "author": None,
        "tags": None,
        "description": None,
        "scraped_at": "2026-01-01T00:00:00Z",
    }
    record.update(overrides)
    return record


def quote(**overrides):
    record = {
        "source": QUOTES_SOURCE,
        "source_url": "https://quotes.toscrape.com/",
        "name_or_title": "Be yourself.",
        "author": "Oscar Wilde",
        "tags": "life",
        "price": None,
        "rating": None,
    }
    record.update(overrides)
    return record


def test_valid_book_has_no_problems():
    assert validate_record(book()) == []


def test_valid_quote_has_no_problems():
    assert validate_record(quote()) == []


def test_missing_title():
    assert validate_record(book(name_or_title=None)) == ["missing_name"]
    assert validate_record(book(name_or_title="   ")) == ["missing_name"]


def test_missing_and_invalid_url():
    assert validate_record(book(source_url=None)) == ["missing_url"]
    assert validate_record(book(source_url="books.toscrape.com/x")) == ["invalid_url"]


def test_multiple_problems_are_all_reported():
    assert validate_record(book(name_or_title=None, source_url="nope")) == ["missing_name", "invalid_url"]


def test_invalid_price():
    assert validate_record(book(price="free")) == ["invalid_price"]
    assert validate_record(book(price=float("nan"))) == ["invalid_price"]


def test_negative_price():
    assert validate_record(book(price=-1.0)) == ["negative_price"]


def test_zero_price_is_allowed():
    assert validate_record(book(price=0)) == []


def test_invalid_rating():
    for bad in (0, 6, "Zero", 3.5, True):
        assert validate_record(book(rating=bad)) == ["invalid_rating"], bad


def test_rating_bounds_accepted():
    assert validate_record(book(rating=1)) == []
    assert validate_record(book(rating=5)) == []


def test_unknown_source():
    assert "unknown_source" in validate_record(book(source="Some Other Site"))
    assert "unknown_source" in validate_record(book(source=None))


def test_quote_requires_author():
    assert validate_record(quote(author=None)) == ["missing_author"]


def test_validate_records_counts_rejections_and_reasons():
    records = [book(), book(name_or_title=None, price=-2), quote(source_url="bad")]
    valid, rejected, reasons = validate_records(records)
    assert len(valid) == 1
    assert rejected == 2
    assert reasons == {"missing_name": 1, "negative_price": 1, "invalid_url": 1}
