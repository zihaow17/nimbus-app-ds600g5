
"""Nimbus Company Comparison.

Compare two companies with Yahoo Finance information, price charts,
financial metrics, and compatibility with Recent History.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlparse
import base64
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

from features.history import record_search


# ============================================================
# SETTINGS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGO_DIR = PROJECT_ROOT / "assets" / "company_logos"

PERIOD_LABELS = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
    "5Y": "5y",
    "ALL": "max",
}

HISTORY_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

LOGO_URLS = {
    "AAPL": "https://cdn.simpleicons.org/apple/FFFFFF",
    "MSFT": "https://cdn.simpleicons.org/microsoft/5EBAA7",
    "GOOGL": "https://cdn.simpleicons.org/google/4285F4",
    "GOOG": "https://cdn.simpleicons.org/google/4285F4",
    "AMZN": "https://cdn.simpleicons.org/amazon/FF9900",
    "NVDA": "https://cdn.simpleicons.org/nvidia/76B900",
    "TSLA": "https://cdn.simpleicons.org/tesla/E82127",
    "META": "https://cdn.simpleicons.org/meta/0866FF",
}


# ============================================================
# STYLING
# ============================================================

CSS = """
<style>
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

.nimbus-kicker,
.nimbus-title,
.nimbus-muted,
.nimbus-section {
    font-family: Consolas, monospace;
}

.nimbus-title {
    font-size: 2.65rem;
    font-weight: 800;
    letter-spacing: -.045em;
    line-height: 1.15;
    margin: .4rem 0;
}

