"""Shared constants and helpers describing the common output schema.

Both scrapers emit records in this schema, so the processing layer never needs
to know which website a record came from (apart from the source-specific
cleaning/validation/deduplication rules, which key off ``source``).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

BOOKS_SOURCE = "Books to Scrape"
QUOTES_SOURCE = "Quotes to Scrape"
KNOWN_SOURCES = (BOOKS_SOURCE, QUOTES_SOURCE)

# Fixed column order for the final CSV (also the set of allowed record keys).
OUTPUT_COLUMNS = (
    "source",
    "source_url",
    "name_or_title",
    "category",
    "price",
    "rating",
    "author",
    "tags",
    "description",
    "scraped_at",
)

Record = dict[str, Any]


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string (second precision)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_record(source: str, **fields: Any) -> Record:
    """Create a record with every schema column set to ``None``.

    ``source`` and ``scraped_at`` are filled in automatically; any other
    column can be supplied as a keyword argument.
    """
    unknown = set(fields) - set(OUTPUT_COLUMNS)
    if unknown:
        raise ValueError(f"Unknown record fields: {sorted(unknown)}")
    record: Record = {column: None for column in OUTPUT_COLUMNS}
    record["source"] = source
    record["scraped_at"] = utc_now_iso()
    record.update(fields)
    return record
