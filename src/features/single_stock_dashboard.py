
"""Single-company financial dashboard for Nimbus."""

from datetime import datetime
from html import escape
import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf


# ============================================================
# THEME
# ============================================================

GREEN = "#00B894"
RED = "#FF5264"
BLUE = "#68B1FF"
YELLOW = "#FFD343"

BACKGROUND = "#151A20"
TEXT = "#E7E9ED"
GRID = "#394047"


# ============================================================
# NUMBER AND DATA HELPERS
# ============================================================

def valid(value):
    """Check whether a value is a finite number."""
    try:
        return (
            value is not None
            and not bool(pd.isna(value))
            and math.isfinite(float(value))
        )
    except (TypeError, ValueError):
        return False


def number(value, decimals=2, prefix=""):
    """Format a numeric value."""
    if not valid(value):
        return "—"

    return f"{prefix}{float(value):,.{decimals}f}"


def compact(value):
    """Format large numbers using T, B, M and K."""
    if not valid(value):
        return "—"

    value = float(value)
    absolute = abs(value)

    for threshold, suffix in [
        (1e12, "T"),
        (1e9, "B"),
        (1e6, "M"),
        (1e3, "K"),
    ]:
        if absolute >= threshold:
            return f"{value / threshold:,.2f}{suffix}"

    return f"{value:,.2f}"


def percentage(value):
    """Format a decimal ratio as a percentage."""
    if not valid(value):
        return "—"

    return f"{float(value) * 100:,.2f}%"


def date_text(value):
    """Format a Unix timestamp or date."""
    if value is None:
        return "—"

    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(
                value
            ).strftime("%d %b %Y")

        return pd.Timestamp(value).strftime("%d %b %Y")

    except Exception:
        return "—"


def safe_attribute(stock, name):
    """Read Yahoo Finance attributes safely."""
    try:
        return getattr(stock, name)
    except Exception:
        return None


def first_valid(*values):
    """Return the first valid numeric value."""
    for value in values:
        if valid(value):
            return value

    return None


# ============================================================
# YAHOO FINANCE DATA
# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def get_company_info(ticker):
    return yf.Ticker(ticker).info or {}


@st.cache_data(ttl=600, show_spinner=False)
def get_stock_history(ticker, period, interval):
    return yf.Ticker(ticker).history(
        period=period,
        interval=interval,
        auto_adjust=True,
    )


@st.cache_data(ttl=3600, show_spinner=False)
def get_extra_data(ticker):
    stock = yf.Ticker(ticker)

    return {
        "analyst_price_targets": safe_attribute(
            stock,
            "analyst_price_targets",
        ),
        "recommendations": safe_attribute(
            stock,
            "recommendations",
        ),
        "upgrades_downgrades": safe_attribute(
            stock,
            "upgrades_downgrades",
        ),
        "earnings_history": safe_attribute(
            stock,
            "earnings_history",
        ),
        "quarterly_income_stmt": safe_attribute(
            stock,
            "quarterly_income_stmt",
        ),
    }


# ============================================================
# HISTORICAL STOCK DATA
# ============================================================

def get_history_for_range(ticker, selected_range):
    """
    Retrieve stock price history.

    Short periods use intraday data.
    Longer periods use daily, weekly or monthly data.
    """

    options = {
        "1D": ("1d", "1m"),
        "5D": ("5d", "5m"),
        "1M": ("1mo", "1d"),
        "6M": ("6mo", "1d"),
        "YTD": ("ytd", "1d"),
        "1Y": ("1y", "1d"),
        "5Y": ("5y", "1wk"),
        "All": ("max", "1mo"),
    }

    period, interval = options[selected_range]

    return get_stock_history(
        ticker,
        period,
        interval,
    )


# ============================================================
# YAHOO FINANCE-STYLE PRICE CHART
# ============================================================