.nimbus-title span {
    background: linear-gradient(95deg, #45b8ff, #8576ff);
    color: transparent;
    background-clip: text;
    -webkit-background-clip: text;
}

.nimbus-muted {
    color: #9daec3;
    font-size: .92rem;
    margin: 0 0 1.2rem;
}

.nimbus-kicker {
    font-size: .75rem;
    color: #7a9ccc;
    letter-spacing: .16em;
    font-weight: 700;
}

.nimbus-company {
    display: flex;
    gap: 13px;
    align-items: center;
    margin-bottom: 10px;
}

.nimbus-mark {
    width: 47px;
    height: 47px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    color: #fff;
    font-size: 1.05rem;
    background: linear-gradient(135deg, #223c64, #225da3);
    border: 1px solid #405a79;
}

.nimbus-logo {
    width: 47px;
    height: 47px;
    border-radius: 12px;
    object-fit: contain;
    background: #1a293d;
    padding: 7px;
    border: 1px solid #405a79;
}

.nimbus-name {
    font-size: 1.08rem;
    font-weight: 740;
    line-height: 1.35;
}

.nimbus-symbol {
    font-size: .77rem;
    color: #91a5ba;
}

.nimbus-section {
    font-size: 1.15rem;
    font-weight: 750;
    margin: .45rem 0 1rem;
}

.nimbus-note {
    font-size: .76rem;
    color: #91a1b3;
}

[data-testid="stVerticalBlockBorderWrapper"] > div {
    border-color: #29394d !important;
}

.stApp {
    background: #0b121d;
}

div[data-testid="stMetric"] {
    background: #111e30;
    border: 1px solid #25374e;
    border-radius: 12px;
    padding: 12px 14px;
}

div[data-testid="stMetricLabel"] {
    color: #a7b8cc;
}

div[data-testid="stMetricValue"] {
    font-size: 1.48rem;
}

.stButton button[kind="primary"],
button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(105deg, #1260e8, #634cf0);
    border: 0;
    color: white;
}
</style>
"""


# ============================================================
# NUMBER FORMATTING
# ============================================================

def _valid_number(value):
    try:
        return (
            not isinstance(value, bool)
            and value is not None
            and math.isfinite(float(value))
        )
    except (TypeError, ValueError):
        return False


def _number(value, decimals=2, prefix="", suffix=""):
    if not _valid_number(value):
        return "N/A"

    return f"{prefix}{float(value):,.{decimals}f}{suffix}"


def _big(value, currency="USD"):
    if not _valid_number(value):
        return "N/A"

    value = float(value)
    sign = "-" if value < 0 else ""
    value = abs(value)

    for factor, suffix in (
        (1e12, "T"),
        (1e9, "B"),
        (1e6, "M"),
        (1e3, "K"),
    ):
        if value >= factor:
            return (
                f"{sign}{value / factor:,.2f}{suffix} "
                f"{currency}"
            )

    return f"{sign}{value:,.2f} {currency}"


def _percent(value):
    if not _valid_number(value):
        return "N/A"

    return _number(
        float(value) * 100,
        suffix="%",
    )


def _dividend_yield(info):
    value = info.get("dividendYield")

    if _valid_number(value):
        return _number(value, suffix="%")

    return _percent(
        info.get("trailingAnnualDividendYield")
    )


# ============================================================
# YAHOO FINANCE — CACHED REQUESTS
# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def company_info(ticker):
    """Retrieve and cache company information for 15 minutes."""

    ticker = ticker.strip().upper()

    info = yf.Ticker(ticker).info or {}

    if not info or not (
        info.get("symbol")
        or info.get("shortName")
        or info.get("longName")
    ):
        raise ValueError(
            f"No Yahoo Finance information found for {ticker}."
        )

    return info


@st.cache_data(ttl=900, show_spinner=False)
def company_history(ticker, period):
    """Retrieve and cache OHLCV history for 15 minutes."""

    ticker = ticker.strip().upper()

    result = yf.Ticker(ticker).history(
        period=period,
        auto_adjust=False,
    )

    if not isinstance(result, pd.DataFrame):
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    if any(
        column not in result.columns
        for column in HISTORY_COLUMNS
    ):
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    return result[HISTORY_COLUMNS].dropna(
        subset=["Close"]
    )


def _load_company_pair(ticker1, ticker2):
    """Fetch two companies concurrently."""

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(company_info, ticker1)
        second = executor.submit(company_info, ticker2)

        info1 = first.result()
        info2 = second.result()

    return info1, info2


def _load_history_pair(ticker1, ticker2, period):
    """Fetch the two price histories concurrently."""

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            company_history,
            ticker1,
            period,
        )
        second = executor.submit(
            company_history,
            ticker2,
            period,
        )

        history1 = first.result()
        history2 = second.result()

    return {
        ticker1: history1,
        ticker2: history2,
    }


# ============================================================
# COMPANY LOGOS
# ============================================================

def _company_logo(ticker, info=None):
    """Return the company logo or an initials fallback."""

    ticker = str(ticker).strip().upper()
    safe_ticker = escape(ticker)

    fallback = (
        '<span class="nimbus-mark nimbus-logo-fallback">'
        f'{escape(ticker[:2])}'
        '</span>'
    )

    local_path = LOGO_DIR / f"{ticker}.png"

    if local_path.is_file():
        encoded = base64.b64encode(
            local_path.read_bytes()
        ).decode("ascii")

        url = f"data:image/png;base64,{encoded}"

    elif ticker in LOGO_URLS:
        url = LOGO_URLS[ticker]

    else:
        website = str(
            (info or {}).get("website") or ""
        ).strip()

        if not website:
            return fallback

        if "://" not in website:
            website = "https://" + website

        hostname = urlparse(website).hostname

        if not hostname or "." not in hostname:
            return fallback

        url = (
            "https://www.google.com/s2/favicons?domain="
            + quote(hostname, safe="")
            + "&sz=128"
        )

    return (
        '<span class="nimbus-logo-wrap">'
        f'<img class="nimbus-logo" '
        f'src="{escape(url, quote=True)}" '
        f'alt="{safe_ticker} logo" '
        'onerror="this.style.display=\'none\';'
        'this.nextElementSibling.style.display=\'flex\'">'
        '<span class="nimbus-mark nimbus-logo-fallback" '
        'style="display:none">'
        f'{escape(ticker[:2])}'
        '</span>'
        '</span>'
    )


# ============================================================
# STOCK CHART
# ============================================================

def _stock_chart(history, currency="USD"):
    """Display the stock chart with volume and OHLCV details."""

    if history is None or history.empty:
        st.info("Historical prices are unavailable.")
        return

    history = history.copy()

    for column in HISTORY_COLUMNS:
        history[column] = pd.to_numeric(
            history[column],
            errors="coerce",
        )

    history = history.dropna(subset=["Close"])

    if history.empty:
        st.info("No valid stock prices are available.")
        return

    dates = history.index
    close = history["Close"]

    fig = make_subplots(
        specs=[[{"secondary_y": True}]]
    )

    fig.add_trace(
        go.Bar(
            x=dates,
            y=history["Volume"],
            name="Volume",
            marker_color="rgba(145,163,180,0.45)",
            hoverinfo="skip",
            showlegend=False,
        ),
        secondary_y=True,
    )

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=close,
            name="Close",
            mode="lines",
            line={
                "color": "#15bf91",
                "width": 2.5,
            },
            fill="tozeroy",
            fillcolor="rgba(21,191,145,0.14)",
            customdata=history[
                ["Open", "High", "Low", "Volume"]
            ].to_numpy(),
            hovertemplate=(
                "<b>%{x|%d %b %Y}</b><br>"
                f"Close: {currency} %{{y:,.2f}}<br>"
                f"Open: {currency} %{{customdata[0]:,.2f}}<br>"
                f"High: {currency} %{{customdata[1]:,.2f}}<br>"
                f"Low: {currency} %{{customdata[2]:,.2f}}<br>"
                "Volume: %{customdata[3]:,.0f}"
                "<extra></extra>"
            ),
            showlegend=False,
        ),
        secondary_y=False,
    )

    low = float(close.min())
    high = float(close.max())

    spread = max(
        high - low,
        abs(high) * 0.015,
        0.01,
    )

    fig.update_yaxes(
        range=[
            low - spread * 0.24,
            high + spread * 0.17,
        ],
        tickformat=",.2f",
        showgrid=True,
        gridcolor="rgba(153,174,197,0.16)",
        zeroline=False,
        side="right",
        secondary_y=False,
    )

    max_volume = history["Volume"].max()

    fig.update_yaxes(
        range=[
            0,
            max(
                float(max_volume) * 3.9
                if _valid_number(max_volume)
                else 1,
                1,
            ),
        ],
        visible=False,
        showgrid=False,
        secondary_y=True,
    )

    fig.update_xaxes(
        showgrid=False,
        rangeslider_visible=False,
        tickfont={"color": "#99a9bd"},
    )

    fig.update_layout(
        height=285,
        margin={
            "l": 8,
            "r": 20,
            "t": 16,
            "b": 12,
        },
        plot_bgcolor="#101923",
        paper_bgcolor="#101923",
        font={
            "color": "#dce5ef",
            "size": 12,
        },
        hovermode="x",
        hoverlabel={
            "bgcolor": "#17232e",
            "font_color": "#f0f4f8",
        },
        bargap=0.18,
        dragmode="pan",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displaylogo": False,
            "scrollZoom": False,
        },
    )


# ============================================================
# INDIVIDUAL COMPANY PROFILE
# ============================================================

def _profile(
    ticker,
    info,
    period,
    cached_history=None,
    history_cache_only=False,
):
    """
    Render a company profile.

    Supports cached_history for Recent History compatibility.
    """

    name = escape(
        str(
            info.get("shortName")
            or info.get("longName")
            or ticker
        )
    )

    currency = str(
        info.get("currency") or "USD"
    )

    exchange = escape(
        str(
            info.get("exchange")
            or "Listed company"
        )
    )

    with st.container(border=True):
        st.markdown(
            (
                '<div class="nimbus-company">'
                f'{_company_logo(ticker, info)}'
                '<div>'
                f'<div class="nimbus-name">{name}</div>'
                '<div class="nimbus-symbol">'
                f'{escape(ticker)} · {exchange}'
                '</div>'
                '</div>'
                '</div>'
            ),
            unsafe_allow_html=True,
        )

        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
        )

        previous = (
            info.get("previousClose")
            or info.get("regularMarketPreviousClose")
        )

        if (
            _valid_number(price)
            and _valid_number(previous)
            and float(previous) != 0
        ):
            change = (
                float(price) / float(previous) - 1
            ) * 100
        else:
            change = None

        st.metric(
            "Reported stock price",
            _number(
                price,
                prefix=f"{currency} ",
            ),
            (
                _number(
                    change,
                    suffix="%",
                )
                if change is not None
                else None
            ),
        )

        if cached_history is not None:
            history = cached_history

        elif history_cache_only:
            history = pd.DataFrame(
                columns=HISTORY_COLUMNS
            )

        else:
            history = company_history(
                ticker,
                period,
            )

        if history is None or history.empty:
            st.info(
                "Historical prices unavailable for this ticker."
            )
        else:
            _stock_chart(
                history,
                currency,
            )

        left, right = st.columns(2)

        with left:
            st.metric(
                "Market cap",
                _big(
                    info.get("marketCap"),
                    currency,
                ),
            )

            st.metric(
                "Revenue",
                _big(
                    info.get("totalRevenue"),
                    currency,
                ),
            )

        with right:
            st.metric(
                "P/E ratio",
                _number(
                    info.get("trailingPE")
                ),
            )

            st.metric(
                "EPS (TTM)",
                _number(
                    info.get("trailingEps"),
                    prefix=f"{currency} ",
                ),
            )


# ============================================================
# FINANCIAL METRICS COMPARISON
# ============================================================

def _comparison(t1, i1, t2, i2):
    """Display the two-company financial comparison table."""

    c1 = str(
        i1.get("currency") or "USD"
    )

    c2 = str(
        i2.get("currency") or "USD"
    )

    rows = [
        (
            "Stock price",
            "currentPrice",
            lambda value, currency: _number(
                value,
                prefix=f"{currency} ",
            ),
        ),
        (
            "Market capitalization",
            "marketCap",
            _big,
        ),
        (
            "P/E ratio",
            "trailingPE",
            lambda value, currency: _number(value),
        ),
        (
            "Revenue",
            "totalRevenue",
            _big,
        ),
        (
            "Net income",
            "netIncomeToCommon",
            _big,
        ),
        (
            "EPS (TTM)",
            "trailingEps",
            lambda value, currency: _number(
                value,
                prefix=f"{currency} ",
            ),
        ),
        (
            "Gross margin",
            "grossMargins",
            lambda value, currency: _percent(value),
        ),
        (
            "Operating margin",
            "operatingMargins",
            lambda value, currency: _percent(value),
        ),
        (
            "Profit margin",
            "profitMargins",
            lambda value, currency: _percent(value),
        ),
        (
            "Return on equity",
            "returnOnEquity",
            lambda value, currency: _percent(value),
        ),
    ]

    result = []

    for label, key, formatter in rows:
        result.append(
            {
                "Metric": label,
                t1: formatter(i1.get(key), c1),
                t2: formatter(i2.get(key), c2),
            }
        )

    result.append(
        {
            "Metric": "Dividend yield",
            t1: _dividend_yield(i1),
            t2: _dividend_yield(i2),
        }
    )

    st.dataframe(
        pd.DataFrame(result),
        hide_index=True,
        use_container_width=True,
        height=460,
        column_config={
            "Metric": st.column_config.TextColumn(
                "Metric",
                width="medium",
            ),
            t1: st.column_config.TextColumn(
                t1,
                width="medium",
            ),
            t2: st.column_config.TextColumn(
                t2,
                width="medium",
            ),
        },
    )

    if c1 != c2:
        st.warning(
            f"Currencies differ ({c1} versus {c2}); "
            "values are not FX-converted."
        )


# ============================================================
# RENDER COMPLETE COMPARISON
# ============================================================

def _render_comparison_dashboard(
    t1,
    i1,
    t2,
    i2,
    period,
    histories=None,
    history_cache_only=False,
):
    """Render both companies and their financial comparison."""

    histories = dict(histories or {})

    if not history_cache_only:
        missing = [
            ticker
            for ticker in (t1, t2)
            if histories.get(ticker) is None
        ]

        if len(missing) == 2:
            with st.spinner(
                "Loading comparison price history..."
            ):
                histories.update(
                    _load_history_pair(
                        t1,
                        t2,
                        period,
                    )
                )

        elif len(missing) == 1:
            ticker = missing[0]

            with st.spinner(
                "Loading price history..."
            ):
                histories[ticker] = company_history(
                    ticker,
                    period,
                )

        history_cache = st.session_state.setdefault(
            "nimbus_comparison_history_cache",
            {},
        )

        for ticker, history in histories.items():
            history_cache[(ticker, period)] = history

    left, right = st.columns(
        2,
        gap="medium",
    )

    with left:
        _profile(
            t1,
            i1,
            period,
            cached_history=histories.get(t1),
            history_cache_only=history_cache_only,
        )

    with right:
        _profile(
            t2,
            i2,
            period,
            cached_history=histories.get(t2),
            history_cache_only=history_cache_only,
        )

    st.markdown(
        '<div class="nimbus-section">'
        'Key metrics comparison'
        '</div>',
        unsafe_allow_html=True,
    )

    _comparison(
        t1,
        i1,
        t2,
        i2,
    )


# ============================================================
# RECENT HISTORY COMPATIBILITY
# ============================================================

def get_cached_comparison(ticker1: str, ticker2: str):
    """
    Retrieve the current comparison and its cached charts.

    Required by features/recent_history.py.
    """

    ticker1 = ticker1.strip().upper()
    ticker2 = ticker2.strip().upper()

    data = st.session_state.get(
        "nimbus_comparison_results"
    )

    if not data:
        return None

    if (
        data[0] != ticker1
        or data[2] != ticker2
    ):
        return None

    selected_period = st.session_state.get(
        "nimbus_history_period",
        "1Y",
    )

    period = PERIOD_LABELS.get(
        selected_period,
        "1y",
    )

    history_cache = st.session_state.get(
        "nimbus_comparison_history_cache",
        {},
    )

    return {
        "data": data,
        "period": period,
        "histories": {
            ticker: history_cache.get(
                (ticker, period)
            )
            for ticker in (ticker1, ticker2)
        },
        "retrieved_at": st.session_state.get(
            "nimbus_comparison_retrieved_at"
        ),
    }


def show_cached_comparison(cached_comparison):
    """
    Display a previously loaded comparison.

    Does not make additional Yahoo Finance requests.
    Required by features/recent_history.py.
    """

    if not cached_comparison:
        st.info(
            "Cached comparison data is not available "
            "for this ticker pair in this session."
        )
        return

    st.markdown(
        CSS,
        unsafe_allow_html=True,
    )

    t1, i1, t2, i2 = cached_comparison["data"]

    retrieved_at = cached_comparison.get(
        "retrieved_at"
    )

    if retrieved_at:
        st.caption(
            f"Cached data retrieved: {retrieved_at}"
        )
    else:
        st.caption(
            "Cached comparison data; "
            "retrieval time unavailable."
        )

    _render_comparison_dashboard(
        t1=t1,
        i1=i1,
        t2=t2,
        i2=i2,
        period=cached_comparison.get(
            "period",
            "1y",
        ),
        histories=cached_comparison.get(
            "histories"
        ),
        history_cache_only=True,
    )


# ============================================================
# STORE COMPARISON
# ============================================================

def _store_comparison(
    ticker1,
    info1,
    ticker2,
    info2,
):
    """Save comparison results to Streamlit session state."""

    ticker1 = ticker1.strip().upper()
    ticker2 = ticker2.strip().upper()

    st.session_state["nimbus_comparison_results"] = (
        ticker1,
        info1,
        ticker2,
        info2,
    )

    st.session_state[
        "nimbus_comparison_retrieved_at"
    ] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    try:
        record_search(
            "comparison",
            ticker1,
            ticker2,
            primary_name=(
                info1.get("shortName")
                or info1.get("longName")
                or ticker1
            ),
            secondary_name=(
                info2.get("shortName")
                or info2.get("longName")
                or ticker2
            ),
        )

    except Exception as error:
        st.caption(
            f"Comparison history could not be saved: {error}"
        )


# ============================================================
# MAIN COMPANY COMPARISON PAGE
# ============================================================

def show_company_comparison(
    ticker1: Optional[str] = None,
    ticker2: Optional[str] = None,
):
    """Render the complete Nimbus Company Comparison page."""

    st.markdown(
        CSS,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="nimbus-kicker">'
        'NIMBUS / FINANCIAL INTELLIGENCE'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="nimbus-title">'
        'Company <span>Comparison</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="nimbus-muted">'
        'Compare companies side by side with price '
        'histories and key financial metrics.'
        '</div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # INPUT FORM
    # --------------------------------------------------------

    with st.form("nimbus_comparison_inputs"):
        left, right, action = st.columns(
            [2.2, 2.2, 1.2],
            vertical_alignment="bottom",
        )

        with left:
            ticker1_value = st.text_input(
                "First company ticker",
                value=(ticker1 or "AAPL").upper(),
                key="nimbus_ticker1",
            ).strip().upper()

        with right:
            ticker2_value = st.text_input(
                "Second company ticker",
                value=(ticker2 or "MSFT").upper(),
                key="nimbus_ticker2",
            ).strip().upper()

        with action:
            submitted = st.form_submit_button(
                "Compare →",
                type="primary",
                use_container_width=True,
            )

    # --------------------------------------------------------
    # FETCH ON SUBMIT
    # --------------------------------------------------------

    if submitted:
        if not ticker1_value or not ticker2_value:
            st.warning(
                "Enter two stock tickers."
            )
            return

        if ticker1_value == ticker2_value:
            st.warning(
                "Choose two different tickers."
            )
            return

        with st.spinner(
            "Fetching company information..."
        ):
            try:
                info1, info2 = _load_company_pair(
                    ticker1_value,
                    ticker2_value,
                )
            except Exception as error:
                st.error(
                    "Could not retrieve company information: "
                    f"{error}"
                )
                return

        _store_comparison(
            ticker1_value,
            info1,
            ticker2_value,
            info2,
        )

    # --------------------------------------------------------
    # OPTIONAL AUTOMATIC COMPARISON
    # --------------------------------------------------------

    data = st.session_state.get(
        "nimbus_comparison_results"
    )

    if data is None and ticker1 and ticker2:
        ticker1 = ticker1.strip().upper()
        ticker2 = ticker2.strip().upper()

        if ticker1 == ticker2:
            st.warning(
                "Choose two different tickers."
            )
            return

        with st.spinner(
            "Fetching company information..."
        ):
            try:
                info1, info2 = _load_company_pair(
                    ticker1,
                    ticker2,
                )
            except Exception as error:
                st.error(
                    "Could not retrieve company information: "
                    f"{error}"
                )
                return

        _store_comparison(
            ticker1,
            info1,
            ticker2,
            info2,
        )

        data = st.session_state.get(
            "nimbus_comparison_results"
        )

    # --------------------------------------------------------
    # WAIT FOR USER SEARCH
    # --------------------------------------------------------

    if data is None:
        st.info(
            "Enter two tickers and select Compare "
            "to load the dashboard."
        )
        return

    t1, i1, t2, i2 = data

    # --------------------------------------------------------
    # STOCK PRICE HISTORY SELECTOR
    # --------------------------------------------------------

    chosen = st.radio(
        "Price history",
        list(PERIOD_LABELS.keys()),
        index=3,
        horizontal=True,
        key="nimbus_history_period",
    )

    period = PERIOD_LABELS.get(
        chosen,
        "1y",
    )

    # --------------------------------------------------------
    # RENDER THE RESULTS
    # --------------------------------------------------------

    _render_comparison_dashboard(
        t1=t1,
        i1=i1,
        t2=t2,
        i2=i2,
        period=period,
    )

    st.caption(
        "Source: Yahoo Finance (via yfinance). "
        f"Viewed {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. "
        "Data may be delayed, incomplete, or cached "
        "for up to 15 minutes. Not investment advice."
    )


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":
    st.set_page_config(
        page_title="Nimbus | Company Comparison",
        layout="wide",
    )

    show_company_comparison()
