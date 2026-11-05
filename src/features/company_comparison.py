"""Company-comparison UI, cached Yahoo Finance lookups, and chart/metric rendering."""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from html import escape
import math
from typing import Optional

import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis import get_financials
from features.history import record_search


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGO_DIR = PROJECT_ROOT / "assets" / "company_logos"

# Public brand icons. Add a local PNG under assets/company_logos/TICKER.png
# if you prefer to supply a logo yourself.
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

# Style the custom dashboard cards while keeping charts, tables, and controls native.
CSS = """
<style>
.nimbus-logo-wrap {display:inline-flex;width:48px;height:48px;align-items:center;justify-content:center;flex-shrink:0;}
.nimbus-logo-wrap img {max-width:44px;max-height:44px;object-fit:contain;}
.nimbus-logo-fallback {flex-shrink:0;}
.nimbus-kicker, .nimbus-title, .nimbus-muted, .nimbus-section {font-family:Consolas,monospace;}
.nimbus-title {font-size:2.65rem;font-weight:800;letter-spacing:-.045em;line-height:1.15;margin:.4rem 0;}
.nimbus-title span {background:linear-gradient(95deg,#45b8ff,#8576ff);color:transparent;background-clip:text;-webkit-background-clip:text;}
.nimbus-muted {color:#9daec3;font-size:.92rem;margin:0 0 1.2rem;}
.nimbus-kicker {font-size:.75rem;color:#7a9ccc;letter-spacing:.16em;font-weight:700;}
.nimbus-company {display:flex;gap:13px;align-items:center;margin-bottom:10px;}
.nimbus-mark {width:47px;height:47px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:1.05rem;background:linear-gradient(135deg,#223c64,#225da3);border:1px solid #405a79;}
.nimbus-logo {width:47px;height:47px;border-radius:12px;object-fit:contain;background:#1a293d;padding:7px;border:1px solid #405a79;}
.nimbus-name {font-size:1.08rem;font-weight:740;line-height:1.35;}
.nimbus-symbol {font-size:.77rem;color:#91a5ba;}
.nimbus-section {font-size:1.15rem;font-weight:750;margin:.45rem 0 1rem;}
.nimbus-note {font-size:.76rem;color:#91a1b3;}
[data-testid="stVerticalBlockBorderWrapper"] > div {border-color:#29394d!important;}
.stApp {background:#0b121d;}
div[data-testid="stMetric"] {background:#111e30;border:1px solid #25374e;border-radius:12px;padding:12px 14px;}
div[data-testid="stMetricLabel"] {color:#a7b8cc;}
div[data-testid="stMetricValue"] {font-size:1.48rem;}
.stButton button[kind="primary"], button[data-testid="stBaseButton-primary"] {background:linear-gradient(105deg,#1260e8,#634cf0);border:0;color:white;}
</style>
"""


def _number(value, decimals=2, prefix="", suffix=""):
    """Format a finite numeric value with optional prefix and suffix."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return "N/A"
    return f"{prefix}{value:,.{decimals}f}{suffix}"


def _big(value, currency="USD"):
    """Format a financial value using compact K, M, B, or T units."""
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return "N/A"
    sign = "-" if value < 0 else ""
    v = abs(value)
    units = ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K"))
    for factor, suffix in units:
        if v >= factor:
            return f"{sign}{v/factor:,.2f}{suffix} {currency}"
    return f"{sign}{v:,.2f} {currency}"


def _percent(value):
    """Convert a fractional value to a percentage string."""
    return _number(value * 100, suffix="%") if isinstance(value, (int, float)) else "N/A"


@st.cache_data(ttl=900, show_spinner=False)
def company_info(ticker):
    """Fetch company details and reject responses without a recognizable company."""
    info = yf.Ticker(ticker).info or {}
    if not info or not (info.get("symbol") or info.get("shortName")):
        raise ValueError(f"No Yahoo Finance information found for {ticker}.")
    return info


@st.cache_data(ttl=900, show_spinner=False)
def company_history(ticker, period):
    """Fetch and validate the OHLCV price history needed by the comparison chart."""
    result = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    needed = ["Open", "High", "Low", "Close", "Volume"]
    if not isinstance(result, pd.DataFrame) or any(c not in result.columns for c in needed):
        return pd.DataFrame(columns=needed)
    return result[needed].dropna(subset=["Close"])


@st.cache_data(ttl=86400, show_spinner=False)
def currency_history(currency):
    """Fetch historical USD-per-unit FX rates for one source currency."""
    currency = str(currency or "").upper()
    if currency == "USD":
        return pd.DataFrame(columns=["Close"])
    result = yf.Ticker(f"{currency}USD=X").history(
        period="max",
        auto_adjust=False,
    )
    if not isinstance(result, pd.DataFrame) or "Close" not in result.columns:
        return pd.DataFrame(columns=["Close"])
    return result[["Close"]].dropna()


def _load_company_pair(ticker1, ticker2):
    """Load the two Yahoo company profiles concurrently, preserving input order."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(company_info, ticker1)
        second = executor.submit(company_info, ticker2)
        return first.result(), second.result()


