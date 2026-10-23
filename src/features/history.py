"""Simple local search-history persistence for the Streamlit app.

This is intentionally limited to local, temporary storage during development. The
project is expected to move to AWS-backed storage later, but this keeps the
current app behavior unchanged while allowing recent searches to be saved locally.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HISTORY_DIR = PROJECT_ROOT / ".cache" / "nimbus"
HISTORY_PATH = HISTORY_DIR / "search_history.csv"


def _write_history_header() -> None:
    """Write the current schema header to the local history file."""
    with HISTORY_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow([
            "user_id",
            "timestamp_utc",
            "search_type",
            "primary_ticker",
            "secondary_ticker",
            "primary_name",
            "secondary_name",
        ])


def _migrate_legacy_history_file() -> None:
    """Upgrade older CSV files that do not yet include a user_id column."""
    if not HISTORY_PATH.exists():
        _write_history_header()
        return

    with HISTORY_PATH.open("r", newline="", encoding="utf-8") as csv_file:
        rows = list(csv.reader(csv_file))

    if not rows:
        _write_history_header()
        return

    if rows[0] and rows[0][0].strip().lower() == "user_id":
        return

    migrated_rows: list[list[str]] = []
    for row in rows[1:]:
        if not row:
            continue
        normalized = ["", *row[:6]]
        while len(normalized) < 7:
            normalized.append("")
        migrated_rows.append(normalized[:7])

    with HISTORY_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow([
            "user_id",
            "timestamp_utc",
            "search_type",
            "primary_ticker",
            "secondary_ticker",
            "primary_name",
            "secondary_name",
        ])
        writer.writerows(migrated_rows)


def _ensure_history_file() -> Path:
    """Create the local history directory and CSV header when needed."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORY_PATH.exists():
        _write_history_header()
    else:
        _migrate_legacy_history_file()
    return HISTORY_PATH


def _normalize_history_entry(row: dict[str, str]) -> Optional[dict[str, str]]:
    """Convert a stored CSV row into a display-ready search record."""
    user_id = (row.get("user_id") or "").strip()
    search_type = (row.get("search_type") or "").strip().lower()
    primary_ticker = (row.get("primary_ticker") or "").strip().upper()
    secondary_ticker = (row.get("secondary_ticker") or "").strip().upper()
    primary_name = (row.get("primary_name") or "").strip()
    secondary_name = (row.get("secondary_name") or "").strip()
    timestamp = (row.get("timestamp_utc") or "").strip()

    if search_type == "single":
        if not primary_ticker:
            return None
        return {
            "user_id": user_id,
            "timestamp": timestamp,
            "search_type": "Company search",
            "company_name": primary_name or primary_ticker,
            "ticker_value": primary_ticker,
            "primary_ticker": primary_ticker,
            "secondary_ticker": "",
            "primary_name": primary_name,
            "secondary_name": "",
        }

    if search_type == "comparison":
        if not primary_ticker and not secondary_ticker:
            return None
        name_one = primary_name or primary_ticker or "Unknown company"
        name_two = secondary_name or secondary_ticker or "Unknown company"
        return {
            "user_id": user_id,
            "timestamp": timestamp,
            "search_type": "Company comparison",
            "company_name": f"{name_one} vs {name_two}",
            "ticker_value": f"{primary_ticker} vs {secondary_ticker}".strip(" vs "),
            "primary_ticker": primary_ticker,
            "secondary_ticker": secondary_ticker,
            "primary_name": primary_name,
            "secondary_name": secondary_name,
        }

    return None


def record_search(
    search_type: str,
    primary_ticker: str,
    secondary_ticker: Optional[str] = None,
    primary_name: str = "",
    secondary_name: str = "",
    user_id: Optional[str] = None,
) -> Path:
    """Append a single search to the local CSV history file."""
    primary = (primary_ticker or "").strip().upper()
    secondary = (secondary_ticker or "").strip().upper()

    if not primary and not secondary:
        return HISTORY_PATH

    normalized_type = "single" if search_type == "single" else "comparison"
    file_path = _ensure_history_file()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with file_path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow([
            (user_id or "").strip(),
            timestamp,
            normalized_type,
            primary,
            secondary,
            (primary_name or "").strip(),
            (secondary_name or "").strip(),
        ])

    return file_path


def load_history(user_id: Optional[str] = None) -> pd.DataFrame:
    """Read locally saved searches and return a DataFrame for the UI."""
    file_path = _ensure_history_file()
    rows: list[dict[str, str]] = []

    if not file_path.exists():
        return pd.DataFrame(columns=[
            "user_id",
            "timestamp",
            "search_type",
            "company_name",
            "ticker_value",
            "primary_ticker",
            "secondary_ticker",
            "primary_name",
            "secondary_name",
        ])

    with file_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            if not row:
                continue
            if user_id is not None:
                stored_user_id = (row.get("user_id") or "").strip()
                if stored_user_id and stored_user_id != user_id:
                    continue
                if not stored_user_id and row.get("timestamp_utc"):
                    continue
            normalized = _normalize_history_entry(row)
            if normalized is not None:
                rows.append(normalized)

    frame = pd.DataFrame(rows, columns=[
        "user_id",
        "timestamp",
        "search_type",
        "company_name",
        "ticker_value",
        "primary_ticker",
        "secondary_ticker",
        "primary_name",
        "secondary_name",
    ])
    if frame.empty:
        return frame
    frame = frame.sort_values("timestamp", ascending=False, kind="mergesort").reset_index(drop=True)
    return frame
