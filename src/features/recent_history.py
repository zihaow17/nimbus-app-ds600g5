"""Recently viewed history page and read-only result dialog."""

from datetime import datetime, timezone
from html import escape

import pandas as pd
import psycopg
import streamlit as st

from analysis import get_analyst_ratings, get_news, get_price
from features.company_comparison import get_cached_comparison, show_cached_comparison
from features.company_search import RESULT_VIEW_OPTIONS, render_search_result
from features.history import load_history
from features.notes import show_saved_notes


def _show_more_history(total_rows: int) -> None:
    """Reveal the next five history records without exceeding available data."""
    visible_count = st.session_state.get("recent_history_visible_count", 5)
    st.session_state["recent_history_visible_count"] = min(visible_count + 5, total_rows)


def _format_timestamp(timestamp: str) -> str:
    parsed = pd.to_datetime(timestamp, errors="coerce", utc=True)
    if pd.isna(parsed):
        return "Timestamp unavailable"
    return parsed.tz_convert("Asia/Singapore").strftime("%Y-%m-%d %H:%M SGT")


def _load_history_record(record: dict) -> None:
    """Select a history item and attach matching in-session comparison data."""
    st.session_state["history_result_view"] = RESULT_VIEW_OPTIONS[0]
    selected = dict(record)
    if selected.get("search_type") == "Company comparison":
        selected["comparison_cache"] = get_cached_comparison(
            selected.get("primary_ticker", ""),
            selected.get("secondary_ticker", ""),
        )
    st.session_state["history_popup_record"] = selected


def _fetch_legacy_single_result(record: dict) -> tuple[dict, str]:
    """Load a legacy record's default price-and-ratings view on demand."""
    ticker = record["primary_ticker"]
    result = {
        "ticker": ticker,
        "company_name": record.get("primary_name") or ticker,
        "analysis_type": "stock price ratings",
        "price": get_price(ticker),
        "ratings": get_analyst_ratings(ticker),
    }
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return result, retrieved_at


@st.dialog("Search result", width="large", dismissible=False)
def _show_history_result_dialog(record: dict) -> None:
    """Show a saved result without exposing search controls."""
    if record.get("search_type") == "Company comparison":
        primary_name = record.get("primary_name") or record.get("primary_ticker", "")
        secondary_name = record.get("secondary_name") or record.get("secondary_ticker", "")
        st.subheader(f"{primary_name} vs {secondary_name}")
        st.caption(f"{record.get('primary_ticker', '')} vs {record.get('secondary_ticker', '')}")
        show_cached_comparison(record.get("comparison_cache"))
        show_saved_notes(record["search_id"], record["user_id"])
    else:
        ticker = record.get("primary_ticker") or record.get("ticker_value") or ""
        company_name = record.get("primary_name") or record.get("company_name") or ticker
        result = record.get("result")
        if result is not None:
            retrieved_at = _format_timestamp(record.get("timestamp", ""))
        else:
            try:
                with st.spinner(f"Loading saved result for {ticker}..."):
                    result, retrieved_at = _fetch_legacy_single_result(record)
            except Exception as error:
                st.error(f"Could not load data for {ticker}.")
                st.caption(f"Details: {error}")
                result = None
                retrieved_at = "Timestamp unavailable"

        st.subheader(f"{company_name} ({ticker})")
        st.caption(f"Data retrieved: {retrieved_at}")
        if result is not None:
            render_search_result(result, selector_key="history_result_view")
        show_saved_notes(record["search_id"], record["user_id"])

    if st.button("Back", key="history_result_dialog_back"):
        st.session_state["history_popup_record"] = None
        st.rerun(scope="app")


def show_recent_history_page() -> None:
    """Render recent searches and open their results in a modal dialog."""
    st.markdown('<h2 class="content-section-title">Recently Viewed</h2>', unsafe_allow_html=True)
    try:
        history = load_history(st.session_state["current_user_id"])
    except (psycopg.Error, ValueError) as error:
        st.error(f"Could not load recent searches: {error}")
        return
    if history.empty:
        st.info("No recent searches yet.")
        return

    history = history.sort_values("timestamp", ascending=False, kind="mergesort").reset_index(drop=True)
    if "recent_history_visible_count" not in st.session_state:
        st.session_state["recent_history_visible_count"] = 5

    total_rows = len(history)
    visible_count = min(st.session_state["recent_history_visible_count"], total_rows)
    visible_history = history.head(visible_count)

    header_cols = st.columns([1.5, 2.8, 1.6, 1.8, 0.9], vertical_alignment="center")
    headers = ["Type", "Company / Companies", "Ticker(s)", "Timestamp", "View"]
    for column, label in zip(header_cols, headers):
        with column:
            st.markdown(f"<div class='recent-history-header'>{label}</div>", unsafe_allow_html=True)

    st.markdown("<div class='recent-history-row-gap recent-history-row-gap-header'></div>", unsafe_allow_html=True)

    for row_index, (_, row) in enumerate(visible_history.iterrows()):
        columns = st.columns([1.5, 2.8, 1.6, 1.8, 0.9], vertical_alignment="center")
        values = [
            row["search_type"],
            row["company_name"],
            row["ticker_value"],
            _format_timestamp(row["timestamp"]),
        ]
        for column, value in zip(columns[:4], values):
            with column:
                st.markdown(
                    f"<div class='recent-history-cell'>{escape(str(value))}</div>",
                    unsafe_allow_html=True,
                )
        with columns[4]:
            st.button(
                "View",
                key=f"history_view_{row_index}",
                width="stretch",
                on_click=_load_history_record,
                args=(row.to_dict(),),
            )
        st.markdown("<div class='recent-history-row-gap'></div>", unsafe_allow_html=True)

    if total_rows > visible_count:
        st.button(
            "Show more",
            key="recent_history_show_more",
            on_click=_show_more_history,
            args=(total_rows,),
        )

    selected_record = st.session_state.get("history_popup_record")
    if selected_record:
        _show_history_result_dialog(selected_record)
