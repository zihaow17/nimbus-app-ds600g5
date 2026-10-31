
"""Company Search UI, Yahoo Finance orchestration, and rendering of stored results."""

from html import escape
from pathlib import Path

import streamlit as st

from analysis import (
    get_analyst_ratings,
    get_financials,
    get_news,
    get_financial_currency,
    get_price,
)

from features.company_comparison import (
    _company_logo,
    company_info as cached_company_info,
)
from features.company_overview import show_company_overview
from features.favourites import show_favourite_companies
from features.history import record_search
from features.single_stock_dashboard import (
    show_single_stock_dashboard,
)
from features.financial_statements import (
    show_financial_statements,
)


# ============================================================
# SETTINGS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

WIDE_LOGO_PATH = (
    PROJECT_ROOT / "assets" / "nimbus-logo-wide.png"
)

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


@st.cache_data(ttl=900, show_spinner=False)
def cached_company_name(ticker):
    """Return a cached display name for a ticker."""

    info = cached_company_info(ticker) or {}
    return (
        info.get("shortName")
        or info.get("longName")
        or ticker
    )


@st.cache_data(ttl=900, show_spinner=False)
def cached_financial_currency(ticker):
    """Return the cached reporting currency for a ticker."""

    return get_financial_currency(ticker)


@st.cache_data(ttl=900, show_spinner=False)
def cached_news(ticker):
    """Return cached recent news for a ticker."""

    return get_news(ticker)


@st.cache_data(ttl=900, show_spinner=False)
def cached_analyst_ratings(ticker):
    """Return cached analyst ratings for a ticker."""

    return get_analyst_ratings(ticker)


# Keep the company identity card visually consistent with the comparison page.
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


def _company_identity_html(
    ticker,
    info,
    company_name,
):
    """Render company logo and identity."""

    name = escape(
        str(
            company_name
            or info.get("shortName")
            or info.get("longName")
            or ticker
        )
    )

    exchange = escape(
        str(
            info.get("exchange")
            or "Listed company"
        )
    )

    return (
        '<div class="nimbus-company">'
        f'{_company_logo(ticker, info)}'
        '<div>'
        f'<div class="nimbus-company-name">{name}</div>'
        '<div class="nimbus-company-symbol">'
        f'{escape(str(ticker))} · {exchange}'
        '</div>'
        '</div>'
        '</div>'
    )


# ============================================================
# SEARCH INPUT
# ============================================================

def _uppercase_search_ticker():
    """Convert ticker symbols to uppercase."""

    value = st.session_state.get(
        "company_search_ticker",
        "",
    )

    st.session_state["company_search_ticker"] = (
        value.upper()
    )

def _uppercase_search_ticker() -> None:
    """Normalize the ticker field as the user types."""
    ticker = st.session_state.get("company_search_ticker", "")
    st.session_state["company_search_ticker"] = ticker.upper()

def _company_name_for_ticker(ticker):
    """Preserve the existing helper interface."""

    ticker = (ticker or "").strip().upper()

    if not ticker:
        return "Unknown company"

    return cached_company_name(ticker)


# ============================================================
# RUN COMPANY SEARCH
# ============================================================

def _run_single_search(ticker):
    """
    Fetch all result datasets and persist the completed search for this user.
    """

    ticker = (ticker or "").strip().upper()

    if not ticker:
        st.error("Please enter a ticker symbol.")
        return

    st.session_state.pop("company_search_history_id", None)
    st.session_state.pop("company_search_user_id", None)
    try:
        company_name = _company_name_for_ticker(ticker)
    except Exception as error:
        st.warning(
            "Company name could not be loaded. The ticker will be used instead."
        )
        st.caption(f"Details: {error}")
        company_name = ticker

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
    except Exception as error:
        st.error(f"Could not load data for {ticker}. Check the symbol and try again.")
        st.caption(f"Details: {error}")
        return

    st.session_state[RESULTS_KEY] = {
        "ticker": ticker,
        "company_name": company_name,
        **result,
    }
    st.session_state[RESULT_VIEW_KEY] = RESULT_VIEW_OPTIONS[0]
    user_id = st.session_state["current_user_id"]
    try:
        search_id = record_search(
            "single",
            ticker,
            primary_name=company_name,
            user_id=user_id,
            analysis_type="all",
            result={
                **result,
                "ticker": ticker,
                "company_name": company_name,
            },
        )
        st.session_state["current_history_id"] = search_id
        st.session_state["notes_history_editor_open"] = False
        st.session_state["notes_pending_context"] = None
        st.session_state["notes_active_id"] = None
        st.session_state["notes_draft"] = False
    except Exception as error:
        st.error(f"Search results loaded, but history could not be saved for {ticker}.")
        st.caption(f"Details: {error}")
    else:
        st.session_state["company_search_history_id"] = search_id
        st.session_state["company_search_user_id"] = user_id

# ============================================================
# LAZY-LOADED FINANCIAL STATEMENTS
# ============================================================

def _render_financial_statements(
    ticker,
    financials=None,
    error_message=None,
):
    """
    Retrieve financial statements only when selected.

    financial_statements.py already caches full statements.
    """

    if financials is None and error_message:
        st.warning(
            "Previously saved financial data is unavailable. "
            "Nimbus will try to retrieve the latest statements."
        )

    currency = cached_financial_currency(ticker)

    show_financial_statements(
        ticker=ticker,
        financials=financials,
        currency=currency,
    )


