"""PostgreSQL persistence for company-search and comparison history."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from io import StringIO
from typing import Optional
from uuid import uuid4

import pandas as pd
from psycopg.types.json import Jsonb

from database import DEMO_USERS, connect, ensure_schema


def _encode_result_value(value):
    """Represent DataFrames as JSON-safe markers before storing results in JSONB."""
    if isinstance(value, pd.DataFrame):
        return {"__dataframe__": value.to_json(orient="split", date_format="iso")}
    if isinstance(value, dict):
        return {key: _encode_result_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode_result_value(item) for item in value]
    return value


def _decode_result_value(value):
    """Restore marked DataFrame payloads when saved search results are loaded."""
    if isinstance(value, dict) and set(value) == {"__dataframe__"}:
        return pd.read_json(StringIO(value["__dataframe__"]), orient="split")
    if isinstance(value, dict):
        return {key: _decode_result_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode_result_value(item) for item in value]
    return value


def _normalize_history_entry(row: dict) -> Optional[dict]:
    """Map one PostgreSQL row into the display shape used by Recently Viewed."""
    search_type = row["search_type"]
    primary_ticker = row["primary_ticker"]
    secondary_ticker = row["secondary_ticker"]
    primary_name = row["primary_name"]
    secondary_name = row["secondary_name"]

    if search_type == "single":
        display_type = "Company search"
        company_name = primary_name or primary_ticker
        ticker_value = primary_ticker
    elif search_type == "comparison":
        display_type = "Company comparison"
        company_name = (
            f"{primary_name or primary_ticker} vs "
            f"{secondary_name or secondary_ticker}"
        )
        ticker_value = f"{primary_ticker} vs {secondary_ticker}".strip(" vs ")
    else:
        return None

    timestamp = row["timestamp_utc"]
    if isinstance(timestamp, datetime):
        timestamp = timestamp.astimezone(timezone.utc).isoformat()

    result = row["result_json"]
    if isinstance(result, str):
        result = json.loads(result)

    return {
        "search_id": str(row["search_id"]),
        "user_id": row["user_id"],
        "timestamp": str(timestamp),
        "search_type": display_type,
        "company_name": company_name,
        "ticker_value": ticker_value,
        "primary_ticker": primary_ticker,
        "secondary_ticker": secondary_ticker,
        "primary_name": primary_name,
        "secondary_name": secondary_name,
        "analysis_type": row["analysis_type"],
        "result": _decode_result_value(result) if result is not None else None,
    }


def record_search(
    search_type: str,
    primary_ticker: str,
    secondary_ticker: Optional[str] = None,
    primary_name: str = "",
    secondary_name: str = "",
    user_id: str = "",
    analysis_type: str = "",
    result=None,
) -> str:
    """Persist one search for a demo user and return its stable search ID."""
    user_id = (user_id or "").strip()
    if user_id not in DEMO_USERS:
        raise ValueError("A valid demo user is required to save search history.")

    primary = (primary_ticker or "").strip().upper()
    secondary = (secondary_ticker or "").strip().upper()
    if not primary:
        raise ValueError("A primary ticker is required to save search history.")
    if search_type not in {"single", "comparison"}:
        raise ValueError("Search type must be 'single' or 'comparison'.")

    search_id = uuid4()
    encoded_result = (
        Jsonb(_encode_result_value(result))
        if result is not None
        else None
    )
    ensure_schema()
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO search_history (
                    search_id, user_id, search_type, primary_ticker,
                    secondary_ticker, primary_name, secondary_name,
                    analysis_type, result_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    search_id,
                    user_id,
                    search_type,
                    primary,
                    secondary,
                    (primary_name or "").strip(),
                    (secondary_name or "").strip(),
                    (analysis_type or "").strip().lower(),
                    encoded_result,
                ),
            )
    return str(search_id)


def load_history(user_id: str) -> pd.DataFrame:
    """Load history belonging only to the selected demo user."""
    if user_id not in DEMO_USERS:
        raise ValueError("A valid demo user is required to load search history.")

    ensure_schema()
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT search_id, user_id, timestamp_utc, search_type,
                       primary_ticker, secondary_ticker, primary_name,
                       secondary_name, analysis_type, result_json
                FROM search_history
                WHERE user_id = %s
                ORDER BY timestamp_utc DESC, search_id DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()

    normalized = [
        entry
        for row in rows
        if (entry := _normalize_history_entry(row)) is not None
    ]
    return pd.DataFrame(normalized, columns=[
        "search_id",
        "user_id",
        "history_id",
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
