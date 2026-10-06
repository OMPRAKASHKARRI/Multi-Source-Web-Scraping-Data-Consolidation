"""Write the consolidated CSV and the JSON summary report."""
from __future__ import annotations

import csv
import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from data_model import OUTPUT_COLUMNS, Record

logger = logging.getLogger(__name__)


def _format_for_csv(record: Record) -> Record:
    """Return a copy with the price shown with two decimals (e.g. ``12.50``)."""
    row = dict(record)
    price = row.get("price")
    if isinstance(price, (int, float)) and not isinstance(price, bool):
        row["price"] = f"{price:.2f}"
    return row


def write_dataset_csv(records: Iterable[Record], path: Path) -> int:
    """Write records with a fixed column order; returns the number of rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(_format_for_csv(record))  # None is written as an empty cell
            count += 1
    logger.info("Wrote %d rows to %s", count, path)
    return count


def write_summary_report(report: dict[str, Any], path: Path) -> None:
    """Write the summary report as pretty-printed UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("Wrote summary report to %s", path)
