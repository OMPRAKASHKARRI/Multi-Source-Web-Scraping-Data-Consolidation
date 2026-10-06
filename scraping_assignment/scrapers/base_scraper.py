"""Reusable HTTP layer and pagination loop shared by every scraper.

Two classes live here:

* :class:`HttpClient` - a ``requests.Session`` wrapper adding a User-Agent,
  timeout, polite delay, status checking and retries with exponential backoff.
* :class:`BaseScraper` - follows ``li.next > a`` links page by page and hands
  each record element to a source-specific ``parse_record`` implementation.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, ClassVar, Iterator, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from data_model import Record

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; ScrapingAssignmentBot/1.0; educational use)"
REQUEST_TIMEOUT_SECONDS = 15
MAX_RETRIES = 3  # retries *after* the first attempt -> 4 attempts in total
BACKOFF_FACTOR_SECONDS = 1.0  # waits 1s, 2s, 4s between attempts
MAX_RETRY_AFTER_SECONDS = 30.0
REQUEST_DELAY_SECONDS = 0.5
RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_PAGES = 200  # safety cap so a broken "next" link can never loop forever
NEXT_PAGE_SELECTOR = "li.next > a"


class FetchError(Exception):
    """Raised when a URL could not be fetched after all retries."""


class HttpClient:
    """Polite HTTP GET client with retries, exponential backoff and a delay.

    ``sleep`` and ``clock`` are injectable so tests run instantly.
    """

    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
        backoff_factor: float = BACKOFF_FACTOR_SECONDS,
        delay: float = REQUEST_DELAY_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT})
        self.session = session
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.delay = delay
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: Optional[float] = None

    def get(self, url: str) -> requests.Response:
        """GET ``url``; retry temporary failures; raise :class:`FetchError` if it fails."""
        attempts = self.max_retries + 1
        reason = "unknown error"
        for attempt in range(1, attempts + 1):
            self._wait_for_rate_limit()
            retry_after: Optional[float] = None
            try:
                response = self.session.get(url, timeout=self.timeout)
            except (requests.Timeout, requests.ConnectionError) as exc:
                reason = f"{type(exc).__name__}: {exc}"
            except requests.RequestException as exc:
                # Invalid URL, too many redirects, ... - retrying will not help.
                raise FetchError(f"Request to {url} failed: {exc}") from exc
            else:
                if response.ok:
                    return response
                if response.status_code not in RETRY_STATUS_CODES:
                    raise FetchError(
                        f"HTTP {response.status_code} for {url} (not retryable)"
                    )
                reason = f"HTTP {response.status_code}"
                retry_after = self._parse_retry_after(response)
            finally:
                self._last_request_at = self._clock()

            if attempt < attempts:
                wait = self.backoff_factor * 2 ** (attempt - 1)
                if retry_after is not None:
                    wait = max(wait, retry_after)
                logger.warning(
                    "Attempt %d/%d failed for %s (%s); retrying in %.1fs",
                    attempt, attempts, url, reason, wait,
                )
                self._sleep(wait)
        raise FetchError(f"Giving up on {url} after {attempts} attempts: {reason}")

    def close(self) -> None:
        """Close the underlying session."""
        self.session.close()

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self.delay - (self._clock() - self._last_request_at)
        if remaining > 0:
            self._sleep(remaining)

    @staticmethod
    def _parse_retry_after(response: requests.Response) -> Optional[float]:
        value = response.headers.get("Retry-After")
        try:
            return min(float(value), MAX_RETRY_AFTER_SECONDS) if value else None
        except ValueError:  # HTTP-date form is not supported; fall back to backoff
            return None


@dataclass
class ScrapeResult:
    """Everything a scraper hands back to the pipeline."""

    records: list[Record] = field(default_factory=list)
    pages_fetched: int = 0
    pages_failed: int = 0
    parse_errors: int = 0
    warnings: list[str] = field(default_factory=list)


def select_text(element: Tag, css_selector: str) -> Optional[str]:
    """Return the text of the first match inside ``element`` or ``None`` if absent."""
    match = element.select_one(css_selector)
    return match.get_text() if match is not None else None


def parse_html(content: bytes) -> BeautifulSoup:
    """Parse raw bytes (not ``response.text``) so the page's own charset is honoured."""
    return BeautifulSoup(content, "lxml")