def _load_history_pair(ticker1, ticker2, period):
    """Load price histories concurrently; the underlying functions are cached."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(company_history, ticker1, period)
        second = executor.submit(company_history, ticker2, period)
        return {ticker1: first.result(), ticker2: second.result()}


def _currency_code(currency):
    """Return a Yahoo FX pair's base code and unit conversion factor."""
    raw_code = str(currency or "USD")
    code = raw_code.upper()
    if raw_code == "GBp" or code == "GBX":
        return "GBP", 0.01
    return code, 1.0


def _normalized_date_index(index):
    """Keep each market's calendar date while removing timezone and time."""
    dates = pd.DatetimeIndex(pd.to_datetime(index))
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    return dates.normalize()


def _fx_series(currency, fx_histories):
    """Return daily USD-per-unit FX rates indexed by normalized date."""
    code, _ = _currency_code(currency)
    if code == "USD":
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    frame = (fx_histories or {}).get(code)
    if not isinstance(frame, pd.DataFrame) or frame.empty or "Close" not in frame:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    rates = pd.to_numeric(frame["Close"], errors="coerce").dropna().copy()
    rates.index = _normalized_date_index(rates.index)
    return rates[~rates.index.duplicated(keep="last")].sort_index()


def _fx_rate_as_of(currency, value_date, fx_histories):
    """Return the last available USD FX rate on or before a date."""
    code, unit_scale = _currency_code(currency)
    if code == "USD":
        return 1.0
    rates = _fx_series(code, fx_histories)
    if rates.empty:
        return None
    target = _normalized_date_index([pd.Timestamp(value_date)])[0]
    available = rates.loc[:target]
    if available.empty:
        return None
    return float(available.iloc[-1]) * unit_scale


def _to_usd_history(history, currency, fx_histories):
    """Convert OHLC prices into USD using the rate on each trading date."""
    if history is None or history.empty:
        return history, True
    code, unit_scale = _currency_code(currency)
    converted = history.copy()
    if code == "USD":
        converted["FXRateToUSD"] = 1.0
        return converted, True
    rates = _fx_series(code, fx_histories)
    if rates.empty:
        return converted.iloc[0:0], False
    normalized_dates = _normalized_date_index(converted.index)
    daily_rates = rates.reindex(normalized_dates, method="ffill") * unit_scale
    daily_rates.index = converted.index
    converted["FXRateToUSD"] = daily_rates
    for column in ("Open", "High", "Low", "Close"):
        converted[column] = converted[column] * daily_rates
    converted = converted.dropna(subset=["Close"])
    return converted, bool(daily_rates.notna().all())


def _statement_period_values(statement, keywords):
    """Find a relevant statement row and return its dated numeric values."""
    if not isinstance(statement, pd.DataFrame) or statement.empty:
        return []
    candidates = []
    for row_name in statement.index:
        label = str(row_name).lower()
        if all(word in label for word in keywords):
            candidates.append((label, row_name))
    if not candidates:
        return []
    _, row_name = min(candidates, key=lambda item: (len(item[0]), item[0]))
    values = []
    for column in statement.columns:
        period = pd.to_datetime(column, errors="coerce", utc=True)
        if pd.isna(period):
            continue
        value = pd.to_numeric(pd.Series([statement.at[row_name, column]]), errors="coerce").iloc[0]
        if pd.notna(value):
            values.append((period.tz_convert(None).normalize(), float(value)))
    return sorted(values, key=lambda item: item[0], reverse=True)


