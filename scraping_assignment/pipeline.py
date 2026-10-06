"""Orchestration: scrape -> clean -> validate -> deduplicate -> consolidate."""
from __future__ import annotations

import logging
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from data_model import Record
from processing.cleaning import clean_record
from processing.deduplication import deduplicate
from processing.validation import validate_records
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

PARSE_ERROR_REASON = "parse_error"
CLEANING_ERROR_REASON = "cleaning_error"


@dataclass
class SourceReport:
    """Per-source counters. ``raw - rejected - duplicates == final``."""

    raw_records: int = 0
    cleaned_records: int = 0
    rejected_records: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    duplicates: int = 0
    final_records: int = 0
    pages_fetched: int = 0
    pages_failed: int = 0
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def reconciles(self) -> bool:
        return self.raw_records - self.rejected_records - self.duplicates == self.final_records


@dataclass
class PipelineResult:
    records: list[Record]
    report: dict[str, Any]


def process_source(scraper: BaseScraper) -> tuple[list[Record], SourceReport]:
    """Run one scraper through the whole pipeline; never raises."""
    name = scraper.source_name
    report = SourceReport()
    try:
        scraped = scraper.scrape()
    except Exception as exc:  # noqa: BLE001 - isolation boundary: one source must not stop the others
        logger.exception("[%s] Scraper crashed", name)
        report.error = f"{type(exc).__name__}: {exc}"
        return [], report

    report.pages_fetched = scraped.pages_fetched
    report.pages_failed = scraped.pages_failed
    report.warnings = list(scraped.warnings)
    reasons: Counter = Counter()
    if scraped.parse_errors:
        reasons[PARSE_ERROR_REASON] += scraped.parse_errors

    cleaned: list[Record] = []
    cleaning_errors = 0
    for raw in scraped.records:
        try:
            cleaned.append(clean_record(raw))
        except (AttributeError, TypeError, ValueError) as exc:
            cleaning_errors += 1
            logger.warning("[%s] Cleaning failed for %r: %s", name, raw, exc)
    if cleaning_errors:
        reasons[CLEANING_ERROR_REASON] += cleaning_errors

    valid, invalid_count, validation_reasons = validate_records(cleaned)
    reasons.update(validation_reasons)
    unique, duplicates = deduplicate(valid)

    report.raw_records = len(scraped.records) + scraped.parse_errors
    report.cleaned_records = len(cleaned)
    report.rejected_records = scraped.parse_errors + cleaning_errors + invalid_count
    report.rejection_reasons = dict(sorted(reasons.items()))
    report.duplicates = len(duplicates)
    report.final_records = len(unique)
    logger.info(
        "[%s] raw=%d cleaned=%d rejected=%d duplicates=%d final=%d",
        name, report.raw_records, report.cleaned_records, report.rejected_records,
        report.duplicates, report.final_records,
    )
    return unique, report


def run_pipeline(scrapers: list[BaseScraper]) -> PipelineResult:
    """Process every source independently and consolidate the results."""
    started_at = datetime.now(timezone.utc)
    timer_start = time.monotonic()

    all_records: list[Record] = []
    source_reports: dict[str, SourceReport] = {}
    for scraper in scrapers:
        records, report = process_source(scraper)
        all_records.extend(records)
        source_reports[scraper.source_name] = report

    finished_at = datetime.now(timezone.utc)
    report_dict = {
        "sources": {name: asdict(rep) for name, rep in source_reports.items()},
        "final_record_count": len(all_records),
        "counts_reconcile": all(rep.reconciles for rep in source_reports.values())
        and len(all_records) == sum(rep.final_records for rep in source_reports.values()),
        "start_time": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_time": finished_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": round(time.monotonic() - timer_start, 2),
    }
    return PipelineResult(records=all_records, report=report_dict)