class BaseScraper(ABC):
    """Template for a paginated scraper; subclasses only parse one record."""

    source_name: ClassVar[str]
    default_start_url: ClassVar[str]
    record_selector: ClassVar[str]

    def __init__(
        self,
        client: HttpClient,
        start_url: Optional[str] = None,
        max_pages: int = MAX_PAGES,
    ) -> None:
        self.client = client
        self.start_url = start_url or self.default_start_url
        self.max_pages = max_pages

    @abstractmethod
    def parse_record(self, element: Tag, page_url: str) -> Record:
        """Convert one record element into a raw (uncleaned) record."""

    def scrape(self) -> ScrapeResult:
        """Scrape every page reachable from ``start_url``."""
        result = ScrapeResult()
        logger.info("[%s] Starting scrape at %s", self.source_name, self.start_url)
        for soup, page_url in self.iter_pages(self.start_url, result):
            records = self.parse_page(soup, page_url, result)
            logger.info(
                "[%s] Page %d (%s): %d records",
                self.source_name, result.pages_fetched, page_url, len(records),
            )
            result.records.extend(records)
        logger.info(
            "[%s] Finished: %d records, %d pages fetched, %d pages failed, %d parse errors",
            self.source_name, len(result.records), result.pages_fetched,
            result.pages_failed, result.parse_errors,
        )
        return result

    def iter_pages(
        self, start_url: str, result: ScrapeResult
    ) -> Iterator[tuple[BeautifulSoup, str]]:
        """Yield ``(soup, url)`` for each page by following the *next* link.

        Stops when there is no next link, a page cannot be fetched (its next
        link is unknown), a URL repeats, or ``max_pages`` is reached.
        """
        url: Optional[str] = start_url
        visited: set[str] = set()
        while url:
            if url in visited:
                logger.warning("[%s] Pagination loop detected at %s; stopping", self.source_name, url)
                return
            if len(visited) >= self.max_pages:
                logger.warning("[%s] Reached max_pages=%d; stopping", self.source_name, self.max_pages)
                return
            visited.add(url)
            try:
                response = self.client.get(url)
            except FetchError as exc:
                result.pages_failed += 1
                logger.error("[%s] Page failed, stopping pagination here: %s", self.source_name, exc)
                return
            result.pages_fetched += 1
            soup = parse_html(response.content)
            yield soup, response.url
            url = self.find_next_url(soup, response.url)

    @staticmethod
    def find_next_url(soup: BeautifulSoup, page_url: str) -> Optional[str]:
        """Return the absolute URL of the next page, or ``None`` on the last page."""
        link = soup.select_one(NEXT_PAGE_SELECTOR)
        href = link.get("href") if link is not None else None
        return urljoin(page_url, str(href)) if href else None

    def parse_page(self, soup: BeautifulSoup, page_url: str, result: ScrapeResult) -> list[Record]:
        """Parse all record elements on a page; one bad record never aborts the page."""
        elements = soup.select(self.record_selector)
        if not elements:
            logger.warning(
                "[%s] No elements matched '%s' on %s", self.source_name, self.record_selector, page_url
            )
        records: list[Record] = []
        for index, element in enumerate(elements, start=1):
            try:
                records.append(self.parse_record(element, page_url))
            except (AttributeError, KeyError, TypeError, ValueError) as exc:
                result.parse_errors += 1
                logger.warning(
                    "[%s] Could not parse record #%d on %s: %s: %s",
                    self.source_name, index, page_url, type(exc).__name__, exc,
                )
        return records
