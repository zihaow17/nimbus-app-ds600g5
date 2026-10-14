"""Recently viewed history page."""

import pandas as pd
import streamlit as st

from features.history import load_history


def _show_more_history(total_rows: int) -> None:
    """Reveal the next five history records without exceeding available data."""
    visible_count = st.session_state.get("recent_history_visible_count", 5)
    st.session_state["recent_history_visible_count"] = min(visible_count + 5, total_rows)


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

    for _, row in visible_table.iterrows():
        columns = st.columns([1.5, 2.8, 1.6, 1.8, 0.9], vertical_alignment="center")
        values = [row["Type"], row["Company / Companies"], row["Ticker(s)"], row["Timestamp"], ""]
        for column, value in zip(columns, values):
            with column:
                if value == "":
                    st.markdown("<div class='recent-history-button-wrap'><button class='recent-history-reload' disabled>Reload</button></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='recent-history-cell'>{value}</div>", unsafe_allow_html=True)
        st.markdown("<div class='recent-history-row-gap'></div>", unsafe_allow_html=True)

    if total_rows > visible_count:
        st.button(
            "Show more",
            key="recent_history_show_more",
            on_click=_show_more_history,
            args=(total_rows,),
        )