def _usd_amount(value, currency, value_date, fx_histories):
    """Convert one reported amount to USD using the rate as of its date."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return None
    rate = _fx_rate_as_of(currency, value_date, fx_histories)
    return float(value) * rate if rate is not None else None


def _comparison_snapshot(ticker1, ticker2, period):
    """Fetch all comparison inputs required to render and persist one snapshot."""
    financial_errors = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        info_one = executor.submit(company_info, ticker1)
        info_two = executor.submit(company_info, ticker2)
        financials_one = executor.submit(get_financials, ticker1)
        financials_two = executor.submit(get_financials, ticker2)
        prices = executor.submit(_load_history_pair, ticker1, ticker2, period)
        info1, info2 = info_one.result(), info_two.result()
        financials = {}
        for ticker, future in (
            (ticker1, financials_one),
            (ticker2, financials_two),
        ):
            try:
                financials[ticker] = future.result()
            except Exception as error:
                financials[ticker] = {}
                financial_errors[ticker] = str(error)
        histories = prices.result()

    currencies = set()
    for info in (info1, info2):
        for field in ("currency", "financialCurrency"):
            code, _ = _currency_code(info.get(field))
            if code != "USD":
                currencies.add(code)

    fx_histories = {}
    fx_errors = {}
    for code in sorted(currencies):
        try:
            rates = currency_history(code)
            fx_histories[code] = rates
            if rates.empty:
                fx_errors[code] = "No historical USD exchange rates were returned."
        except Exception as error:
            fx_histories[code] = pd.DataFrame(columns=["Close"])
            fx_errors[code] = str(error)

    return {
        "version": 1,
        "tickers": [ticker1, ticker2],
        "period": period,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "profiles": {ticker1: info1, ticker2: info2},
        "financials": financials,
        "price_history": histories,
        "fx_history": fx_histories,
        "fx_errors": fx_errors,
        "financial_errors": financial_errors,
    }


def _stock_chart(history, currency="USD"):
    """Render a price-and-volume chart with OHLCV hover details."""
    dates = history.index
    close = history["Close"]
    # Each company uses one consistent price-series color.
    line_color = "#15bf91"
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=dates, y=history["Volume"], name="Volume",
        marker_color="rgba(145,163,180,0.45)",
        hoverinfo="skip", showlegend=False,
    ), secondary_y=True)
    fig.add_trace(go.Scatter(
        x=dates, y=close, name="Close", mode="lines",
        line=dict(color=line_color, width=2.5),
        fill="tozeroy", fillcolor="rgba(21,191,145,0.14)",
        customdata=history[["Open", "High", "Low", "Volume"]].to_numpy(),
        hovertemplate=(
            "<b>%{x|%d %b %Y}</b><br>"
            f"Close: {currency} %{{y:,.2f}}<br>"
            f"Open: {currency} %{{customdata[0]:,.2f}}<br>"
            f"High: {currency} %{{customdata[1]:,.2f}}<br>"
            f"Low: {currency} %{{customdata[2]:,.2f}}<br>"
            "Volume: %{customdata[3]:,.0f}<extra></extra>"
        ),
        showlegend=False,
    ), secondary_y=False)
    # Tighten price axis so the movements remain readable; area fills from bottom axis.
    low = float(close.min())
    high = float(close.max())
    spread = max(high - low, high * .015, .01)
    fig.update_yaxes(range=[max(0, low - spread * .24), high + spread * .17],
                     tickformat=",.2f", showgrid=True, gridcolor="rgba(153,174,197,0.16)",
                     zeroline=False, side="right", secondary_y=False)
    fig.update_yaxes(range=[0, max(float(history["Volume"].max()) * 3.9, 1)],
                     visible=False, showgrid=False, secondary_y=True)
    fig.update_xaxes(showgrid=False, rangeslider_visible=False, tickfont=dict(color="#99a9bd"))
    fig.update_layout(
        height=285, margin=dict(l=8, r=20, t=16, b=12),
        plot_bgcolor="#101923", paper_bgcolor="#101923",
        font=dict(color="#dce5ef", size=12),
        hovermode="x", hoverlabel=dict(bgcolor="#17232e", font_color="#f0f4f8"),
        bargap=.18, dragmode="pan",
    )
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": False})


def _company_logo(ticker, info=None):
    """Use local logo, known brand icon, or company website favicon.

    The initials badge remains visible if the remote image cannot load.
    """
    import base64
    from urllib.parse import urlparse, quote

    safe_ticker = escape(ticker)
    fallback = f'<span class="nimbus-mark nimbus-logo-fallback">{escape(ticker[:2])}</span>'
    local = LOGO_DIR / f"{ticker}.png"
    if local.is_file():
        encoded = base64.b64encode(local.read_bytes()).decode("ascii")
        url = f"data:image/png;base64,{encoded}"
    elif ticker in LOGO_URLS:
        url = LOGO_URLS[ticker]
    else:
        website = str((info or {}).get("website") or "").strip()
        hostname = urlparse(website if "://" in website else "https://" + website).hostname
        if not hostname or "." not in hostname:
            return fallback
        # Domain-based favicons work for many companies, but aren't guaranteed
        # to be their official corporate logo.
        url = "https://www.google.com/s2/favicons?domain=" + quote(hostname, safe="") + "&sz=128"

    # The fallback is shown automatically if the image fails to load.
    return (f'<span class="nimbus-logo-wrap">'
            f'<img class="nimbus-logo" src="{escape(url, quote=True)}" '
            f'alt="{safe_ticker} logo" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
            f'<span class="nimbus-mark nimbus-logo-fallback" style="display:none">{escape(ticker[:2])}</span>'
            f'</span>')


def _profile(
    ticker,
    info,
    period,
    cached_history=None,
    history_cache_only=False,
    chart_currency=None,
):
    """Render one company's identity, key metrics, and selected price history."""
    name = escape(str(info.get("shortName") or info.get("longName") or ticker))
    currency = str(info.get("currency") or "USD")
    financial_currency = str(info.get("financialCurrency") or currency)
    with st.container(border=True):
        st.markdown(f'<div class="nimbus-company">{_company_logo(ticker, info)}<div><div class="nimbus-name">{name}</div><div class="nimbus-symbol">{escape(ticker)} · {escape(str(info.get("exchange") or "Listed company"))}</div></div></div>', unsafe_allow_html=True)
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        previous = info.get("previousClose") or info.get("regularMarketPreviousClose")
        change = ((price / previous) - 1) * 100 if isinstance(price, (int, float)) and isinstance(previous, (int, float)) and previous else None
        st.metric("Reported stock price", _number(price, prefix=f"{currency} "), _number(change, suffix="%") if change is not None else None)
        if cached_history is not None:
            history = cached_history
        elif history_cache_only:
            history = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        else:
            history = company_history(ticker, period)
            history_cache = st.session_state.setdefault("nimbus_comparison_history_cache", {})
            history_cache[(ticker, period)] = history
        if history.empty:
            st.info("Historical prices unavailable for this ticker.")
        else:
            _stock_chart(history, chart_currency or currency)
        a, b = st.columns(2)
        with a:
            st.metric("Market cap", _big(info.get("marketCap"), financial_currency))
            st.metric("Revenue", _big(info.get("totalRevenue"), financial_currency))
        with b:
            st.metric("P/E ratio", _number(info.get("trailingPE")))
            st.metric("EPS (TTM)", _number(info.get("trailingEps"), prefix=f"{financial_currency} "))


