"""Unit tests for processing.deduplication (no network)."""
from data_model import BOOKS_SOURCE, QUOTES_SOURCE
from processing.cleaning import clean_record
from processing.deduplication import deduplicate, fingerprint, normalize_for_fingerprint


def book(title, url="https://books.toscrape.com/catalogue/x_1/index.html"):
    return {"source": BOOKS_SOURCE, "source_url": url, "name_or_title": title}


def quote(text, author="Albert Einstein"):
    return {"source": QUOTES_SOURCE, "source_url": "https://quotes.toscrape.com/", "name_or_title": text, "author": author}


def test_assignment_example_titles_are_duplicates():
    variants = ["Example Book Title", " Example Book Title ", "EXAMPLE BOOK TITLE"]
    assert len({fingerprint(book(title)) for title in variants}) == 1


def test_whitespace_punctuation_and_case_are_ignored():
    assert normalize_for_fingerprint("  Hello,\tWORLD!!  ") == "hello world"
    assert fingerprint(book("It's a Book")) == fingerprint(book("its  a   BOOK"))


def test_different_titles_are_not_duplicates():
    assert fingerprint(book("Book A")) != fingerprint(book("Book B"))


def test_same_title_in_different_sources_is_not_a_duplicate():
    assert fingerprint(book("Same")) != fingerprint({"source": QUOTES_SOURCE, "name_or_title": "Same", "author": ""})


def test_quote_duplicates_use_author_and_first_50_characters():
    text = "The world as we have created it is a process of our thinking."
    assert fingerprint(quote(text)) == fingerprint(quote("  " + text.upper() + " "))
    # same text, different author -> different quote
    assert fingerprint(quote(text)) != fingerprint(quote(text, author="Someone Else"))
    # only the first 50 normalised characters count
    assert fingerprint(quote(text)) == fingerprint(quote(text[:50] + " and a different ending"))


def test_deduplicate_keeps_first_and_reports_duplicates():
    records = [
        book("Example Book Title"),
        book(" Example Book Title "),
        book("EXAMPLE BOOK TITLE"),
        book("Another Book"),
    ]
    unique, duplicates = deduplicate(records)
    assert [r["name_or_title"] for r in unique] == ["Example Book Title", "Another Book"]
    assert len(duplicates) == 2


def test_deduplicate_works_on_cleaned_records():
    raw = [
        {"source": BOOKS_SOURCE, "source_url": "https://books.toscrape.com/a/index.html", "name_or_title": "  Dune\xa0"},
        {"source": BOOKS_SOURCE, "source_url": "https://books.toscrape.com/b/index.html", "name_or_title": "DUNE"},
    ]
    unique, duplicates = deduplicate([clean_record(r) for r in raw])
    assert len(unique) == 1 and len(duplicates) == 1


def test_deduplicate_empty_input():
    assert deduplicate([]) == ([], [])
