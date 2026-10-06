"""Scraper parsing + pagination tests against inline HTML fixtures (no network)."""
from data_model import BOOKS_SOURCE, QUOTES_SOURCE
from scrapers import BooksScraper, FetchError, QuotesScraper

BOOK_HTML = """
<article class="product_pod">
  <p class="star-rating Three"><i class="icon-star"></i></p>
  <h3><a href="{href}" title="{title}">{short}</a></h3>
  <div class="product_price"><p class="price_color">Â£51.77</p></div>
</article>
"""


def books_page(items, next_href=None, sidebar=""):
    articles = "".join(BOOK_HTML.format(href=h, title=t, short=t[:10] + "...") for h, t in items)
    pager = f'<ul class="pager"><li class="next"><a href="{next_href}">next</a></li></ul>' if next_href else ""
    return f"<html><body>{sidebar}<section>{articles}</section>{pager}</body></html>"


def quotes_page(quotes, next_href=None):
    blocks = "".join(
        f'<div class="quote"><span class="text">\u201c{text}\u201d</span>'
        f'<span>by <small class="author">{author}</small></span>'
        f'<div class="tags">{"".join(f"<a class=tag href=/t/{t}>{t}</a>" for t in tags)}</div></div>'
        for text, author, tags in quotes
    )
    pager = f'<ul class="pager"><li class="next"><a href="{next_href}">Next</a></li></ul>' if next_href else ""
    return f"<html><body>{blocks}{pager}</body></html>"


class FakeResponse:
    def __init__(self, html, url):
        self.content = html.encode("utf-8")
        self.url = url


class FakeClient:
    """Serves pages from a dict; missing URLs raise FetchError."""

    def __init__(self, pages):
        self.pages = pages
        self.requested = []

    def get(self, url):
        self.requested.append(url)
        if url not in self.pages:
            raise FetchError(f"no page for {url}")
        return FakeResponse(self.pages[url], url)


def test_books_parsing_uses_title_attribute_and_resolves_urls():
    client = FakeClient({"https://b.test/": books_page([("catalogue/dune_1/index.html", "A Very Long Book Title Indeed")])})
    result = BooksScraper(client, "https://b.test/").scrape()
    record = result.records[0]
    assert record["source"] == BOOKS_SOURCE
    assert record["name_or_title"] == "A Very Long Book Title Indeed"  # not the truncated link text
    assert record["source_url"] == "https://b.test/catalogue/dune_1/index.html"
    assert record["rating"] == "Three"
    assert "51.77" in record["price"]


def test_books_pagination_follows_relative_next_links_until_the_end():
    pages = {
        "https://b.test/": books_page([("catalogue/a_1/index.html", "Book A")], next_href="catalogue/page-2.html"),
        "https://b.test/catalogue/page-2.html": books_page([("b_2/index.html", "Book B")], next_href="page-3.html"),
        "https://b.test/catalogue/page-3.html": books_page([("c_3/index.html", "Book C")]),
    }
    client = FakeClient(pages)
    result = BooksScraper(client, "https://b.test/").scrape()
    assert [r["name_or_title"] for r in result.records] == ["Book A", "Book B", "Book C"]
    assert result.pages_fetched == 3 and result.pages_failed == 0
    assert result.records[2]["source_url"] == "https://b.test/catalogue/c_3/index.html"


def test_books_categories_are_mapped_from_category_pages():
    sidebar = (
        '<div class="side_categories"><ul class="nav-list"><li><a href="catalogue/category/books_1/index.html">Books</a>'
        '<ul><li><a href="catalogue/category/books/travel_2/index.html">Travel</a></li></ul></li></ul></div>'
    )
    pages = {
        "https://b.test/": books_page([("catalogue/a_1/index.html", "Book A")], sidebar=sidebar),
        "https://b.test/catalogue/category/books/travel_2/index.html": books_page([("../../../a_1/index.html", "Book A")]),
    }
    result = BooksScraper(FakeClient(pages), "https://b.test/").scrape()
    assert result.records[0]["category"] == "Travel"


def test_books_category_failure_is_not_fatal():
    result = BooksScraper(FakeClient({"https://b.test/": books_page([("a_1/index.html", "Book A")])}), "https://b.test/").scrape()
    assert len(result.records) == 1
    assert result.records[0]["category"] is None
    assert any(w.startswith("category_missing") for w in result.warnings)


def test_failed_page_stops_pagination_but_keeps_earlier_records():
    pages = {"https://b.test/": books_page([("a_1/index.html", "Book A")], next_href="page-2.html")}  # page-2 missing
    result = BooksScraper(FakeClient(pages), "https://b.test/").scrape()
    assert len(result.records) == 1
    assert result.pages_failed == 1


def test_missing_elements_do_not_crash_the_scraper():
    html = '<html><body><article class="product_pod"><p>nothing useful</p></article></body></html>'
    result = BooksScraper(FakeClient({"https://b.test/": html}), "https://b.test/").scrape()
    record = result.records[0]
    assert record["name_or_title"] is None and record["source_url"] is None and record["price"] is None


def test_pagination_loop_is_detected():
    pages = {"https://b.test/": books_page([("a_1/index.html", "Book A")], next_href="https://b.test/")}
    result = BooksScraper(FakeClient(pages), "https://b.test/").scrape()
    assert result.pages_fetched == 1


def test_max_pages_cap():
    pages = {f"https://q.test/page/{n}/": quotes_page([(f"Quote {n}", "A", ["x"])], f"/page/{n + 1}/") for n in range(1, 10)}
    result = QuotesScraper(FakeClient(pages), "https://q.test/page/1/", max_pages=3).scrape()
    assert result.pages_fetched == 3


def test_quotes_parsing_and_absolute_next_link():
    pages = {
        "https://q.test/": quotes_page([("Be yourself.", "Oscar Wilde", ["Life", "inspirational"])], "/page/2/"),
        "https://q.test/page/2/": quotes_page([("Stay hungry.", "Steve Jobs", [])]),
    }
    result = QuotesScraper(FakeClient(pages), "https://q.test/").scrape()
    first, second = result.records
    assert first["source"] == QUOTES_SOURCE
    assert first["author"] == "Oscar Wilde"
    assert first["tags"] == ["Life", "inspirational"]  # raw; cleaning lowercases/sorts
    assert first["source_url"] == "https://q.test/"
    assert second["source_url"] == "https://q.test/page/2/"
    assert second["tags"] == []


def test_no_category_lookup_when_nothing_was_scraped():
    client = FakeClient({})  # start page fails
    result = BooksScraper(client, "https://b.test/").scrape()
    assert result.records == [] and result.pages_failed == 1
    assert client.requested == ["https://b.test/"]  # fetched once, not re-requested for categories