def _dividend_yield(info):
    """Yahoo Finance dividendYield is generally already expressed in percent points.

    trailingAnnualDividendYield is normally a decimal fraction, so normalize it.
    """
    value = info.get("dividendYield")
    if isinstance(value, (int, float)) and math.isfinite(value):
        return _number(value, suffix="%")
    trailing = info.get("trailingAnnualDividendYield")
    return _percent(trailing)


def _statement_comparison_metrics(info, financials, history, fx_histories, retrieved_at):
    """Build dated USD amounts and growth rates from the latest annual statements."""
    statement_currency = info.get("financialCurrency") or info.get("currency") or "USD"
    income = (financials or {}).get("Income Statement")
    revenue_values = _statement_period_values(income, ("revenue",))
    income_values = _statement_period_values(income, ("net", "income"))
    retrieved_date = pd.to_datetime(retrieved_at, errors="coerce", utc=True)
    if pd.isna(retrieved_date):
        retrieved_date = pd.Timestamp.now(tz="UTC")

    def amount_and_growth(values):
        if not values:
            return None, None, None, None
        latest_date, latest_value = values[0]
        usd_value = _usd_amount(
            latest_value,
            statement_currency,
            latest_date,
            fx_histories,
        )
        growth = None
        if len(values) > 1:
            previous_date, previous_value = values[1]
            previous_usd_value = _usd_amount(
                previous_value,
                statement_currency,
                previous_date,
                fx_histories,
            )
            if (
                usd_value is not None
                and previous_usd_value not in (None, 0)
            ):
                growth = (usd_value / previous_usd_value - 1) * 100
        return usd_value, growth, latest_date, latest_value

    revenue_usd, revenue_growth, revenue_date, _ = amount_and_growth(revenue_values)
    income_usd, income_growth, income_date, _ = amount_and_growth(income_values)

    market_cap_currency = info.get("financialCurrency") or info.get("currency") or "USD"
    market_cap_usd = _usd_amount(
        info.get("marketCap"),
        market_cap_currency,
        retrieved_date,
        fx_histories,
    )
    close_usd = None
    price_date = None
    price_currency = market_cap_currency
    if isinstance(history, pd.DataFrame) and not history.empty:
        price_date = history.index[-1]
        rate = _fx_rate_as_of(price_currency, price_date, fx_histories)
        if rate is not None:
            close = pd.to_numeric(history["Close"], errors="coerce").iloc[-1]
            if pd.notna(close):
                close_usd = float(close) * rate

    return {
        "stock_price_usd": close_usd,
        "stock_price_date": price_date,
        "market_cap_usd": market_cap_usd,
        "revenue_usd": revenue_usd,
        "revenue_growth_pct": revenue_growth,
        "revenue_period": revenue_date,
        "net_income_usd": income_usd,
        "net_income_growth_pct": income_growth,
        "net_income_period": income_date,
    }