def create_stock_chart(
    history,
    chart_type="Price",
    show_volume=True,
    previous_close=None,
    currency="USD",
    selected_range="1M",
    ticker="",
):
    """
    Create an interactive stock price chart.

    Features:
    - Actual observed Yahoo Finance prices
    - No smoothing
    - Tight Y-axis range
    - Candlestick option
    - Trading volume
    - Previous-close reference line
    """

    if history is None or history.empty:
        return go.Figure()

    data = history.copy().sort_index()

    for column in [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

    data = data.dropna(subset=["Close"])

    if data.empty:
        return go.Figure()

    dates = data.index
    close = data["Close"]

    intraday = selected_range in [
        "1D",
        "5D",
    ]

    has_volume = (
        show_volume
        and "Volume" in data.columns
        and data["Volume"].notna().any()
    )

    fig = make_subplots(
        rows=2 if has_volume else 1,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.80, 0.20] if has_volume else None,
    )

    first_price = float(close.iloc[0])
    last_price = float(close.iloc[-1])

    line_color = (
        GREEN if last_price >= first_price else RED
    )

    # --------------------------------------------------------
    # PRICE OR CANDLESTICK GRAPH
    # --------------------------------------------------------

    if chart_type == "Candlestick":

        fig.add_trace(
            go.Candlestick(
                x=dates,
                open=data["Open"],
                high=data["High"],
                low=data["Low"],
                close=data["Close"],
                increasing_line_color=GREEN,
                decreasing_line_color=RED,
                increasing_fillcolor=GREEN,
                decreasing_fillcolor=RED,
                name="OHLC",
            ),
            row=1,
            col=1,
        )

        minimum = float(data["Low"].min())
        maximum = float(data["High"].max())

    else:

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=close,
                mode="lines",
                line=dict(
                    color=line_color,
                    width=1.7,
                    shape="linear",
                    simplify=False,
                ),
                connectgaps=False,
                name="Stock price",
                hovertemplate=(
                    "%{x|%d %b %Y %H:%M}"
                    "<br>Price: %{y:,.2f}"
                    "<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

        minimum = float(close.min())
        maximum = float(close.max())

    # --------------------------------------------------------
    # TIGHT PRICE AXIS
    # --------------------------------------------------------

    spread = maximum - minimum

    if spread <= 0:
        spread = max(
            abs(last_price) * 0.002,
            0.01,
        )

    padding = spread * 0.12

    lower = minimum - padding
    upper = maximum + padding

    # --------------------------------------------------------
    # PREVIOUS CLOSE REFERENCE
    # --------------------------------------------------------

    if valid(previous_close):

        previous = float(previous_close)

        if lower <= previous <= upper:

            fig.add_hline(
                y=previous,
                line_dash="dot",
                line_color="#86919E",
                opacity=0.5,
                row=1,
                col=1,
            )

    # --------------------------------------------------------
    # LAST PRICE MARKER
    # --------------------------------------------------------

    fig.add_trace(
        go.Scatter(
            x=[dates[-1]],
            y=[last_price],
            mode="markers",
            marker=dict(
                size=7,
                color=line_color,
            ),
            showlegend=False,
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )

    # --------------------------------------------------------
    # TRADING VOLUME
    # --------------------------------------------------------

    if has_volume:

        differences = close.diff().fillna(0)

        bar_colors = [
            GREEN if difference >= 0 else RED
            for difference in differences
        ]

        fig.add_trace(
            go.Bar(
                x=dates,
                y=data["Volume"].fillna(0),
                marker_color=bar_colors,
                opacity=0.65,
                name="Volume",
                hovertemplate=(
                    "%{x|%d %b %Y %H:%M}"
                    "<br>Volume: %{y:,.0f}"
                    "<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

        fig.update_yaxes(
            tickformat="~s",
            showgrid=False,
            zeroline=False,
            row=2,
            col=1,
        )

    # --------------------------------------------------------
    # AXIS SETTINGS
    # --------------------------------------------------------

    range_breaks = []

    # Hide weekends for trading charts.
    if isinstance(dates, pd.DatetimeIndex):

        range_breaks.append(
            dict(bounds=["sat", "mon"])
        )

        # Hide overnight gaps only for US equity tickers.
        # Other exchanges can have different trading hours.
        ticker_upper = (ticker or "").upper()

        non_us_suffixes = (
            ".SI", ".HK", ".L", ".TO",
            ".AX", ".T", ".PA", ".DE",
            ".MI", ".SW", ".KS", ".KQ",
        )

        if (
            intraday
            and ticker_upper
            and not ticker_upper.endswith(non_us_suffixes)
        ):
            range_breaks.append(
                dict(
                    bounds=[16, 9.5],
                    pattern="hour",
                )
            )

    price_prefix = (
        "$" if currency == "USD" else ""
    )

    fig.update_yaxes(
        range=[lower, upper],
        tickprefix=price_prefix,
        tickformat=",.2f",
        side="right",
        showgrid=True,
        gridcolor="rgba(140,150,160,0.20)",
        zeroline=False,
        row=1,
        col=1,
    )

    fig.update_xaxes(
        type="date",
        rangebreaks=range_breaks,
        showgrid=False,
        zeroline=False,
        rangeslider_visible=False,
    )

    # --------------------------------------------------------
    # DARK STYLE
    # --------------------------------------------------------

    fig.update_layout(
        height=480,
        margin=dict(
            l=12,
            r=60,
            t=20,
            b=15,
        ),
        paper_bgcolor=BACKGROUND,
        plot_bgcolor=BACKGROUND,
        font=dict(
            color=TEXT,
            size=12,
        ),
        showlegend=False,
        hovermode="x unified",
        dragmode="zoom",
        bargap=0.10,
        xaxis_rangeslider_visible=False,
    )

    return fig


# ============================================================
# STATISTIC ROW DESIGN
# ============================================================

def statistic_row(label, value):
    """
    Display one label/value row with a dotted separator.
    """

    st.markdown(
        (
            '<div class="nimbus-stat-row">'
            f"<span>{escape(str(label))}</span>"
            f"<strong>{escape(str(value))}</strong>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


# ============================================================
# KEY STATISTICS — NO TITLE
# ============================================================

def display_key_statistics(info):
    """
    Yahoo Finance-style key statistics.

    No heading.
    No surrounding cards.
    Four columns with dotted separators.
    """

    # --------------------------------------------------------
    # DIVIDEND AND YIELD
    # --------------------------------------------------------

    dividend_rate = info.get("dividendRate")
    dividend_yield = info.get("dividendYield")

    if valid(dividend_yield):

        yield_value = float(dividend_yield)

        # Yahoo Finance may report yields as a
        # percentage number such as 0.31.
        # Prefer the directly supplied dividend rate
        # and price when both are available.
        current_price = first_valid(
            info.get("currentPrice"),
            info.get("regularMarketPrice"),
        )

        if (
            valid(dividend_rate)
            and valid(current_price)
            and float(current_price) > 0
        ):
            yield_percent = (
                float(dividend_rate)
                / float(current_price)
                * 100
            )

        elif yield_value > 0.1:
            yield_percent = yield_value

        else:
            yield_percent = yield_value * 100

        yield_text = f"{yield_percent:.2f}%"

    else:
        yield_text = "—"

    if valid(dividend_rate):
        dividend_text = (
            f"{number(dividend_rate)} ({yield_text})"
        )
    else:
        dividend_text = "—"

    # --------------------------------------------------------
    # BID / ASK
    # --------------------------------------------------------

    bid = info.get("bid")
    ask = info.get("ask")

    bid_size = info.get("bidSize")
    ask_size = info.get("askSize")

    bid_text = number(bid)
    ask_text = number(ask)

    if valid(bid) and valid(bid_size):
        if float(bid_size) > 0:
            bid_text += (
                f" x {int(float(bid_size)):,}"
            )

    if valid(ask) and valid(ask_size):
        if float(ask_size) > 0:
            ask_text += (
                f" x {int(float(ask_size)):,}"
            )

    # --------------------------------------------------------
    # FOUR STATISTIC COLUMNS
    # --------------------------------------------------------

    groups = [
        [
            (
                "Previous close",
                number(info.get("previousClose")),
            ),
            (
                "Open",
                number(info.get("open")),
            ),
            (
                "Bid",
                bid_text,
            ),
            (
                "Ask",
                ask_text,
            ),
        ],
        [
            (
                "Day's range",
                (
                    f"{number(info.get('dayLow'))} - "
                    f"{number(info.get('dayHigh'))}"
                ),
            ),
            (
                "52-week range",
                (
                    f"{number(info.get('fiftyTwoWeekLow'))} - "
                    f"{number(info.get('fiftyTwoWeekHigh'))}"
                ),
            ),
            (
                "Volume",
                number(
                    info.get("volume"),
                    0,
                ),
            ),
            (
                "Avg. volume",
                number(
                    info.get("averageVolume"),
                    0,
                ),
            ),
        ],
        [
            (
                "Market cap (intra-day)",
                compact(info.get("marketCap")),
            ),
            (
                "Beta (5Y monthly)",
                number(info.get("beta")),
            ),
            (
                "PE ratio (TTM)",
                number(info.get("trailingPE")),
            ),
            (
                "EPS (TTM)",
                number(info.get("trailingEps")),
            ),
        ],
        [
            (
                "Earnings date",
                date_text(
                    first_valid(
                        info.get("earningsTimestamp"),
                        info.get("earningsTimestampStart"),
                    )
                ),
            ),
            (
                "Forward dividend & yield",
                dividend_text,
            ),
            (
                "Ex-dividend date",
                date_text(info.get("exDividendDate")),
            ),
            (
                "1y target est",
                number(info.get("targetMeanPrice")),
            ),
        ],
    ]

    columns = st.columns(
        4,
        gap="medium",
    )

    for column, items in zip(
        columns,
        groups,
    ):
        with column:
            for label, value in items:
                statistic_row(
                    label,
                    value,
                )


# ============================================================
# PERFORMANCE OVERVIEW
# ============================================================

def calculate_return(prices, days=None):
    prices = prices.dropna()

    if prices.empty:
        return None

    if days is None:

        year = prices.index[-1].year

        previous = prices[
            prices.index.year < year
        ]

    else:

        cutoff = (
            prices.index[-1]
            - pd.Timedelta(days=days)
        )

        previous = prices[
            prices.index <= cutoff
        ]

    if previous.empty:
        return None

    starting_price = float(previous.iloc[-1])
    ending_price = float(prices.iloc[-1])

    if starting_price == 0:
        return None

    return (
        ending_price / starting_price - 1
    ) * 100


def display_performance(ticker):
    st.subheader("Performance Overview")

    st.caption(
        "Approximate adjusted-price returns "
        "compared with the S&P 500 (^GSPC)."
    )

    try:

        stock_prices = get_stock_history(
            ticker,
            "10y",
            "1wk",
        )["Close"].dropna()

        benchmark_prices = get_stock_history(
            "^GSPC",
            "10y",
            "1wk",
        )["Close"].dropna()

    except Exception:

        st.info(
            "Performance data is unavailable."
        )

        return

    if (
        stock_prices.empty
        or benchmark_prices.empty
    ):

        st.info(
            "Not enough historical data."
        )

        return

    latest_date = min(
        stock_prices.index.max(),
        benchmark_prices.index.max(),
    )

    stock_prices = stock_prices[
        stock_prices.index <= latest_date
    ]

    benchmark_prices = benchmark_prices[
        benchmark_prices.index <= latest_date
    ]

    periods = [
        ("YTD", None),
        ("1-year", 365),
        ("3-year", 1095),
        ("5-year", 1825),
    ]

    columns = st.columns(4)

    for column, (label, days) in zip(
        columns,
        periods,
    ):

        stock_return = calculate_return(
            stock_prices,
            days,
        )

        benchmark_return = calculate_return(
            benchmark_prices,
            days,
        )

        with column:

            with st.container(border=True):

                st.markdown(
                    f"**{label} Return**"
                )

                st.metric(
                    ticker,
                    (
                        f"{stock_return:+.2f}%"
                        if stock_return is not None
                        else "—"
                    ),
                )

                st.caption(
                    (
                        f"S&P 500: {benchmark_return:+.2f}%"
                        if benchmark_return is not None
                        else "S&P 500: —"
                    )
                )


# ============================================================
# EARNINGS TRENDS
# ============================================================

def display_earnings(extra, currency):
    st.subheader("Earnings Trends")

    left, right = st.columns(2)

    # --------------------------------------------------------
    # EPS ACTUAL VS ESTIMATE
    # --------------------------------------------------------

    with left:

        with st.container(border=True):

            st.markdown(
                "**EPS: Actual vs. Estimate**"
            )

            earnings = extra.get(
                "earnings_history"
            )

            if (
                isinstance(earnings, pd.DataFrame)
                and not earnings.empty
                and {
                    "epsEstimate",
                    "epsActual",
                }.issubset(earnings.columns)
            ):

                data = (
                    earnings
                    .sort_index()
                    .tail(6)
                )

                labels = [
                    pd.Timestamp(value).strftime("%b %Y")
                    for value in data.index
                ]

                fig = go.Figure()

                fig.add_bar(
                    x=labels,
                    y=data["epsEstimate"],
                    name="Estimate",
                    marker_color="#7897B5",
                )

                fig.add_bar(
                    x=labels,
                    y=data["epsActual"],
                    name="Actual",
                    marker_color=GREEN,
                )

                fig.update_layout(
                    barmode="group",
                    height=320,
                    paper_bgcolor=BACKGROUND,
                    plot_bgcolor=BACKGROUND,
                    font_color=TEXT,
                    legend=dict(
                        orientation="h",
                    ),
                    margin=dict(
                        l=5,
                        r=5,
                        t=10,
                        b=10,
                    ),
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True,
                )

            else:

                st.info(
                    "Earnings estimate history unavailable."
                )

    # --------------------------------------------------------
    # REVENUE VS NET INCOME
    # --------------------------------------------------------

    with right:

        with st.container(border=True):

            st.markdown(
                "**Quarterly Revenue vs. Net Income**"
            )

            statement = extra.get(
                "quarterly_income_stmt"
            )

            if (
                isinstance(statement, pd.DataFrame)
                and not statement.empty
                and "Total Revenue" in statement.index
            ):

                data = (
                    statement.T
                    .sort_index()
                    .tail(5)
                )

                profit_column = next(
                    (
                        column
                        for column in [
                            "Net Income",
                            "Net Income Common Stockholders",
                            "Net Income From Continuing Operation Net Minority Interest",
                        ]
                        if column in data.columns
                    ),
                    None,
                )

                labels = [
                    (
                        f"{pd.Timestamp(value).year} "
                        f"Q{pd.Timestamp(value).quarter}"
                    )
                    for value in data.index
                ]

                revenue = pd.to_numeric(
                    data["Total Revenue"],
                    errors="coerce",
                )

                fig = go.Figure()

                fig.add_bar(
                    x=labels,
                    y=revenue / 1e9,
                    name="Revenue",
                    marker_color=BLUE,
                )

                if profit_column:

                    net_income = pd.to_numeric(
                        data[profit_column],
                        errors="coerce",
                    )

                    fig.add_bar(
                        x=labels,
                        y=net_income / 1e9,
                        name="Net Income",
                        marker_color=YELLOW,
                    )

                fig.update_layout(
                    barmode="group",
                    height=320,
                    paper_bgcolor=BACKGROUND,
                    plot_bgcolor=BACKGROUND,
                    font_color=TEXT,
                    legend=dict(
                        orientation="h",
                    ),
                    margin=dict(
                        l=5,
                        r=5,
                        t=10,
                        b=10,
                    ),
                    yaxis=dict(
                        title=f"{currency} billions",
                        gridcolor=GRID,
                    ),
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True,
                )

            else:

                st.info(
                    "Quarterly financial data unavailable."
                )


# ============================================================
# ANALYST INSIGHTS
# ============================================================

def display_analyst_insights(info, extra, ratings):
    st.subheader("Analyst Insights")

    col1, col2, col3 = st.columns(3)

    targets = extra.get(
        "analyst_price_targets"
    )

    if not isinstance(targets, dict):
        targets = {}

    currency = info.get("currency") or "USD"

    prefix = (
        "$"
        if currency == "USD"
        else f"{currency} "
    )

    # --------------------------------------------------------
    # ANALYST PRICE TARGETS
    # --------------------------------------------------------

    with col1:

        with st.container(border=True):

            st.markdown(
                "**Analysts' Price Targets**"
            )

            low = first_valid(
                targets.get("low"),
                info.get("targetLowPrice"),
            )

            mean = first_valid(
                targets.get("mean"),
                info.get("targetMeanPrice"),
            )

            high = first_valid(
                targets.get("high"),
                info.get("targetHighPrice"),
            )

            st.metric(
                "Average target",
                number(
                    mean,
                    prefix=prefix,
                ),
            )

            st.caption(
                f"Low: {number(low, prefix=prefix)}"
            )

            st.caption(
                f"High: {number(high, prefix=prefix)}"
            )

    # --------------------------------------------------------
    # ANALYST RECOMMENDATIONS
    # --------------------------------------------------------

    with col2:

        with st.container(border=True):

            st.markdown(
                "**Analyst Recommendations**"
            )

            if (
                not isinstance(ratings, pd.DataFrame)
                or ratings.empty
            ):
                ratings = extra.get(
                    "recommendations"
                )

            required = [
                "strongBuy",
                "buy",
                "hold",
                "sell",
                "strongSell",
            ]

            if (
                isinstance(ratings, pd.DataFrame)
                and not ratings.empty
                and all(
                    column in ratings.columns
                    for column in required
                )
            ):

                available = ratings

                if "period" in ratings.columns:

                    current = ratings[
                        ratings["period"].astype(str)
                        == "0m"
                    ]

                    if not current.empty:
                        available = current

                latest = available.iloc[0]

                counts = [
                    (
                        int(latest[column])
                        if valid(latest[column])
                        else 0
                    )
                    for column in required
                ]

                total = sum(counts)

                positive = (
                    counts[0] + counts[1]
                )

                neutral = counts[2]

                negative = (
                    counts[3] + counts[4]
                )

                if total > 0:

                    st.metric(
                        "Positive recommendations",
                        f"{positive / total * 100:.1f}%",
                    )

                    st.progress(
                        positive / total
                    )

                    st.caption(
                        f"{positive} positive · "
                        f"{neutral} neutral · "
                        f"{negative} negative"
                    )

                else:

                    st.info(
                        "No recommendation counts available."
                    )

                with st.expander(
                    "Detailed recommendation periods"
                ):

                    st.dataframe(
                        ratings,
                        hide_index=True,
                        width="stretch",
                    )

            else:

                st.info(
                    "Analyst recommendations unavailable."
                )

    # --------------------------------------------------------
    # LATEST ANALYST ACTION
    # --------------------------------------------------------

    with col3:

        with st.container(border=True):

            st.markdown(
                "**Latest Analyst Rating Action**"
            )

            actions = extra.get(
                "upgrades_downgrades"
            )

            if (
                isinstance(actions, pd.DataFrame)
                and not actions.empty
            ):

                latest_actions = (
                    actions.sort_index(
                        ascending=False
                    )
                )

                action = latest_actions.iloc[0]

                st.caption(
                    date_text(
                        latest_actions.index[0]
                    )
                )

                st.markdown(
                    f"**{action.get('Firm', 'Unknown firm')}**"
                )

                for field in [
                    "Action",
                    "ToGrade",
                    "FromGrade",
                ]:

                    value = action.get(field)

                    if (
                        value is not None
                        and pd.notna(value)
                    ):

                        st.caption(
                            f"{field}: {value}"
                        )

            else:

                st.info(
                    "Individual analyst actions unavailable."
                )


# ============================================================
# FINANCIAL STATISTICS
# ============================================================

def display_financial_statistics(info):
    st.subheader("Financial Statistics")

    valuation = [
        (
            "Market cap",
            compact(info.get("marketCap")),
        ),
        (
            "Enterprise value",
            compact(info.get("enterpriseValue")),
        ),
        (
            "Trailing P/E",
            number(info.get("trailingPE")),
        ),
        (
            "Forward P/E",
            number(info.get("forwardPE")),
        ),
        (
            "PEG ratio",
            number(
                first_valid(
                    info.get("trailingPegRatio"),
                    info.get("pegRatio"),
                )
            ),
        ),
        (
            "Price / sales",
            number(
                info.get(
                    "priceToSalesTrailing12Months"
                )
            ),
        ),
        (
            "Price / book",
            number(info.get("priceToBook")),
        ),
        (
            "EV / revenue",
            number(
                info.get("enterpriseToRevenue")
            ),
        ),
        (
            "EV / EBITDA",
            number(
                info.get("enterpriseToEbitda")
            ),
        ),
    ]

    financial = [
        (
            "Profit margin",
            percentage(info.get("profitMargins")),
        ),
        (
            "Return on assets",
            percentage(info.get("returnOnAssets")),
        ),
        (
            "Return on equity",
            percentage(info.get("returnOnEquity")),
        ),
        (
            "Revenue (TTM)",
            compact(info.get("totalRevenue")),
        ),
        (
            "Net income (TTM)",
            compact(info.get("netIncomeToCommon")),
        ),
        (
            "Diluted EPS (TTM)",
            number(info.get("trailingEps")),
        ),
        (
            "Total cash",
            compact(info.get("totalCash")),
        ),
        (
            "Debt / equity",
            (
                f"{number(info.get('debtToEquity'))}%"
                if valid(info.get("debtToEquity"))
                else "—"
            ),
        ),
        (
            "Levered free cash flow",
            compact(info.get("freeCashflow")),
        ),
    ]

    left, right = st.columns(2)

    with left:

        with st.container(border=True):

            st.markdown(
                "**Valuation Measures**"
            )

            for label, value in valuation:

                statistic_row(
                    label,
                    value,
                )

    with right:

        with st.container(border=True):

            st.markdown(
                "**Financial Highlights**"
            )

            for label, value in financial:

                statistic_row(
                    label,
                    value,
                )


# ============================================================
# MAIN SINGLE STOCK DASHBOARD
# ============================================================

def show_single_stock_dashboard(
    ticker,
    ratings=None,
    overview_callback=None,
):
    """
    Final Nimbus layout:

    1. Company name and current stock price
    2. Historical Stock Price
    3. Four-column key statistics (NO heading)
    4. Company Overview
    5. Performance Overview
    6. Earnings Trends
    7. Analyst Insights
    8. Financial Statistics
    """

    ticker = (ticker or "").strip().upper()

    if not ticker:

        st.warning(
            "Please enter a ticker."
        )

        return

    # --------------------------------------------------------
    # CUSTOM STYLING
    # --------------------------------------------------------

    st.markdown(
        """
        <style>
        .nimbus-stat-row {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 12px;
            min-height: 43px;
            padding: 9px 0;
            border-bottom: 1px dotted #303841;
            font-size: 0.88rem;
        }

        .nimbus-stat-row span {
            color: #C4C8CC;
            flex: 1;
        }

        .nimbus-stat-row strong {
            color: #F0F2F3;
            text-align: right;
            font-weight: 650;
            white-space: normal;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # COMPANY INFORMATION
    # --------------------------------------------------------

    try:
        info = get_company_info(ticker)
    except Exception:
        info = {}

    company_name = (
        info.get("longName")
        or info.get("shortName")
        or ticker
    )

    currency = (
        info.get("currency")
        or "USD"
    )

    exchange = (
        info.get("fullExchangeName")
        or info.get("exchange")
        or "Exchange unavailable"
    )

    price_prefix = (
        "$"
        if currency == "USD"
        else f"{currency} "
    )

    # ========================================================
    # 1. COMPANY NAME AND STOCK PRICE
    # ========================================================

    st.caption(
        f"{exchange} · {currency} · "
        "Market quotes may be delayed"
    )

    st.title(
        f"{company_name} ({ticker})"
    )

    current_price = first_valid(
        info.get("currentPrice"),
        info.get("regularMarketPrice"),
    )

    previous_close = info.get(
        "previousClose"
    )

    if not valid(current_price):

        try:

            recent = get_stock_history(
                ticker,
                "5d",
                "1d",
            )

            current_price = (
                recent["Close"]
                .dropna()
                .iloc[-1]
            )

        except Exception:

            current_price = None

    delta = None

    if (
        valid(current_price)
        and valid(previous_close)
        and float(previous_close) != 0
    ):

        change = (
            float(current_price)
            - float(previous_close)
        )

        change_pct = (
            change / float(previous_close)
            * 100
        )

        delta = (
            f"{change:+,.2f} "
            f"({change_pct:+.2f}%)"
        )

    price_col, after_hours_col = (
        st.columns([2, 1])
    )

    with price_col:

        st.metric(
            "Latest regular-market price",
            number(
                current_price,
                prefix=price_prefix,
            ),
            delta,
        )

    with after_hours_col:

        postmarket = info.get(
            "postMarketPrice"
        )

        premarket = info.get(
            "preMarketPrice"
        )

        if valid(postmarket):

            st.metric(
                "Post-market price",
                number(
                    postmarket,
                    prefix=price_prefix,
                ),
            )

        elif valid(premarket):

            st.metric(
                "Pre-market price",
                number(
                    premarket,
                    prefix=price_prefix,
                ),
            )

        else:

            st.caption(
                "Pre-/post-market price unavailable."
            )

    # ========================================================
    # 2. HISTORICAL STOCK PRICE
    # ========================================================

    st.divider()

    st.subheader(
        "Historical Stock Price"
    )

    controls = st.columns(
        [3, 1, 1]
    )

    with controls[0]:

        selected_range = st.selectbox(
            "Time range",
            [
                "1D",
                "5D",
                "1M",
                "6M",
                "YTD",
                "1Y",
                "5Y",
                "All",
            ],
            index=2,
            key=f"stock_range_{ticker}",
        )

    with controls[1]:

        chart_type = st.selectbox(
            "Chart type",
            [
                "Price",
                "Candlestick",
            ],
            key=f"stock_chart_type_{ticker}",
        )

    with controls[2]:

        show_volume = st.checkbox(
            "Show volume",
            value=True,
            key=f"stock_volume_{ticker}",
        )

    try:

        history = get_history_for_range(
            ticker,
            selected_range,
        )

        if history.empty:

            st.info(
                "No historical prices available "
                "for this time range."
            )

        else:

            fig = create_stock_chart(
                history,
                chart_type=chart_type,
                show_volume=show_volume,
                previous_close=previous_close,
                currency=currency,
                selected_range=selected_range,
                ticker=ticker,
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
                config={
                    "displaylogo": False,
                    "scrollZoom": True,
                },
            )

            prices = (
                history["Close"]
                .dropna()
            )

            if len(prices) >= 2:

                first = float(
                    prices.iloc[0]
                )

                last = float(
                    prices.iloc[-1]
                )

                if first != 0:

                    price_change_pct = (
                        last / first - 1
                    ) * 100

                    st.caption(
                        f"{selected_range} price change: "
                        f"{price_change_pct:+.2f}%"
                    )

    except Exception as error:

        st.warning(
            f"Unable to load stock chart: {error}"
        )

    # ========================================================
    # 3. FOUR-COLUMN KEY STATISTICS
    #    NO TITLE
    # ========================================================

    st.divider()

    display_key_statistics(info)

    # ========================================================
    # 4. COMPANY OVERVIEW
    #    DIRECTLY BELOW KEY STATISTICS
    # ========================================================

    if overview_callback is not None:

        overview_callback(ticker)

    else:

        with st.expander(
            f"{company_name} Overview",
            expanded=False,
        ):

            st.write(
                info.get("longBusinessSummary")
                or "Company description unavailable."
            )

            st.write(
                "Sector:",
                info.get("sector") or "N/A",
            )

            st.write(
                "Industry:",
                info.get("industry") or "N/A",
            )

    # ========================================================
    # 5. PERFORMANCE OVERVIEW
    # ========================================================

    st.divider()

    display_performance(ticker)

    # ========================================================
    # GET ADDITIONAL FINANCIAL DATA
    # ========================================================

    try:

        extra = get_extra_data(ticker)

    except Exception:

        extra = {}

    # ========================================================
    # 6. EARNINGS TRENDS
    # ========================================================

    st.divider()

    display_earnings(
        extra,
        currency,
    )

    # ========================================================
    # 7. ANALYST INSIGHTS
    # ========================================================

    st.divider()

    display_analyst_insights(
        info,
        extra,
        ratings,
    )

    # ========================================================
    # 8. FINANCIAL STATISTICS
    # ========================================================

    st.divider()

    display_financial_statistics(info)

    # ========================================================
    # DATA SOURCE
    # ========================================================

    st.caption(
        "Source: Yahoo Finance via yfinance. "
        "Historical prices are adjusted."
    )
