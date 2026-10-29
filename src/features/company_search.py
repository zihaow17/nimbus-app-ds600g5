
"""Company search page and result rendering for Nimbus."""

from html import escape
from pathlib import Path

import streamlit as st
import yfinance as yf

from analysis import (
    get_analyst_ratings,
    get_financials,
    get_news,
    get_price,
    format_financial_statement,
    get_financial_currency,
)
from features.company_comparison import _company_logo, company_info
from features.favourites import show_favourite_companies
from features.history import record_search
from features.company_overview import show_company_overview
from features.single_stock_dashboard import show_single_stock_dashboard


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WIDE_LOGO_PATH = PROJECT_ROOT / "assets" / "nimbus-logo-wide.png"

RESULTS_KEY = "company_search_results"
RESULT_VIEW_KEY = "company_search_result_view"

RESULT_VIEW_OPTIONS = (
    "stock price ratings",
    "filings",
    "news",
)

RESULT_VIEW_LABELS = {
    "stock price ratings": "Stock price and analyst ratings",
    "filings": "Financial statements",
    "news": "Recent news",
}


# ============================================================
# STYLING
# ============================================================

COMPANY_IDENTITY_CSS = """
<style>
.nimbus-company {
    display: flex;
    align-items: center;
    gap: 13px;
    margin-bottom: 15px;
}

.nimbus-company-name {
    font-size: 1.12rem;
    font-weight: 740;
    line-height: 1.35;
}

.nimbus-company-symbol {
    color: #91A5BA;
    font-size: 0.8rem;
}

.nimbus-logo-wrap {
    display: inline-flex;
    width: 48px;
    height: 48px;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.nimbus-logo-wrap img {
    max-width: 44px;
    max-height: 44px;
    object-fit: contain;
}

.nimbus-logo-fallback {
    flex-shrink: 0;
}

.nimbus-mark {
    width: 47px;
    height: 47px;
    border-radius: 14px;
    background: #223C64;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
}

.nimbus-logo {
    width: 47px;
    height: 47px;
    border-radius: 12px;
    object-fit: contain;
    background: #1A293D;
    padding: 7px;
    border: 1px solid #405A79;
}
</style>
"""


# ============================================================
# COMPANY IDENTITY
# ============================================================

def _company_identity_html(ticker, info, company_name):
    name = escape(
        str(
            company_name
            or info.get("shortName")
            or info.get("longName")
            or ticker
        )
    )

    exchange = escape(
        str(info.get("exchange") or "Listed company")
    )

    safe_ticker = escape(str(ticker))

    return (
        '<div class="nimbus-company">'
        f'{_company_logo(ticker, info)}'
        '<div>'
        f'<div class="nimbus-company-name">{name}</div>'
        '<div class="nimbus-company-symbol">'
        f'{safe_ticker} · {exchange}'
        '</div>'
        '</div>'
        '</div>'
    )


def _uppercase_search_ticker():
    ticker = st.session_state.get(
        "company_search_ticker",
        "",
    )
    st.session_state["company_search_ticker"] = ticker.upper()


def _company_name_for_ticker(ticker):
    ticker = (ticker or "").strip().upper()

    if not ticker:
        return "Unknown company"

    try:
        info = yf.Ticker(ticker).info or {}
        return (
            info.get("shortName")
            or info.get("longName")
            or ticker
        )
    except Exception:
        return ticker


# ============================================================
# FETCH SEARCH DATA
# ============================================================

def _run_single_search(ticker):
    ticker = (ticker or "").strip().upper()

    if not ticker:
        st.error("Please enter a ticker symbol.")
        return

    company_name = _company_name_for_ticker(ticker)

    with st.spinner(f"Loading data for {ticker}..."):
        result = {
            "ticker": ticker,
            "company_name": company_name,
            "analysis_type": "all",
            "errors": {},
        }

        functions = [
            ("financials", get_financials),
            ("news", get_news),
            ("price", get_price),
            ("ratings", get_analyst_ratings),
        ]

        for key, fetch_function in functions:
            try:
                result[key] = fetch_function(ticker)
            except Exception as error:
                result[key] = None
                result["errors"][key] = str(error)

    st.session_state[RESULTS_KEY] = result
    st.session_state[RESULT_VIEW_KEY] = RESULT_VIEW_OPTIONS[0]

    try:
        record_search(
            "single",
            ticker,
            primary_name=company_name,
            analysis_type="all",
            result=result,
        )
    except Exception as error:
        st.caption(f"Search history could not be saved: {error}")


# ============================================================
# FINANCIAL STATEMENTS
# ============================================================

def _render_financial_statements(
    ticker,
    financials,
    error_message=None,
):
    if financials is None:
        st.error("Financial statements are unavailable.")
        if error_message:
            st.caption(str(error_message))
        return

    try:
        currency = get_financial_currency(ticker)
    except Exception:
        currency = None

    st.caption(
        f"Reporting currency: {currency or 'Unavailable'} | "
        "B = billions, M = millions, K = thousands. "
        "Values are rounded for display."
    )

    for section, data in financials.items():
        with st.container(border=True):
            st.subheader(section)

            if data is None or data.empty:
                st.info(f"No {section.lower()} data available.")
            else:
                formatted_data = format_financial_statement(
                    data,
                    currency=currency,
                )

                st.dataframe(
                    formatted_data,
                    width="stretch",
                )


