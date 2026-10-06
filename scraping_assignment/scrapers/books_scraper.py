"""Scraper for https://books.toscrape.com/ (selectors isolated in this module)."""
from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urljoin

from bs4 import Tag

from data_model import BOOKS_SOURCE, Record, new_record
from scrapers.base_scraper import (
    BaseScraper,
    FetchError,
    HttpClient,
    ScrapeResult,
    MAX_PAGES,
    parse_html,
    select_text,
)

logger = logging.getLogger(__name__)

CATEGORY_LINK_SELECTOR = "div.side_categories ul ul a"  # nested list = real categories
DESCRIPTION_SELECTOR = "#product_description + p"


class BooksScraper(BaseScraper):
    """Scrapes the book catalogue.

    * Title, URL, price and rating come from the listing pages.
    * Category is resolved cheaply by crawling the category listing pages once
      (~50 categories) instead of opening every book's detail page.
    * Description only exists on detail pages (~1000 extra requests), so it is
      fetched only when ``fetch_descriptions`` is enabled.
    """

    source_name = BOOKS_SOURCE
    default_start_url = "https://books.toscrape.com/"
    record_selector = "article.product_pod"

    def __init__(
        self,
        client: HttpClient,
        start_url: Optional[str] = None,
        max_pages: int = MAX_PAGES,
        fetch_descriptions: bool = False,
    ) -> None:
        super().__init__(client, start_url, max_pages)
        self.fetch_descriptions = fetch_descriptions

    def parse_record(self, element: Tag, page_url: str) -> Record:
        link = element.select_one("h3 > a")
        title = url = None
        if link is not None:
            # The visible link text is truncated ("A Light in the ..."); the
            # title attribute holds the full title.
            title = link.get("title") or link.get_text()
            href = link.get("href")
            url = urljoin(page_url, str(href)) if href else None
        return new_record(
            BOOKS_SOURCE,
            source_url=url,
            name_or_title=title,
            price=select_text(element, "p.price_color"),
            rating=self._extract_rating(element),
        )

    @staticmethod
    def _extract_rating(element: Tag) -> Optional[str]:
        """Rating is a CSS class: ``<p class="star-rating Three">``."""
        rating_tag = element.select_one("p.star-rating")
        if rating_tag is None:
            return None
        words = [name for name in rating_tag.get("class", []) if name != "star-rating"]
        return words[0] if words else None

    def scrape(self) -> ScrapeResult:
        result = super().scrape()
        if not result.records:  # nothing scraped -> no point hitting the site again
            return result
        self._attach_categories(result)
        if self.fetch_descriptions:
            self._attach_descriptions(result)
        return result

    # -- categories -------------------------------------------------------
    def _attach_categories(self, result: ScrapeResult) -> None:
        category_by_url = self._build_category_map(result)
        for record in result.records:
            record["category"] = category_by_url.get(record["source_url"])
        missing = sum(1 for record in result.records if not record["category"])
        if missing:
            message = f"category_missing_for_{missing}_books"
            result.warnings.append(message)
            logger.warning("[%s] %s", self.source_name, message)

    def _build_category_map(self, result: ScrapeResult) -> dict[str, str]:
        """Map book URL -> category name by crawling each category's listing."""
        category_by_url: dict[str, str] = {}
        try:
            response = self.client.get(self.start_url)
        except FetchError as exc:
            logger.warning("[%s] Category index unavailable: %s", self.source_name, exc)
            result.warnings.append("category_index_unavailable")
            return category_by_url
        soup = parse_html(response.content)
        categories = [
            (link.get_text(strip=True), urljoin(response.url, str(link["href"])))
            for link in soup.select(CATEGORY_LINK_SELECTOR)
            if link.get("href")
        ]
        logger.info("[%s] Found %d categories", self.source_name, len(categories))
        scratch = ScrapeResult()  # category-page stats are tracked separately
        for name, category_url in categories:
            for page_soup, page_url in self.iter_pages(category_url, scratch):
                for link in page_soup.select(f"{self.record_selector} h3 > a[href]"):
                    category_by_url[urljoin(page_url, str(link["href"]))] = name
        if scratch.pages_failed:
            result.warnings.append(f"category_pages_failed_{scratch.pages_failed}")
        return category_by_url

    # -- descriptions -----------------------------------------------------
    def _attach_descriptions(self, result: ScrapeResult) -> None:
        failed = 0
        for record in result.records:
            url = record["source_url"]
            if not url:
                continue
            try:
                response = self.client.get(url)
            except FetchError as exc:
                failed += 1
                logger.warning("[%s] Detail page failed: %s", self.source_name, exc)
                continue
            soup = parse_html(response.content)
            tag = soup.select_one(DESCRIPTION_SELECTOR)
            record["description"] = tag.get_text() if tag is not None else None
        if failed:
            result.warnings.append(f"description_pages_failed_{failed}")