def _comparison(
    t1,
    i1,
    t2,
    i2,
    financials=None,
    histories=None,
    fx_histories=None,
    retrieved_at=None,
):
    """Render scale-independent ratios and dated USD comparison amounts."""
    financials = financials or {}
    histories = histories or {}
    fx_histories = fx_histories or {}
    retrieved_at = retrieved_at or datetime.now(timezone.utc).isoformat()
    metrics = {
        ticker: _statement_comparison_metrics(
            info,
            financials.get(ticker),
            histories.get(ticker),
            fx_histories,
            retrieved_at,
        )
        for ticker, info in ((t1, i1), (t2, i2))
    }

    def formatted(value, suffix=""):
        return _number(value, suffix=suffix)

    def period_date(value):
        return value.strftime("%Y-%m-%d") if isinstance(value, pd.Timestamp) else "N/A"

    rows = [
        ("Latest close (USD; trading-date FX)", "stock_price_usd", lambda x: _big(x, "USD")),
        ("Market capitalization (USD; retrieval-date FX)", "market_cap_usd", lambda x: _big(x, "USD")),
        ("Latest annual revenue (USD; period-end FX)", "revenue_usd", lambda x: _big(x, "USD")),
        ("Revenue period ending", "revenue_period", period_date),
        ("Revenue growth (latest annual period)", "revenue_growth_pct", lambda x: formatted(x, "%")),
        ("Latest annual net income (USD; period-end FX)", "net_income_usd", lambda x: _big(x, "USD")),
        ("Net income period ending", "net_income_period", period_date),
        ("Net income growth (latest annual period)", "net_income_growth_pct", lambda x: formatted(x, "%")),
        ("P/E ratio", "trailingPE", lambda x: _number(x)),
        ("Gross margin", "grossMargins", _percent),
        ("Operating margin", "operatingMargins", _percent),
        ("Profit margin", "profitMargins", _percent),
        ("Return on equity", "returnOnEquity", _percent),
        ("Dividend yield", "dividendYield", _percent),
    ]
    result = []
    for label, key, format_fn in rows:
        if key in {"stock_price_usd", "market_cap_usd", "revenue_usd",
                   "revenue_period", "revenue_growth_pct", "net_income_usd",
                   "net_income_period", "net_income_growth_pct"}:
            first = metrics[t1].get(key)
            second = metrics[t2].get(key)
        elif key == "dividendYield":
            first = _dividend_yield(i1)
            second = _dividend_yield(i2)
            result.append({"Metric": label, t1: first, t2: second})
            continue
        else:
            first = i1.get(key)
            second = i2.get(key)
        result.append({
            "Metric": label,
            t1: format_fn(first),
            t2: format_fn(second),
        })

    st.dataframe(
        pd.DataFrame(result),
        hide_index=True,
        width="stretch",
        height=480,
        column_config={
            "Metric": st.column_config.TextColumn("Metric", width="medium"),
            t1: st.column_config.TextColumn(t1, width="medium"),
            t2: st.column_config.TextColumn(t2, width="medium"),
        },
    )
    st.caption(
        "Statement growth compares the latest two reported annual periods "
        "after converting both periods to USD. Reported amounts use the "
        "latest available exchange rate on or before each reporting date."
    )


