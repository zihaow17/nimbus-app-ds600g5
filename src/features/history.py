"""Simple local search-history persistence for the Streamlit app.

This is intentionally limited to local, temporary storage during development. The
project is expected to move to AWS-backed storage later, but this keeps the
current app behavior unchanged while allowing recent searches to be saved locally.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
from typing import Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HISTORY_DIR = PROJECT_ROOT / ".cache" / "nimbus"
HISTORY_PATH = HISTORY_DIR / "search_history.csv"
HISTORY_COLUMNS = [
    "user_id",
    "timestamp_utc",
    "search_type",
    "primary_ticker",
    "secondary_ticker",
    "primary_name",
    "secondary_name",
    "analysis_type",
    "result_json",
]


def _encode_result_value(value):
    if isinstance(value, pd.DataFrame):
        return {"__dataframe__": value.to_json(orient="split", date_format="iso")}
    if isinstance(value, dict):
        return {key: _encode_result_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode_result_value(item) for item in value]
    return value


def _decode_result_value(value):
    if isinstance(value, dict) and set(value) == {"__dataframe__"}:
        return pd.read_json(StringIO(value["__dataframe__"]), orient="split")
    if isinstance(value, dict):
        return {key: _decode_result_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode_result_value(item) for item in value]
    return value


def _serialize_result(result) -> str:
    return json.dumps(_encode_result_value(result), separators=(",", ":")) if result is not None else ""


def _deserialize_result(result_json: str):
    if not result_json:
        return None
    return _decode_result_value(json.loads(result_json))


def _write_history_header() -> None:
    """Write the current schema header to the local history file."""
    with HISTORY_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(HISTORY_COLUMNS)


def _migrate_legacy_history_file() -> None:
    """Upgrade older history CSV schemas while preserving their stored rows."""
    if not HISTORY_PATH.exists():
        _write_history_header()
        return

    with HISTORY_PATH.open("r", newline="", encoding="utf-8") as csv_file:
        rows = list(csv.reader(csv_file))

    if not rows:
        _write_history_header()
        return

    if [column.strip().lower() for column in rows[0]] == HISTORY_COLUMNS:
        return

    old_columns = [column.strip().lower() for column in rows[0]]
    if old_columns and old_columns[0].lower() != "user_id":
        old_columns = ["user_id", *old_columns]

    migrated_rows = []
    for row in rows[1:]:
        if not row:
            continue
        if old_columns[0] == "user_id" and len(row) == len(old_columns) - 1:
            row = ["", *row]
        if len(row) < len(old_columns):
            row.extend([""] * (len(old_columns) - len(row)))
        old_record = dict(zip(old_columns, row))
        migrated_rows.append([old_record.get(column, "") for column in HISTORY_COLUMNS])

    with HISTORY_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(HISTORY_COLUMNS)
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
    analysis_type = (row.get("analysis_type") or "").strip().lower()
    if analysis_type not in {"filings", "news", "stock price ratings"}:
        analysis_type = "stock price ratings"
    result = _deserialize_result((row.get("result_json") or "").strip())

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
            "analysis_type": analysis_type,
            "result": result,
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
            "analysis_type": "comparison",
            "result": result,
        }

    return None


def record_search(
    search_type: str,
    primary_ticker: str,
    secondary_ticker: Optional[str] = None,
    primary_name: str = "",
    secondary_name: str = "",
    user_id: Optional[str] = None,
    analysis_type: str = "",
    result=None,
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
            (analysis_type or "").strip().lower(),
            _serialize_result(result),
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
            "analysis_type",
            "result",
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
        "analysis_type",
        "result",
    ])
    if frame.empty:
        return frame
    frame = frame.sort_values("timestamp", ascending=False, kind="mergesort").reset_index(drop=True)
    return frame
