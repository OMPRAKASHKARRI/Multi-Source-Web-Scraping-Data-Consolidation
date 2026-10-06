"""Source-specific scrapers and the shared HTTP/pagination layer."""
from scrapers.base_scraper import BaseScraper, FetchError, HttpClient, ScrapeResult
from scrapers.books_scraper import BooksScraper
from scrapers.quotes_scraper import QuotesScraper

__all__ = [
    "BaseScraper",
    "BooksScraper",
    "FetchError",
    "HttpClient",
    "QuotesScraper",
    "ScrapeResult",
]