def _render_comparison_dashboard(
    t1,
    i1,
    t2,
    i2,
    period,
    histories=None,
    history_cache_only=False,
    financials=None,
    fx_histories=None,
    fx_errors=None,
    financial_errors=None,
    retrieved_at=None,
):
    """Render company profiles and comparable metrics from one data snapshot."""
    histories = histories or {}
    financials = financials or {}
    fx_histories = fx_histories or {}
    converted_histories = {}
    conversion_incomplete = []
    for ticker, info in ((t1, i1), (t2, i2)):
        history = histories.get(ticker)
        currency = info.get("currency") or "USD"
        converted, complete = _to_usd_history(
            history,
            currency,
            fx_histories,
        )
        converted_histories[ticker] = converted
        if not complete:
            code, _ = _currency_code(currency)
            conversion_incomplete.append(f"{ticker} ({code})")

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        _profile(
            t1,
            i1,
            period,
            converted_histories.get(t1),
            history_cache_only,
            chart_currency="USD",
        )
    with c2:
        _profile(
            t2,
            i2,
            period,
            converted_histories.get(t2),
            history_cache_only,
            chart_currency="USD",
        )

    st.markdown('<div class="nimbus-section">Key metrics comparison</div>', unsafe_allow_html=True)
    _comparison(
        t1,
        i1,
        t2,
        i2,
        financials=financials,
        histories=histories,
        fx_histories=fx_histories,
        retrieved_at=retrieved_at,
    )
    for code, error in (fx_errors or {}).items():
        st.warning(f"Could not load {code}/USD exchange rates: {error}")
    if conversion_incomplete:
        st.warning(
            "Some historical prices could not be fully converted to USD; "
            "check the saved FX rates for "
            + ", ".join(conversion_incomplete)
            + "."
        )
    for ticker, error in (financial_errors or {}).items():
        st.warning(f"Could not load financial statements for {ticker}: {error}")


