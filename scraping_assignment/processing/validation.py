"""Record validation that returns *reasons*, not just a boolean."""
from __future__ import annotations

import logging
import math
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from data_model import KNOWN_SOURCES, QUOTES_SOURCE, Record
from processing.cleaning import is_valid_url

logger = logging.getLogger(__name__)

MIN_RATING = 1
MAX_RATING = 5


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_record(record: Mapping[str, Any]) -> list[str]:
    """Return the list of problems with ``record`` (empty list == valid)."""
    problems: list[str] = []

    if record.get("source") not in KNOWN_SOURCES:
        problems.append("unknown_source")
    if _is_missing(record.get("name_or_title")):
        problems.append("missing_name")

    url = record.get("source_url")
    if _is_missing(url):
        problems.append("missing_url")
    elif not is_valid_url(url):
        problems.append("invalid_url")

    price = record.get("price")
    if not _is_missing(price):
        if not _is_number(price):
            problems.append("invalid_price")
        elif price < 0:
            problems.append("negative_price")

    rating = record.get("rating")
    if not _is_missing(rating):
        is_int = isinstance(rating, int) and not isinstance(rating, bool)
        if not is_int or not MIN_RATING <= rating <= MAX_RATING:
            problems.append("invalid_rating")

    if record.get("source") == QUOTES_SOURCE and _is_missing(record.get("author")):
        problems.append("missing_author")

    return problems


def validate_records(records: Iterable[Record]) -> tuple[list[Record], int, Counter]:
    """Split records into valid ones; count rejections and their reasons.

    Returns ``(valid_records, rejected_count, reason_counter)``. A record with
    several problems counts once as rejected but once per reason in the counter.
    """
    valid: list[Record] = []
    rejected = 0
    reasons: Counter = Counter()
    for record in records:
        problems = validate_record(record)
        if not problems:
            valid.append(record)
            continue
        rejected += 1
        reasons.update(problems)
        logger.warning(
            "Rejected record (%s, %r): %s",
            record.get("source"), record.get("name_or_title"), ", ".join(problems),
        )
    return valid, rejected, reasons
