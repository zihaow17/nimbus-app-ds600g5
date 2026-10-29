"""Analyst consensus display for Nimbus's single-company search."""

import pandas as pd
import streamlit as st

RATING_COLUMNS = {
    "strongBuy": "Strong Buy",
    "buy": "Buy",
    "hold": "Hold",
    "sell": "Sell",
    "strongSell": "Strong Sell",
}
PERIOD_LABELS = {
    "0m": "Current",
    "-1m": "1 month ago",
    "-2m": "2 months ago",
    "-3m": "3 months ago",
}
RATING_COLORS = ["#398566", "#87C4A6", "#A3AAB6", "#D39585", "#C85C65"]


def show_analyst_ratings(ratings: pd.DataFrame, ticker: str = "") -> None:
    """Display third-party analyst recommendation counts by available period."""
    if ratings is None or ratings.empty:
        st.info("No analyst recommendations are available for this company.")
        return

    data = ratings.copy()
    if "period" not in data.columns:
        if data.index.name == "period":
            data = data.reset_index()
        else:
            st.dataframe(data, width="stretch")
            st.caption("Analyst recommendation periods are unavailable.")
            return

    missing = [col for col in RATING_COLUMNS if col not in data.columns]
    if missing:
        st.dataframe(data, width="stretch")
        st.caption("The analyst data does not contain all rating categories.")
        return

    data["period"] = data["period"].astype(str).str.strip()
    data = data[data["period"].isin(PERIOD_LABELS)].copy()
    if data.empty:
        st.info("No current or recent monthly recommendation counts are available.")
        return

    available = [p for p in PERIOD_LABELS if p in set(data["period"])]
    state_key = f"analyst_period_{ticker or 'company'}"
    if st.session_state.get(state_key) not in available:
        st.session_state[state_key] = available[0]

    st.markdown("### Analyst Consensus")
    st.radio(
        "Recommendation period",
        options=available,
        format_func=lambda p: PERIOD_LABELS[p],
        horizontal=True,
        key=state_key,
    )
    selected = st.session_state[state_key]
    row = data.loc[data["period"] == selected].iloc[0]

    counts = []
    for col in RATING_COLUMNS:
        value = pd.to_numeric(row[col], errors="coerce")
        counts.append(max(0, int(value)) if pd.notna(value) else 0)

    total = sum(counts)
    if total == 0:
        st.info("No analyst recommendations are recorded for this period.")
    else:
        positive = counts[0] + counts[1]
        neutral = counts[2]
        negative = counts[3] + counts[4]
        st.metric("Positive recommendations", f"{positive / total:.1%}")

        # Five segments, sized according to analyst counts.
        segments = "".join(
            f'<div title="{label}: {count}" style="width:{count / total * 100:.6f}%;'
            f'background:{color};height:100%"></div>'
            for (label, count, color) in zip(
                RATING_COLUMNS.values(), counts, RATING_COLORS
            )
        )
        st.markdown(
            '<div style="display:flex;width:100%;height:13px;overflow:hidden;'
            'border-radius:999px;background:#29323a;margin:8px 0 18px">'
            + segments + '</div>',
            unsafe_allow_html=True,
        )
        a, b, c = st.columns(3)
        a.metric("Positive", positive, help="Strong Buy + Buy")
        b.metric("Neutral", neutral, help="Hold")
        c.metric("Negative", negative, help="Sell + Strong Sell")
        st.caption(f"{total} recorded recommendations · {PERIOD_LABELS[selected]}")

    with st.expander("View detailed analyst ratings"):
        detail = ratings.copy()
        if "period" not in detail.columns and detail.index.name == "period":
            detail = detail.reset_index()
        detail = detail.rename(columns={"period": "Period", **RATING_COLUMNS})
        if "Period" in detail.columns:
            detail["Period"] = detail["Period"].astype(str).map(
                lambda p: PERIOD_LABELS.get(p, p)
            )
        st.dataframe(detail, width="stretch", hide_index=True)

    st.caption(
        "Source: Yahoo Finance analyst recommendations. "
        "These are aggregated third-party opinions, not Nimbus investment advice."
    )
