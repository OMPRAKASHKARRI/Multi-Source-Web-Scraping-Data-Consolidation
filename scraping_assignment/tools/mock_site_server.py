"""Local mock of books.toscrape.com / quotes.toscrape.com markup for offline integration testing."""
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

BOOKS = [  # (slug, title, price, rating, category)
    ("dune_1", "Dune: A Very Long Title That Gets Truncated", "£12.50", "Five", "Science Fiction"),
    ("emma_2", "Emma", "£7.00", "Three", "Classics"),
    ("ulysses_3", "Ulysses", "£20.10", "Two", "Classics"),
    ("hobbit_4", "The Hobbit", "£9.99", "Four", "Fantasy"),
    ("neg_5", "Negative Price Book", "£-3.00", "One", "Fantasy"),
    ("zero_6", "Zero Rating Book", "£5.00", "Zero", "Fantasy"),
    ("dupe_7", "  DUNE: a very long title that gets truncated ", "£12.50", "Five", "Science Fiction"),
    ("odd_8", "Odd\xa0\xa0Whitespace\n  Book", "Â£4.25", "Three", "Classics"),
]
PAGE_SIZE = 4
QUOTES = [  # (text, author, tags)
    ("The world as we have created it is a process of our thinking.", "Albert Einstein", ["change", "Deep-Thoughts"]),
    ("It is our choices that show what we truly are.", "J.K. Rowling", ["abilities", "choices"]),
    ("There are only two ways to live your life.", "Albert Einstein", ["inspirational", "life"]),
    ("  THE WORLD AS WE HAVE CREATED IT IS A PROCESS OF OUR THINKING!  ", "albert einstein", ["Change"]),
    ("Quote without an author.", "", ["orphan"]),
    ("Last quote on last page.", "Jane Austen", []),
]
QUOTES_PER_PAGE = 2
flaky_hits = {"books_page2": 0}


def book_article(slug, title, price, rating, href_prefix):
    return (f'<article class="product_pod"><div class="image_container"><a href="{href_prefix}{slug}/index.html"></a></div>'
            f'<p class="star-rating {rating}"></p><h3><a href="{href_prefix}{slug}/index.html" title="{title}">{title[:12]}...</a></h3>'
            f'<div class="product_price"><p class="price_color">{price}</p></div></article>')


def books_listing(page, total_pages):
    items = BOOKS[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
    prefix = "catalogue/" if page == 1 else ""
    articles = "".join(book_article(s, t, p, r, prefix) for s, t, p, r, _ in items)
    nxt = ""
    if page < total_pages:
        nxt = f'<li class="next"><a href="{"catalogue/" if page == 1 else ""}page-{page + 1}.html">next</a></li>'
    side = ""
    if page == 1:
        cats = sorted({b[4] for b in BOOKS})
        side = ('<div class="side_categories"><ul class="nav-list"><li><a href="catalogue/category/books_1/index.html">Books</a><ul>'
                + "".join(f'<li><a href="catalogue/category/books/{c.lower().replace(" ", "-")}/index.html">\n   {c}\n  </a></li>' for c in cats)
                + "</ul></li></ul></div>")
    return f"<html><body>{side}<ol>{articles}</ol><ul class=\"pager\">{nxt}</ul></body></html>"


def category_page(cat):
    items = [b for b in BOOKS if b[4].lower().replace(" ", "-") == cat]
    return "<html><body><ol>" + "".join(book_article(s, t, p, r, "../../../") for s, t, p, r, _ in items) + "</ol></body></html>"


def quotes_listing(page):
    chunk = QUOTES[(page - 1) * QUOTES_PER_PAGE: page * QUOTES_PER_PAGE]
    blocks = "".join(
        '<div class="quote"><span class="text">\u201c%s\u201d</span><span>by %s</span><div class="tags">%s</div></div>'
        % (t, f'<small class="author">{a}</small>' if a else "", "".join(f'<a class="tag" href="/tag/x/">{x}</a>' for x in tg))
        for t, a, tg in chunk)
    last = -(-len(QUOTES) // QUOTES_PER_PAGE)
    nxt = f'<li class="next"><a href="/page/{page + 1}/">Next</a></li>' if page < last else ""
    return f'<html><body>{blocks}<ul class="pager">{nxt}</ul></body></html>'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, status, html=""):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html")  # deliberately no charset, like the real site
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path
        total = -(-len(BOOKS) // PAGE_SIZE)
        if path == "/books/" or path == "/books":
            return self.reply(200, books_listing(1, total))
        m = re.fullmatch(r"/books/catalogue/page-(\d+)\.html", path)
        if m:
            n = int(m.group(1))
            if n == 2 and flaky_hits["books_page2"] < 1:
                flaky_hits["books_page2"] += 1
                return self.reply(503, "temporarily unavailable")
            return self.reply(200, books_listing(n, total)) if 1 <= n <= total else self.reply(404)
        m = re.fullmatch(r"/books/catalogue/category/books/([\w-]+)/index\.html", path)
        if m:
            return self.reply(200, category_page(m.group(1)))
        m = re.fullmatch(r"/books/catalogue/(\w+)/index\.html", path)
        if m:
            return self.reply(200, f'<html><body><div id="product_description"></div><p>Description of {m.group(1)}</p></body></html>')
        if re.fullmatch(r"/quotes/?", path):
            return self.reply(200, quotes_listing(1))
        m = re.fullmatch(r"/page/(\d+)/", path)
        if m:
            return self.reply(200, quotes_listing(int(m.group(1))))
        self.reply(404)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