# ============================================================
# LAZY-LOADED NEWS
# ============================================================

def render_news(ticker, articles=None, error=None):
    """Display company news."""

    with st.container(border=True):
        st.subheader(f"Recent News for {ticker}")

        if articles is None:
            with st.spinner("Loading recent news..."):
                try:
                    articles = cached_news(ticker)

                except Exception as fetch_error:
                    st.error(
                        "Could not load news from Yahoo Finance."
                    )
                    st.caption(str(fetch_error))
                    return

        if articles is None or articles.empty:
            st.info(
                "No recent news is currently available."
            )

            if error:
                st.caption(str(error))

            return

        st.dataframe(
            articles,
            width="stretch",
            hide_index=True,
        )


# ============================================================
# LAZY-LOADED STOCK DASHBOARD
# ============================================================

def render_stock_dashboard(
    ticker,
    company_name,
    ratings=None,
):
    """
    Render the existing stock dashboard.

    Company Overview remains after the stock chart
    and key statistics, as previously requested.
    """

    with st.spinner("Loading company information..."):
        info = cached_company_info(ticker)

    st.markdown(
        COMPANY_IDENTITY_CSS,
        unsafe_allow_html=True,
    )

    st.markdown(
        _company_identity_html(
            ticker,
            info,
            company_name,
        ),
        unsafe_allow_html=True,
    )

    if ratings is None:
        with st.spinner("Loading analyst ratings..."):
            try:
                ratings = cached_analyst_ratings(ticker)

            except Exception:
                ratings = None

    show_single_stock_dashboard(
        ticker,
        ratings=ratings,
        overview_callback=show_company_overview,
    )


# ============================================================
# RENDER SEARCH RESULTS
# ============================================================

def render_search_result(
    result,
    selector_key=RESULT_VIEW_KEY,
):
    if not result:
        return

    ticker = str(
        result.get("ticker", "")
    ).strip().upper()

    if not ticker:
        st.warning(
            "The saved search does not contain a ticker."
        )
        return

    company_name = result.get(
        "company_name",
        ticker,
    )

    analysis_type = result.get(
        "analysis_type",
        "all",
    )

    lazy = bool(
        result.get("lazy_loading", False)
    )

    # --------------------------------------------------------
    # SUPPORT BOTH NEW AND OLD SAVED SEARCHES
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # HANDLE OLDER SAVED RESULTS
    # --------------------------------------------------------

    if (
        not lazy
        and selected_view not in datasets
    ):
        st.info(
            "This saved search does not contain "
            "that result page. Run a new search "
            "to access all sections."
        )
        return

    # --------------------------------------------------------
    # FINANCIAL STATEMENTS
    # --------------------------------------------------------

    if selected_view == "filings":
        _render_financial_statements(
            ticker,
            datasets.get("filings"),
            errors.get("financials"),
        )

    # --------------------------------------------------------
    # NEWS
    # --------------------------------------------------------

    elif selected_view == "news":
        render_news(
            ticker,
            datasets.get("news"),
            errors.get("news"),
        )

    # --------------------------------------------------------
    # STOCK PRICE AND ANALYST INSIGHTS
    # --------------------------------------------------------

    else:
        stock_data = datasets.get(
            "stock price ratings"
        ) or {}

        render_stock_dashboard(
            ticker=ticker,
            company_name=company_name,
            ratings=stock_data.get("ratings"),
        )

    # --------------------------------------------------------
    # COMPANY OVERVIEW
    # --------------------------------------------------------

    # The stock dashboard already contains Company Overview.
    # Keep it at the bottom for News and Financial Statements.
    if selected_view != "stock price ratings":
        st.divider()
        show_company_overview(ticker)


def _render_search_results():
    result = st.session_state.get(
        RESULTS_KEY
    )

    if result:
        render_search_result(result)


# ============================================================
# NIMBUS SEARCH HOMEPAGE
# ============================================================

def show_company_search_page():
    """Render the existing Nimbus homepage."""

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

    # --------------------------------------------------------
    # LOGO AND HOMEPAGE TITLE
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # COMPANY SEARCH INPUT
    # --------------------------------------------------------

    with st.container(key="company-search-bar"):
        ticker = st.text_input(
            "Company or ticker",
            placeholder="Search company or ticker",
            label_visibility="collapsed",
            help=(
                "Enter a ticker symbol such as "
                "AAPL, MSFT, or NVDA."
            ),
            key="company_search_ticker",
            on_change=_uppercase_search_ticker,
        )

        st.caption(
            "e.g. Apple, AAPL, Microsoft, MSFT"
        )

    # --------------------------------------------------------
    # FAVOURITES
    # --------------------------------------------------------

    selected_favourite = show_favourite_companies()

    # --------------------------------------------------------
    # SEARCH BUTTON
    # --------------------------------------------------------

    with st.form("analysis_form"):
        left, center, right = st.columns([1, 1, 1])

        with center:
            run_analysis = st.form_submit_button(
                "Search"
            )

    # Avoid fetching data twice if both actions occur.
    selected_ticker = None

    if run_analysis:
        selected_ticker = ticker

    elif selected_favourite:
        selected_ticker = selected_favourite

    if selected_ticker:
        _run_single_search(selected_ticker)

    _render_search_results()