# ============================================================
# RECENT NEWS
# ============================================================

def render_news(ticker, articles, error=None):
    with st.container(border=True):
        st.subheader(f"Recent news for {ticker}")

        if articles is None:
            st.info("Recent news is unavailable.")
            if error:
                st.caption(str(error))

        elif articles.empty:
            st.info("No recent news was found.")

        else:
            st.dataframe(
                articles,
                width="stretch",
                hide_index=True,
            )


# ============================================================
# STOCK DASHBOARD
# ============================================================

def render_stock_dashboard(ticker, company_name, ratings):
    try:
        info = company_info(ticker) or {}
    except Exception:
        info = {}

    st.markdown(
        COMPANY_IDENTITY_CSS,
        unsafe_allow_html=True,
    )

    st.markdown(
        _company_identity_html(ticker, info, company_name),
        unsafe_allow_html=True,
    )

    # Company Overview appears below the current price,
    # before the historical stock chart.
    show_single_stock_dashboard(
        ticker,
        ratings=ratings,
        overview_callback=show_company_overview,
    )


# ============================================================
# DISPLAY SEARCH RESULTS
# ============================================================

def render_search_result(result, selector_key=RESULT_VIEW_KEY):
    if not result:
        return

    ticker = result.get("ticker", "")

    if not ticker:
        st.warning("The saved search has no ticker.")
        return

    company_name = result.get("company_name", ticker)
    analysis_type = result.get("analysis_type", "all")

    if "financials" in result:
        datasets = {
            "filings": result.get("financials"),
            "news": result.get("news"),
            "stock price ratings": {
                "price": result.get("price"),
                "ratings": result.get("ratings"),
            },
        }

    elif analysis_type == "filings":
        datasets = {
            "filings": result.get("data"),
        }

    elif analysis_type == "news":
        datasets = {
            "news": result.get("data"),
        }

    else:
        datasets = {
            "stock price ratings": {
                "price": result.get("price"),
                "ratings": result.get("ratings"),
            },
        }

    selected_view = st.selectbox(
        "Result page",
        RESULT_VIEW_OPTIONS,
        format_func=RESULT_VIEW_LABELS.get,
        key=selector_key,
    )

    errors = result.get("errors") or {}

    if selected_view not in datasets:
        st.info(
            "This saved search does not contain that result page. "
            "Please run a new search."
        )

    elif selected_view == "filings":
        _render_financial_statements(
            ticker,
            datasets["filings"],
            errors.get("financials"),
        )

    elif selected_view == "news":
        render_news(
            ticker,
            datasets["news"],
            errors.get("news"),
        )

    else:
        stock_data = datasets["stock price ratings"]

        render_stock_dashboard(
            ticker=ticker,
            company_name=company_name,
            ratings=stock_data.get("ratings"),
        )

    # Avoid showing the overview twice on the stock page.
    if (
        selected_view != "stock price ratings"
        and selected_view in datasets
    ):
        st.divider()
        show_company_overview(ticker)


def _render_search_results():
    result = st.session_state.get(RESULTS_KEY)

    if result:
        render_search_result(result)


# ============================================================
# NIMBUS HOMEPAGE
# ============================================================

def show_company_search_page():
    st.markdown(
        """
        <style>
        .st-key-company-search-bar {
            margin: 0 auto;
            max-width: 620px;
        }

        .nimbus-hero-title {
            text-align: center;
            font-size: clamp(1.4rem, 3vw, 2rem);
            font-weight: 700;
            color: #E9EDF4;
            margin-top: 0.3rem;
        }

        .nimbus-hero-description {
            text-align: center;
            color: #A5B1C0;
            font-size: 0.98rem;
            margin-top: 0.2rem;
            margin-bottom: 2.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # IMPORTANT:
    # Use st.image for the logo and unindented HTML for
    # the title/description. This prevents HTML tags
    # from showing up as a Markdown code block.

    if WIDE_LOGO_PATH.exists():
        left, middle, right = st.columns([1, 4, 1])

        with middle:
            st.image(
                str(WIDE_LOGO_PATH),
                use_container_width=True,
            )

    else:
        st.markdown(
            "<h1 style='text-align:center;'>NIMBUS</h1>",
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="nimbus-hero-title">'
        'Financial Intelligence Dashboard'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="nimbus-hero-description">'
        'Search for a company to explore its financial data'
        '</p>',
        unsafe_allow_html=True,
    )

    with st.container(key="company-search-bar"):
        ticker = st.text_input(
            "Company or ticker",
            placeholder="Search company or ticker",
            label_visibility="collapsed",
            help="Enter a ticker symbol such as AAPL or NVDA.",
            key="company_search_ticker",
            on_change=_uppercase_search_ticker,
        )

        st.caption(
            "e.g. Apple, AAPL, Microsoft, MSFT"
        )

    selected_favourite = show_favourite_companies()

    with st.form("analysis_form"):
        left, center, right = st.columns([1, 1, 1])

        with center:
            run_analysis = st.form_submit_button("Search")

    if selected_favourite:
        _run_single_search(selected_favourite)

    if run_analysis:
        _run_single_search(ticker)

    _render_search_results()