def get_cached_comparison(ticker1: str, ticker2: str):
    """Return this user's comparison snapshot for an exact ticker pair."""
    snapshot = st.session_state.get("nimbus_comparison_snapshot")
    if (
        snapshot
        and snapshot.get("tickers")
        == [ticker1.strip().upper(), ticker2.strip().upper()]
        and st.session_state.get("nimbus_comparison_user_id")
        == st.session_state.get("current_user_id")
    ):
        return snapshot

    # Keep compatibility with comparison records created before snapshots.
    data = st.session_state.get("nimbus_comparison_results")
    if not data or data[0] != ticker1.strip().upper() or data[2] != ticker2.strip().upper():
        return None

    period_labels = {"1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y", "5Y": "5y", "ALL": "max"}
    label = st.session_state.get("nimbus_history_period", "1Y")
    period = period_labels.get(label, "1y")
    history_cache = st.session_state.get("nimbus_comparison_history_cache", {})
    return {
        "data": data,
        "period": period,
        "histories": {
            ticker: history_cache.get((ticker, period))
            for ticker in (ticker1.strip().upper(), ticker2.strip().upper())
        },
        "retrieved_at": st.session_state.get("nimbus_comparison_retrieved_at"),
    }


def show_cached_comparison(cached_comparison) -> None:
    """Render a persisted snapshot or a legacy in-session comparison."""
    if not cached_comparison:
        st.info("A saved data snapshot is not available for this comparison.")
        return

    st.markdown(CSS, unsafe_allow_html=True)
    if cached_comparison.get("version") == 1:
        tickers = cached_comparison["tickers"]
        profiles = cached_comparison["profiles"]
        retrieved_at = cached_comparison.get("retrieved_at")
        if retrieved_at:
            st.caption(f"Saved data retrieved: {retrieved_at}")
        period = cached_comparison.get("period", "1y")
        st.caption(
            f"Saved price-history range: {period}. "
            "Reported values and FX rates reflect the snapshot time."
        )
        _render_comparison_dashboard(
            tickers[0],
            profiles.get(tickers[0], {}),
            tickers[1],
            profiles.get(tickers[1], {}),
            period,
            histories=cached_comparison.get("price_history") or {},
            history_cache_only=True,
            financials=cached_comparison.get("financials") or {},
            fx_histories=cached_comparison.get("fx_history") or {},
            fx_errors=cached_comparison.get("fx_errors") or {},
            financial_errors=cached_comparison.get("financial_errors") or {},
            retrieved_at=retrieved_at,
        )
        return

    t1, i1, t2, i2 = cached_comparison["data"]
    retrieved_at = cached_comparison.get("retrieved_at")
    if retrieved_at:
        st.caption(f"Cached data retrieved: {retrieved_at}")
    else:
        st.caption("Cached comparison data; retrieval time unavailable.")

    _render_comparison_dashboard(
        t1,
        i1,
        t2,
        i2,
        cached_comparison["period"],
        histories=cached_comparison.get("histories") or {},
        history_cache_only=True,
        retrieved_at=retrieved_at,
    )


def _remember_history_for_notes(history_id):
    """Keep Recent History / Notes state compatible with current main."""
    st.session_state["current_history_id"] = history_id
    st.session_state["notes_history_editor_open"] = False
    st.session_state["notes_pending_context"] = None
    st.session_state["notes_active_id"] = None
    st.session_state["notes_draft"] = False


def _run_comparison(ticker1, ticker2, period):
    """Fetch, cache, and persist the selected-period comparison snapshot."""
    with st.spinner("Fetching company, financial statement, price, and FX data..."):
        try:
            snapshot = _comparison_snapshot(ticker1, ticker2, period)
        except Exception as error:
            st.error(f"Could not retrieve comparison data: {error}")
            return False

    st.session_state["nimbus_comparison_snapshot"] = snapshot
    st.session_state["nimbus_comparison_results"] = (
        ticker1,
        snapshot["profiles"][ticker1],
        ticker2,
        snapshot["profiles"][ticker2],
    )
    st.session_state["nimbus_comparison_retrieved_at"] = snapshot["retrieved_at"]
    st.session_state["nimbus_comparison_history_id"] = None
    st.session_state["nimbus_comparison_user_id"] = None
    user_id = st.session_state["current_user_id"]
    try:
        search_id = record_search(
            "comparison",
            ticker1,
            ticker2,
            primary_name=(
                snapshot["profiles"][ticker1].get("shortName")
                or snapshot["profiles"][ticker1].get("longName")
                or ticker1
            ),
            secondary_name=(
                snapshot["profiles"][ticker2].get("shortName")
                or snapshot["profiles"][ticker2].get("longName")
                or ticker2
            ),
            user_id=user_id,
            analysis_type="comparison",
            result={"comparison_snapshot": snapshot},
        )
    except Exception as error:
        st.error("Comparison loaded, but the complete snapshot could not be saved.")
        st.caption(f"Details: {error}")
    else:
        st.session_state["nimbus_comparison_history_id"] = search_id
        st.session_state["nimbus_comparison_user_id"] = user_id
        _remember_history_for_notes(search_id)
    return True


