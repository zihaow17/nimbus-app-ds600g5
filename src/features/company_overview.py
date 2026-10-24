
"""Expandable company overview for Nimbus."""

from html import escape
from urllib.parse import urlparse

import streamlit as st
import yfinance as yf


@st.cache_data(ttl=3600, show_spinner=False)
def get_company_info(ticker: str) -> dict:
    return yf.Ticker(ticker).info or {}


def show_company_overview(ticker: str) -> None:
    """Display a company overview with a two-column layout."""

    try:
        info = get_company_info(ticker)
    except Exception:
        st.warning("Company overview is temporarily unavailable.")
        return

    if not info:
        st.info("Company information is unavailable.")
        return

    name = info.get("longName") or info.get("shortName") or ticker
    description = info.get("longBusinessSummary") or "No description available."
    employees = info.get("fullTimeEmployees")
    employee_text = (
        f"{employees:,}" if isinstance(employees, int) else "N/A"
    )

    sector = info.get("sector") or "N/A"
    industry = info.get("industry") or "N/A"

    website = info.get("website") or ""
    parsed = urlparse(website)
    safe_website = (
        website if parsed.scheme in ("http", "https") and parsed.netloc
        else ""
    )

    with st.expander(f"{name} Overview", expanded=False):
        left, right = st.columns([2, 1.1], gap="large")

        with left:
            # Limit the description length, like the reference image.
            short_description = (
                description[:450].rsplit(" ", 1)[0] + "..."
                if len(description) > 450
                else description
            )

            st.markdown(
                f"""
                <div style="
                    color:#e1e3e1;
                    font-size:1.05rem;
                    line-height:1.75;
                    margin-bottom:1.5rem;
                ">
                    {escape(short_description)}
                </div>
                """,
                unsafe_allow_html=True,
            )

            if safe_website:
                st.link_button(
                    f"More about {name}",
                    safe_website,
                )

        with right:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(
                    f"### {escape(employee_text)}"
                )
                st.caption("Full-time employees")

                st.write("")
                st.markdown(f"**{escape(sector)}**")
                st.caption("Sector")

            with col2:
                st.markdown("### N/A")
                st.caption("Fiscal year ends")

                st.write("")
                st.markdown(f"**{escape(industry)}**")
                st.caption("Industry")
