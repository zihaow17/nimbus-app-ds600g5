"""Company search page and result rendering."""

import base64
from pathlib import Path

import streamlit as st
import yfinance as yf

from analysis import get_analyst_ratings, get_financials, get_news, get_price
from features.favourites import show_favourite_companies
from features.history import record_search

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WIDE_LOGO_PATH = PROJECT_ROOT / "assets" / "nimbus-logo-wide.png"
WIDE_LOGO_DATA = base64.b64encode(WIDE_LOGO_PATH.read_bytes()).decode("ascii")
RESULTS_KEY = "company_search_results"


def _company_name_for_ticker(ticker: str) -> str:
    """Resolve a ticker to a company name, falling back to the ticker."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return "Unknown company"
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return ticker
    return (info.get("shortName") or info.get("longName") or ticker).strip() or ticker


def _run_single_search(ticker: str, analysis_type: str) -> None:
    """Fetch one requested dataset, retain it in session state, and log the search."""
    ticker = ticker.strip().upper()
    if not ticker:
        st.error("Enter a ticker symbol before running an analysis.")
        return

    company_name = _company_name_for_ticker(ticker)
    try:
        with st.spinner(f"Loading {analysis_type} for {ticker}..."):
            if analysis_type == "filings":
                result = {"analysis_type": analysis_type, "data": get_financials(ticker)}
            elif analysis_type == "news":
                result = {"analysis_type": analysis_type, "data": get_news(ticker)}
            else:
                result = {
                    "analysis_type": analysis_type,
                    "price": get_price(ticker),
                    "ratings": get_analyst_ratings(ticker),
                }

        st.session_state[RESULTS_KEY] = {
            "ticker": ticker,
            "company_name": company_name,
            **result,
        }
        record_search(
            "single",
            ticker,
            primary_name=company_name,
            analysis_type=analysis_type,
            result=st.session_state[RESULTS_KEY],
        )
    except Exception as error:
        st.error(f"Could not load data for {ticker}. Check the symbol and try again.")
        st.caption(f"Details: {error}")


def render_search_result(result: dict) -> None:
    """Render a stored company-search result without rendering search controls."""
    if not result:
        return

    ticker = result["ticker"]
    analysis_type = result["analysis_type"]
    if analysis_type == "filings":
        for section, data in result["data"].items():
            st.subheader(section)
            if data.empty:
                st.info(f"No {section.lower()} data was found for {ticker}.")
            else:
                st.dataframe(data, use_container_width=True)
    elif analysis_type == "news":
        st.subheader(f"Recent news for {ticker}")
        articles = result["data"]
        if articles.empty:
            st.info(f"No recent news was found for {ticker}.")
        else:
            st.dataframe(articles, use_container_width=True, hide_index=True)
    else:
        st.subheader(f"Stock price and analyst ratings for {ticker}")
        price = result["price"]
        if price is None:
            st.metric("Current price", "Not available")
        else:
            st.metric("Current price", f"${price:,.2f}")
        ratings = result["ratings"]
        if ratings.empty:
            st.info(f"No analyst recommendations were found for {ticker}.")
        else:
            st.dataframe(ratings, use_container_width=True)


def _render_search_results() -> None:
    """Render the most recent successful search stored in session state."""
    result = st.session_state.get(RESULTS_KEY)
    if result:
        render_search_result(result)


def show_company_search_page() -> None:
    """Render the company search form and any retained search results."""
    st.markdown(
        """
        <style>
        .st-key-company-search-bar {
            margin: 0 auto;
            max-width: 620px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <section class="hero">
            <img class="hero-name" src="data:image/png;base64,{WIDE_LOGO_DATA}" alt="Nimbus" />
            <div class="hero-title">Financial Intelligence Dashboard</div>
            <p class="hero-description">Search for a company to explore its financial data</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="company-search-bar"):
        ticker = st.text_input(
            "Company or ticker",
            placeholder="🔍  Search company or ticker",
            label_visibility="collapsed",
            help="Enter a ticker symbol, for example AAPL or MSFT.",
            key="company_search_ticker",
        )
        st.caption("e.g. Apple, AAPL, Microsoft, MSFT")

    selected_favourite = show_favourite_companies()

    with st.form("analysis_form"):
        analysis_type = st.selectbox(
            "Data to explore",
            ("filings", "news", "stock price ratings"),
            label_visibility="collapsed",
            format_func=lambda value: {
                "filings": "Financial statements",
                "news": "Recent news",
                "stock price ratings": "Stock price and analyst ratings",
            }[value],
        )
        button_left, button_center, button_right = st.columns([1, 1, 1])
        with button_center:
            run_analysis = st.form_submit_button("Search")

    if selected_favourite:
        _run_single_search(selected_favourite, "stock price ratings")

    if run_analysis:
        _run_single_search(ticker, analysis_type)

    _render_search_results()
