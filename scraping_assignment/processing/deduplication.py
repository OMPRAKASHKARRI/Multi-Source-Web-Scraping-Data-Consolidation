"""Fingerprint-based duplicate detection.

Records are compared by a SHA-256 hash of *normalised* identifying fields, so
``"Example Book Title"``, ``" Example Book Title "`` and ``"EXAMPLE BOOK TITLE"``
all collapse to the same fingerprint.
"""
from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

from data_model import QUOTES_SOURCE, Record

logger = logging.getLogger(__name__)

QUOTE_PREFIX_LENGTH = 50
KEY_SEPARATOR = "|"
_PUNCTUATION = re.compile(r"[^\w\s]")


def normalize_for_fingerprint(value: Any) -> str:
    """Lowercase, drop punctuation and collapse whitespace."""
    text = unicodedata.normalize("NFKC", "" if value is None else str(value)).lower()
    return " ".join(_PUNCTUATION.sub("", text).split())


def build_identity_key(record: Mapping[str, Any]) -> str:
    """Build the normalised identity string used for duplicate detection.

    * Quotes: source + author + first 50 characters of the (normalised) quote.
    * Everything else (books): source + title.
    """
    source = normalize_for_fingerprint(record.get("source"))
    title = normalize_for_fingerprint(record.get("name_or_title"))
    if record.get("source") == QUOTES_SOURCE:
        author = normalize_for_fingerprint(record.get("author"))
        return KEY_SEPARATOR.join((source, author, title[:QUOTE_PREFIX_LENGTH]))
    return KEY_SEPARATOR.join((source, title))


def fingerprint(record: Mapping[str, Any]) -> str:
    """SHA-256 hex digest of the record's normalised identity key."""
    return hashlib.sha256(build_identity_key(record).encode("utf-8")).hexdigest()


def deduplicate(records: Iterable[Record]) -> tuple[list[Record], list[Record]]:
    """Return ``(unique_records, duplicate_records)``, keeping the first occurrence."""
    seen: set[str] = set()
    unique: list[Record] = []
    duplicates: list[Record] = []
    for record in records:
        digest = fingerprint(record)
        if digest in seen:
            duplicates.append(record)
            logger.info(
                "Duplicate removed (%s): %r", record.get("source"), record.get("name_or_title")
            )
        else:
            seen.add(digest)
            unique.append(record)
    return unique, duplicates
