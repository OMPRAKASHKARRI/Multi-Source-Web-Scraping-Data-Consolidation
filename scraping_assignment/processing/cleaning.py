"""Reusable cleaning functions.

Every function is pure and tolerant: bad input yields ``None``/an empty string
rather than an exception, so validation (not cleaning) decides what is rejected.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any, Callable, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

from data_model import QUOTES_SOURCE, Record

RATING_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
MISSING_MARKERS = frozenset({"", "n/a", "null", "none", "nan"})
ZERO_WIDTH_CHARS = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"))
OPENING_QUOTES = "\"'\u201c\u2018\u00ab"
CLOSING_QUOTES = "\"'\u201d\u2019\u00bb"
# optional minus, optional currency symbols/garbage ("Â£"), then the number
PRICE_PATTERN = re.compile(r"(-?)\s*[^\d\s-]*\s*(\d[\d,]*(?:\.\d+)?)")
ALLOWED_URL_SCHEMES = ("http", "https")


def clean_text(value: Any) -> str:
    """Trim and collapse all whitespace (tabs, newlines, NBSP, ...) to single spaces."""
    if value is None:
        return ""
    text = str(value).translate(ZERO_WIDTH_CHARS)
    return " ".join(text.split())  # str.split() also splits on \xa0


def empty_to_none(value: Any) -> Optional[str]:
    """Clean text and map empty strings / placeholders such as ``N/A`` to ``None``."""
    text = clean_text(value)
    return None if text.lower() in MISSING_MARKERS else text


def strip_quotes(text: Any) -> str:
    """Remove one pair of wrapping quotation marks (straight or curly)."""
    cleaned = clean_text(text)
    if len(cleaned) >= 2 and cleaned[0] in OPENING_QUOTES and cleaned[-1] in CLOSING_QUOTES:
        return cleaned[1:-1].strip()
    return cleaned


def clean_price(value: Any) -> Optional[float]:
    """Convert ``"£51.77"`` (or ``"Â£1,234.50"``) to a float; ``None`` if unparseable."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2) if math.isfinite(value) else None
    match = PRICE_PATTERN.search(clean_text(value))
    if match is None:
        return None
    sign, number = match.groups()
    return round(float(f"{sign}{number.replace(',', '')}"), 2)


def clean_rating(value: Any) -> Optional[int]:
    """Convert ``"Three"`` (or ``3`` / ``"3"``) to an int; ``None`` if unrecognised.

    Out-of-range digits are returned as-is so validation can report them.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, int):
        return value
    text = clean_text(value).lower()
    if text in RATING_WORDS:
        return RATING_WORDS[text]
    return int(text) if text.isdigit() else None


def clean_tags(value: Any) -> Optional[str]:
    """Trim, lowercase, de-duplicate, sort and join tags with ``;``."""
    if value is None:
        return None
    items = re.split(r"[;,]", value) if isinstance(value, str) else value
    tags = {clean_text(item).lower() for item in items}
    tags.discard("")
    return ";".join(sorted(tags)) or None


def is_valid_url(url: Any) -> bool:
    """True for an absolute http(s) URL with a host and no spaces."""
    if not isinstance(url, str) or not url or any(ch.isspace() for ch in url):
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ALLOWED_URL_SCHEMES and bool(parts.netloc)


def normalize_url(url: Any, base: Optional[str] = None) -> Optional[str]:
    """Return a complete, normalised URL or ``None`` if it is not valid-looking.

    Relative URLs are resolved against ``base``; scheme/host are lowercased and
    fragments are dropped.
    """
    text = clean_text(url)
    if not text:
        return None
    candidate = urljoin(base, text) if base else text
    if not is_valid_url(candidate):
        return None
    parts = urlsplit(candidate)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))


def _clean_or_keep(raw: Any, cleaner: Callable[[Any], Any]) -> Any:
    """Apply ``cleaner``; keep the cleaned *text* if parsing fails.

    Keeping an unparseable value (instead of silently turning it into ``None``)
    lets validation report ``invalid_price`` / ``invalid_rating`` / ``invalid_url``
    rather than mistaking it for a legitimately missing field.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        text: Any = empty_to_none(raw)
        if text is None:
            return None
    else:
        text = raw
    parsed = cleaner(text)
    return parsed if parsed is not None else clean_text(text)


def clean_record(raw: Mapping[str, Any]) -> Record:
    """Turn a raw scraped record into a cleaned record in the common schema."""
    source = clean_text(raw.get("source"))
    name = clean_text(raw.get("name_or_title"))
    if source == QUOTES_SOURCE:
        name = strip_quotes(name)
    return {
        "source": source or None,
        "source_url": _clean_or_keep(raw.get("source_url"), normalize_url),
        "name_or_title": name or None,
        "category": empty_to_none(raw.get("category")),
        "price": _clean_or_keep(raw.get("price"), clean_price),
        "rating": _clean_or_keep(raw.get("rating"), clean_rating),
        "author": empty_to_none(raw.get("author")),
        "tags": clean_tags(raw.get("tags")),
        "description": empty_to_none(raw.get("description")),
        "scraped_at": clean_text(raw.get("scraped_at")) or None,
    }