def show_company_comparison(ticker1: Optional[str] = None, ticker2: Optional[str] = None):
    """Validate comparison inputs, fetch company data, persist history, and render results."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="nimbus-kicker">NIMBUS / FINANCIAL INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="nimbus-title">Company <span>Comparison</span></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="nimbus-muted">Compare companies with price histories, '
        'USD-normalized financials, growth rates, and ratios.</div>',
        unsafe_allow_html=True,
    )

    period_labels = {
        "1M": "1mo",
        "3M": "3mo",
        "6M": "6mo",
        "1Y": "1y",
        "5Y": "5y",
        "ALL": "max",
    }
    with st.form("nimbus_comparison_inputs"):
        left, right, period_column, action = st.columns(
            [2.0, 2.0, 1.2, 1.2],
            vertical_alignment="bottom",
        )
        with left:
            ticker1_value = st.text_input("First company ticker", value=(ticker1 or "AAPL").upper(), key="nimbus_ticker1").strip().upper()
        with right:
            ticker2_value = st.text_input("Second company ticker", value=(ticker2 or "MSFT").upper(), key="nimbus_ticker2").strip().upper()
        with period_column:
            selected_period_label = st.selectbox(
                "Price history to save",
                list(period_labels),
                index=3,
                key="nimbus_comparison_snapshot_period",
            )
        with action:
            submitted = st.form_submit_button("Compare →", type="primary", width="stretch")

    if submitted:
        ticker1_value = ticker1_value.strip().upper()
        ticker2_value = ticker2_value.strip().upper()
        if not ticker1_value or not ticker2_value:
            st.warning("Enter two stock tickers.")
            return
        if ticker1_value == ticker2_value:
            st.warning("Choose two different tickers.")
            return
        if not _run_comparison(
            ticker1_value,
            ticker2_value,
            period_labels[selected_period_label],
        ):
            return

    data = st.session_state.get("nimbus_comparison_results")
    if data is None:
        if ticker1 and ticker2:
            ticker1 = ticker1.strip().upper()
            ticker2 = ticker2.strip().upper()
            if ticker1 == ticker2:
                st.warning("Choose two different tickers.")
                return
            selected_label = st.session_state.get(
                "nimbus_comparison_snapshot_period",
                "1Y",
            )
            if not _run_comparison(
                ticker1,
                ticker2,
                period_labels.get(selected_label, "1y"),
            ):
                return
            data = st.session_state["nimbus_comparison_results"]

    if data is None:
        st.info("Enter two tickers and select Compare to load the dashboard.")
        return

    snapshot = st.session_state.get("nimbus_comparison_snapshot")
    if snapshot and snapshot.get("tickers") == [data[0], data[2]]:
        show_cached_comparison(snapshot)
    else:
        t1, i1, t2, i2 = data
        st.info(
            "This comparison is from an older session and has no saved data "
            "snapshot. Submit the comparison again to save its metrics and "
            "price history."
        )
        _render_comparison_dashboard(t1, i1, t2, i2, "1y")

    st.caption(
        f"Source: Yahoo Finance (via yfinance). Viewed "
        f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. "
        "Data may be delayed, incomplete, or cached for up to 15 minutes. "
        "Not investment advice."
    )


if __name__ == "__main__":
    st.set_page_config(page_title="Nimbus | Company Comparison", layout="wide")
    show_company_comparison()
