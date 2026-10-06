"""Unit tests for processing.cleaning (no network)."""
import pytest

from data_model import BOOKS_SOURCE, QUOTES_SOURCE
from processing.cleaning import (
    clean_price,
    clean_rating,
    clean_record,
    clean_tags,
    clean_text,
    normalize_url,
    strip_quotes,
)


class TestCleanText:
    def test_whitespace_cleanup(self):
        assert clean_text("  Hello \n World ") == "Hello World"

    def test_tabs_and_multiple_spaces(self):
        assert clean_text("a\t\tb    c") == "a b c"

    def test_non_breaking_space(self):
        assert clean_text("Price:\xa0\xa0£5") == "Price: £5"

    def test_none_becomes_empty_string(self):
        assert clean_text(None) == ""


class TestStripQuotes:
    def test_curly_quotes(self):
        assert strip_quotes("\u201cThe world is what we think.\u201d") == "The world is what we think."

    def test_straight_quotes_and_spaces(self):
        assert strip_quotes('  "Hi there"  ') == "Hi there"

    def test_unquoted_text_untouched(self):
        assert strip_quotes("No quotes here") == "No quotes here"

    def test_only_one_pair_removed(self):
        assert strip_quotes("\u201c\u2018Nested\u2019\u201d") == "\u2018Nested\u2019"


class TestCleanPrice:
    @pytest.mark.parametrize(
        "raw, expected",
        [("£51.77", 51.77), ("Â£51.77", 51.77), (" £ 1,234.50 ", 1234.5), ("10", 10.0), (12.345, 12.35)],
    )
    def test_valid(self, raw, expected):
        assert clean_price(raw) == expected

    @pytest.mark.parametrize("raw", ["", "free", None, True])
    def test_unparseable_returns_none(self, raw):
        assert clean_price(raw) is None

    def test_negative_is_preserved_for_validation(self):
        assert clean_price("-£5.00") == -5.0


class TestCleanRating:
    @pytest.mark.parametrize(
        "raw, expected",
        [("One", 1), ("two", 2), (" Three ", 3), ("FOUR", 4), ("Five", 5), (4, 4), ("5", 5)],
    )
    def test_conversion(self, raw, expected):
        assert clean_rating(raw) == expected

    @pytest.mark.parametrize("raw", ["Zero", "", None, "great"])
    def test_unrecognised_returns_none(self, raw):
        assert clean_rating(raw) is None


class TestCleanTags:
    def test_trim_lowercase_sort_join(self):
        assert clean_tags([" Love ", "LIFE", "books"]) == "books;life;love"

    def test_deduplicates_and_drops_empty(self):
        assert clean_tags(["a", "A", "", "  "]) == "a"

    def test_empty_returns_none(self):
        assert clean_tags([]) is None
        assert clean_tags(None) is None

    def test_accepts_delimited_string(self):
        assert clean_tags("Zebra; apple") == "apple;zebra"


class TestNormalizeUrl:
    def test_absolute_url_kept(self):
        assert normalize_url("https://books.toscrape.com/catalogue/x/index.html") == (
            "https://books.toscrape.com/catalogue/x/index.html"
        )

    def test_relative_url_resolved_against_base(self):
        assert normalize_url("../x/index.html", base="https://books.toscrape.com/catalogue/page-2.html") == (
            "https://books.toscrape.com/x/index.html"
        )

    def test_host_lowercased_and_fragment_dropped(self):
        assert normalize_url("HTTPS://Quotes.ToScrape.com/page/2/#top") == "https://quotes.toscrape.com/page/2/"

    @pytest.mark.parametrize("bad", ["", None, "not a url", "ftp://x.com/a", "books.toscrape.com/x", "/relative/only"])
    def test_invalid_returns_none(self, bad):
        assert normalize_url(bad) is None


class TestCleanRecord:
    def test_book_record(self):
        raw = {
            "source": BOOKS_SOURCE,
            "source_url": "https://books.toscrape.com/catalogue/a_1/index.html",
            "name_or_title": "  A Light\xa0in the Attic ",
            "price": "Â£51.77",
            "rating": "Three",
            "category": " Poetry ",
            "author": None,
            "tags": None,
            "description": "",
            "scraped_at": "2026-01-01T00:00:00Z",
        }
        cleaned = clean_record(raw)
        assert cleaned["name_or_title"] == "A Light in the Attic"
        assert cleaned["price"] == 51.77
        assert cleaned["rating"] == 3
        assert cleaned["category"] == "Poetry"
        assert cleaned["description"] is None
        assert cleaned["tags"] is None

    def test_quote_record(self):
        raw = {
            "source": QUOTES_SOURCE,
            "source_url": "https://quotes.toscrape.com/",
            "name_or_title": "\u201cBe yourself.\u201d",
            "author": " Oscar Wilde ",
            "tags": ["Life", "inspirational"],
        }
        cleaned = clean_record(raw)
        assert cleaned["name_or_title"] == "Be yourself."
        assert cleaned["author"] == "Oscar Wilde"
        assert cleaned["tags"] == "inspirational;life"
        assert cleaned["price"] is None and cleaned["rating"] is None

    def test_unparseable_values_are_kept_for_validation(self):
        cleaned = clean_record({"source": BOOKS_SOURCE, "price": "free", "rating": "Zero", "source_url": "nope"})
        assert cleaned["price"] == "free"
        assert cleaned["rating"] == "Zero"
        assert cleaned["source_url"] == "nope"

    def test_placeholder_markers_become_none(self):
        cleaned = clean_record({"source": BOOKS_SOURCE, "price": "N/A", "category": "null"})
        assert cleaned["price"] is None and cleaned["category"] is None
