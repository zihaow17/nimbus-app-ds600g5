"""Recently viewed history page."""

import pandas as pd
import streamlit as st

from features.company_comparison import show_company_comparison
from features.company_search import show_company_search_page
from features.history import load_history


def _show_more_history(total_rows: int) -> None:
    """Reveal the next five history records without exceeding available data."""
    visible_count = st.session_state.get("recent_history_visible_count", 5)
    st.session_state["recent_history_visible_count"] = min(visible_count + 5, total_rows)


def _load_history_record(record: dict) -> None:
    """Open a stored history record in the matching detail view."""
    st.session_state["history_detail_active"] = True
    st.session_state["history_detail_record"] = record


def _go_back_to_recent_history() -> None:
    """Return from a historical detail page to the recent-history list."""
    st.session_state["history_detail_active"] = False
    st.session_state["history_detail_record"] = {}
    st.session_state["history_detail_search_ran"] = False
    st.session_state["nimbus_page"] = "Recently Viewed"
    st.session_state["nimbus_page_mobile"] = "Recently Viewed"


def show_history_detail_page() -> None:
    """Render the saved result in the original page layout with a back link."""
    record = st.session_state.get("history_detail_record") or {}
    if not record:
        st.info("No saved search selected.")
        return

    if st.button("<- Back", key="recent_history_back"):
        _go_back_to_recent_history()
        st.rerun()

    search_type = str(record.get("search_type") or "").lower()
    if "comparison" in search_type:
        primary = record.get("primary_ticker") or ""
        secondary = record.get("secondary_ticker") or ""
        show_company_comparison(primary, secondary)
        return

    primary = record.get("primary_ticker") or record.get("ticker_value") or ""
    show_company_search_page(initial_ticker=primary, auto_search=True)


def show_recent_history_page() -> None:
    """Render recent searches in timestamp order with five-row expansion."""
    st.markdown('<h2 class="content-section-title">Recently Viewed</h2>', unsafe_allow_html=True)
    history = load_history()
    if history.empty:
        st.info("No recent searches yet.")
        return

    history = history.sort_values("timestamp", ascending=False, kind="mergesort").reset_index(drop=True)
    table = history[["search_type", "company_name", "ticker_value", "timestamp"]].copy()
    table.rename(
        columns={
            "search_type": "Type",
            "company_name": "Company / Companies",
            "ticker_value": "Ticker(s)",
            "timestamp": "Timestamp",
        },
        inplace=True,
    )
    table["Timestamp"] = pd.to_datetime(table["Timestamp"], errors="coerce", utc=True).dt.tz_convert("Asia/Singapore").dt.strftime("%Y-%m-%d %H:%M SGT")

    if "recent_history_visible_count" not in st.session_state:
        st.session_state["recent_history_visible_count"] = 5

    total_rows = len(table)
    visible_count = min(st.session_state["recent_history_visible_count"], total_rows)
    visible_table = table.head(visible_count)

    header_cols = st.columns([1.5, 2.8, 1.6, 1.8, 0.9], vertical_alignment="center")
    headers = ["Type", "Company / Companies", "Ticker(s)", "Timestamp", "Reload"]
    for column, label in zip(header_cols, headers):
        with column:
            st.markdown(f"<div class='recent-history-header'>{label}</div>", unsafe_allow_html=True)

    st.markdown("<div class='recent-history-row-gap recent-history-row-gap-header'></div>", unsafe_allow_html=True)

    for row_index, row in visible_table.iterrows():
        columns = st.columns([1.5, 2.8, 1.6, 1.8, 0.9], vertical_alignment="center")
        values = [row["Type"], row["Company / Companies"], row["Ticker(s)"], row["Timestamp"]]
        for column, value in zip(columns[:4], values):
            with column:
                st.markdown(f"<div class='recent-history-cell'>{value}</div>", unsafe_allow_html=True)
        with columns[4]:
            st.button(
                "Reload",
                key=f"history_reload_{row_index}",
                use_container_width=True,
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