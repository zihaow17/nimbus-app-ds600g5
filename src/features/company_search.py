
"""Company search page and result rendering."""

import base64
from html import escape
from pathlib import Path

import streamlit as st
import yfinance as yf

from analysis import get_analyst_ratings, get_financials, get_news, get_price
from features.company_comparison import _company_logo, company_info
from features.favourites import show_favourite_companies
from features.history import record_search
from features.company_overview import show_company_overview

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WIDE_LOGO_PATH = PROJECT_ROOT / "assets" / "nimbus-logo-wide.png"
WIDE_LOGO_DATA = base64.b64encode(WIDE_LOGO_PATH.read_bytes()).decode("ascii")
RESULTS_KEY = "company_search_results"
RESULT_VIEW_KEY = "company_search_result_view"
RESULT_VIEW_OPTIONS = ("stock price ratings", "filings", "news")
RESULT_VIEW_LABELS = {
    "filings": "Financial statements",
    "news": "Recent news",
    "stock price ratings": "Stock price and analyst ratings",
}
COMPANY_IDENTITY_CSS = """
<style>
.nimbus-logo-wrap {display:inline-flex;width:48px;height:48px;align-items:center;justify-content:center;flex-shrink:0;}
.nimbus-logo-wrap img {max-width:44px;max-height:44px;object-fit:contain;}
.nimbus-logo-fallback {flex-shrink:0;}
.nimbus-company {display:flex;gap:13px;align-items:center;margin-bottom:10px;}
.nimbus-mark {width:47px;height:47px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:1.05rem;background:linear-gradient(135deg,#223c64,#225da3);border:1px solid #405a79;}
.nimbus-logo {width:47px;height:47px;border-radius:12px;object-fit:contain;background:#1a293d;padding:7px;border:1px solid #405a79;}
.nimbus-name {font-size:1.08rem;font-weight:740;line-height:1.35;}
.nimbus-symbol {font-size:.77rem;color:#91a5ba;}
</style>
"""


def _company_identity_html(ticker: str, info: dict, company_name: str) -> str:
    """Render the comparison-style company logo and identity block."""
    name = escape(company_name or info.get("shortName") or info.get("longName") or ticker)
    exchange = escape(str(info.get("exchange") or "Listed company"))
    safe_ticker = escape(ticker)
    return (
        f'<div class="nimbus-company">{_company_logo(ticker, info)}'
        f'<div><div class="nimbus-name">{name}</div>'
        f'<div class="nimbus-symbol">{safe_ticker} · {exchange}</div></div></div>'
    )


def _uppercase_search_ticker() -> None:
    ticker = st.session_state.get("company_search_ticker", "")
    st.session_state["company_search_ticker"] = ticker.upper()


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


def _run_single_search(ticker: str) -> None:
    """Fetch all company datasets, retain them in session state, and log the search."""
    ticker = ticker.strip().upper()
    if not ticker:
        st.error("Enter a ticker symbol before running an analysis.")
        return

    company_name = _company_name_for_ticker(ticker)
    try:
        with st.spinner(f"Loading financial statements, recent news, and stock data for {ticker}..."):
            result = {"analysis_type": "all", "errors": {}}
            for key, fetch in (
                ("financials", get_financials),
                ("news", get_news),
                ("price", get_price),
                ("ratings", get_analyst_ratings),
            ):
                try:
                    result[key] = fetch(ticker)
                except Exception as error:
                    result[key] = None
                    result["errors"][key] = str(error)

        st.session_state[RESULTS_KEY] = {
            "ticker": ticker,
            "company_name": company_name,
            **result,
        }
        st.session_state[RESULT_VIEW_KEY] = RESULT_VIEW_OPTIONS[0]
        record_search(
            "single",
            ticker,
            primary_name=company_name,
            analysis_type="all",
            result=st.session_state[RESULTS_KEY],
        )
    except Exception as error:
        st.error(f"Could not load data for {ticker}. Check the symbol and try again.")
        st.caption(f"Details: {error}")


def render_search_result(result: dict, selector_key: str = RESULT_VIEW_KEY) -> None:
    """Render a stored company-search result without rendering search controls."""

    if not result:
        return

    ticker = result["ticker"]
    analysis_type = result["analysis_type"]
    if "financials" in result:
        datasets = {
            "filings": result["financials"],
            "news": result.get("news"),
            "stock price ratings": {
                "price": result.get("price"),
                "ratings": result.get("ratings"),
            },
        }
    elif analysis_type == "filings":
        datasets = {"filings": result["data"]}
    elif analysis_type == "news":
        datasets = {"news": result["data"]}
    else:
        datasets = {
            "stock price ratings": {
                "price": result["price"],
                "ratings": result["ratings"],
            }
        }

    selected_view = st.selectbox(
        "Result page",
        RESULT_VIEW_OPTIONS,
        format_func=RESULT_VIEW_LABELS.get,
        key=selector_key,
    )
    if selected_view not in datasets:
        available_view = next(iter(datasets))
        st.info(
            "This saved search contains only "
            f"{RESULT_VIEW_LABELS[available_view].lower()}; run a new search to view all three result pages."
        )
    elif selected_view == "filings":
        if datasets["filings"] is None:
            st.error(f"Could not load financial statements: {result['errors']['financials']}")
        else:
            for section, data in datasets["filings"].items():
                with st.container(border=True):
                    st.subheader(section)
                    if data.empty:
                        st.info(f"No {section.lower()} data was found for {ticker}.")
                    else:
                        st.dataframe(data, width="stretch")
    elif selected_view == "news":
        with st.container(border=True):
            st.subheader(f"Recent news for {ticker}")
            articles = datasets["news"]
            if articles is None:
                st.error(f"Could not load recent news: {result['errors']['news']}")
            elif articles.empty:
                st.info(f"No recent news was found for {ticker}.")
            else:
                st.dataframe(articles, width="stretch", hide_index=True)
    else:
        with st.container(border=True):
            try:
                info = company_info(ticker)
            except Exception as error:
                info = {}
                st.caption(
                    f"Company details are unavailable ({error}); showing the ticker fallback."
                )
            st.markdown(COMPANY_IDENTITY_CSS, unsafe_allow_html=True)
            st.markdown(
                _company_identity_html(ticker, info, result.get("company_name", ticker)),
                unsafe_allow_html=True,
            )
            st.subheader(f"Stock price and analyst ratings for {ticker}")
            stock_data = datasets["stock price ratings"]
            price = stock_data["price"]
            if price is None and "price" in result.get("errors", {}):
                st.error(f"Could not load the current price: {result['errors']['price']}")
            elif price is None:
                st.metric("Current price", "Not available")
            else:
                st.metric("Current price", f"${price:,.2f}")

            ratings = stock_data["ratings"]
            if ratings is None and "ratings" in result.get("errors", {}):
                st.error(f"Could not load analyst recommendations: {result['errors']['ratings']}")
            elif ratings is None or ratings.empty:
                st.info(f"No analyst recommendations were found for {ticker}.")
            else:
                st.dataframe(ratings, width="stretch")

    st.divider()
    show_company_overview(ticker)


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
            on_change=_uppercase_search_ticker,
        )
        st.caption("e.g. Apple, AAPL, Microsoft, MSFT")

    selected_favourite = show_favourite_companies()

    with st.form("analysis_form"):
        button_left, button_center, button_right = st.columns([1, 1, 1])
        with button_center:
            run_analysis = st.form_submit_button("Search")

    if selected_favourite:
        _run_single_search(selected_favourite)

    if run_analysis:
        _run_single_search(ticker)

    _render_search_results()
