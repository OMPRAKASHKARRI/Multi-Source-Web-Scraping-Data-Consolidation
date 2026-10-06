"""Scraper for https://quotes.toscrape.com/ (selectors isolated in this module)."""
from __future__ import annotations

import logging

from bs4 import Tag

from data_model import QUOTES_SOURCE, Record, new_record
from scrapers.base_scraper import BaseScraper, select_text

logger = logging.getLogger(__name__)


class QuotesScraper(BaseScraper):
    """Scrapes quotes with author and tags.

    Individual quotes have no URL of their own, so ``source_url`` is the URL
    of the listing page the quote was found on.
    """

    source_name = QUOTES_SOURCE
    default_start_url = "https://quotes.toscrape.com/"
    record_selector = "div.quote"

    def parse_record(self, element: Tag, page_url: str) -> Record:
        return new_record(
            QUOTES_SOURCE,
            source_url=page_url,
            name_or_title=select_text(element, "span.text"),
            author=select_text(element, "small.author"),
            tags=[tag.get_text() for tag in element.select("a.tag")],
        )
