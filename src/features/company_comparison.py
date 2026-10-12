"""Nimbus two-company comparison page. Run through src/app.py or this file directly."""
from datetime import datetime, timezone
from pathlib import Path
from html import escape
import math

import pandas as pd
import streamlit as st
import yfinance as yf


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

CSS = """
<style>
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
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return "N/A"
    return f"{prefix}{value:,.{decimals}f}{suffix}"


def _big(value, currency="USD"):
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
    return _number(value * 100, suffix="%") if isinstance(value, (int, float)) else "N/A"


@st.cache_data(ttl=900, show_spinner=False)
def company_info(ticker):
    info = yf.Ticker(ticker).info or {}
    if not info or not (info.get("symbol") or info.get("shortName")):
        raise ValueError(f"No Yahoo Finance information found for {ticker}.")
    return info


@st.cache_data(ttl=900, show_spinner=False)
def company_history(ticker, period):
    result = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    return result[["Close"]].dropna() if isinstance(result, pd.DataFrame) and "Close" in result else pd.DataFrame()


def _company_logo(ticker):
    """Return a small company logo, with initials if no logo is available."""
    local = LOGO_DIR / f"{ticker}.png"
    if local.is_file():
        import base64
        encoded = base64.b64encode(local.read_bytes()).decode("ascii")
        return f'<img class="nimbus-logo" src="data:image/png;base64,{encoded}" alt="{escape(ticker)} logo">'
    if ticker in LOGO_URLS:
        return (f'<img class="nimbus-logo" src="{LOGO_URLS[ticker]}" '
                f'alt="{escape(ticker)} logo">')
    return f'<div class="nimbus-mark">{escape(ticker[:2])}</div>'


def _profile(ticker, info, period):
    name = escape(str(info.get("shortName") or info.get("longName") or ticker))
    currency = str(info.get("currency") or "USD")
    with st.container(border=True):
        st.markdown(f'<div class="nimbus-company">{_company_logo(ticker)}<div><div class="nimbus-name">{name}</div><div class="nimbus-symbol">{escape(ticker)} · {escape(str(info.get("exchange") or "Listed company"))}</div></div></div>', unsafe_allow_html=True)
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        previous = info.get("previousClose") or info.get("regularMarketPreviousClose")
        change = ((price / previous) - 1) * 100 if isinstance(price, (int, float)) and isinstance(previous, (int, float)) and previous else None
        st.metric("Reported stock price", _number(price, prefix=f"{currency} "), _number(change, suffix="%") if change is not None else None)
        history = company_history(ticker, period)
        if history.empty:
            st.info("Historical prices unavailable for this ticker.")
        else:
            st.line_chart(history, height=205, use_container_width=True)
        a, b = st.columns(2)
        with a:
            st.metric("Market cap", _big(info.get("marketCap"), currency))
            st.metric("Revenue", _big(info.get("totalRevenue"), currency))
        with b:
            st.metric("P/E ratio", _number(info.get("trailingPE")))
            st.metric("EPS (TTM)", _number(info.get("trailingEps"), prefix=f"{currency} "))


def _dividend_yield(info):
    """Yahoo Finance dividendYield is generally already expressed in percent points.

    trailingAnnualDividendYield is normally a decimal fraction, so normalize it.
    """
    value = info.get("dividendYield")
    if isinstance(value, (int, float)) and math.isfinite(value):
        return _number(value, suffix="%")
    trailing = info.get("trailingAnnualDividendYield")
    return _percent(trailing)


def _comparison(t1, i1, t2, i2):
    c1 = str(i1.get("currency") or "USD")
    c2 = str(i2.get("currency") or "USD")
    rows = [
        ("Stock price", "currentPrice", lambda v, c: _number(v, prefix=f"{c} ")),
        ("Market capitalization", "marketCap", _big),
        ("P/E ratio", "trailingPE", lambda v, c: _number(v)),
        ("Revenue", "totalRevenue", _big),
        ("Net income", "netIncomeToCommon", _big),
        ("EPS (TTM)", "trailingEps", lambda v, c: _number(v, prefix=f"{c} ")),
        ("Gross margin", "grossMargins", lambda v, c: _percent(v)),
        ("Operating margin", "operatingMargins", lambda v, c: _percent(v)),
        ("Profit margin", "profitMargins", lambda v, c: _percent(v)),
        ("Return on equity", "returnOnEquity", lambda v, c: _percent(v)),

    ]
    result = []
    for label, key, format_fn in rows:
        result.append({"Metric": label, t1: format_fn(i1.get(key), c1), t2: format_fn(i2.get(key), c2)})
    result.append({"Metric": "Dividend yield", t1: _dividend_yield(i1), t2: _dividend_yield(i2)})
    st.dataframe(
        pd.DataFrame(result),
        hide_index=True,
        use_container_width=True,
        height=460,
        column_config={
            "Metric": st.column_config.TextColumn("Metric", width="medium"),
            t1: st.column_config.TextColumn(t1, width="medium"),
            t2: st.column_config.TextColumn(t2, width="medium"),
        },
    )
    if c1 != c2:
        st.warning(f"Currencies differ ({c1} versus {c2}); values are not FX-converted.")


def show_company_comparison():
    """Render the complete Nimbus comparison interface."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="nimbus-kicker">NIMBUS / FINANCIAL INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="nimbus-title">Company <span>Comparison</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="nimbus-muted">Compare companies side by side with price histories and key financial metrics.</div>', unsafe_allow_html=True)

    with st.form("nimbus_comparison_inputs"):
        left, right, action = st.columns([2.2, 2.2, 1.2], vertical_alignment="bottom")
        with left:
            ticker1 = st.text_input("First company ticker", value="AAPL", key="nimbus_ticker1").strip().upper()
        with right:
            ticker2 = st.text_input("Second company ticker", value="MSFT", key="nimbus_ticker2").strip().upper()
        with action:
            submitted = st.form_submit_button("Compare →", type="primary", use_container_width=True)

    if submitted:
        if not ticker1 or not ticker2:
            st.warning("Enter two stock tickers.")
            return
        if ticker1 == ticker2:
            st.warning("Choose two different tickers.")
            return
        with st.spinner("Fetching data from Yahoo Finance..."):
            try:
                info1 = company_info(ticker1)
                info2 = company_info(ticker2)
            except Exception as exc:
                st.error(f"Could not retrieve company information: {exc}")
                return
        st.session_state["nimbus_comparison_results"] = (ticker1, info1, ticker2, info2)

    data = st.session_state.get("nimbus_comparison_results")
    if data is None:
        st.info("Enter two tickers and select Compare to load the dashboard.")
        return

    t1, i1, t2, i2 = data
    period = st.selectbox("Price history period", options=["1mo", "3mo", "6mo", "1y", "5y"], index=3, key="nimbus_history_period")
    # Two company cards sit side by side. The complete metrics table is BELOW them.
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        _profile(t1, i1, period or "1y")
    with c2:
        _profile(t2, i2, period or "1y")

    st.markdown('<div class="nimbus-section">Key metrics comparison</div>', unsafe_allow_html=True)
    _comparison(t1, i1, t2, i2)

    st.caption(f"Source: Yahoo Finance (via yfinance). Viewed {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Data may be delayed, incomplete, or cached for up to 15 minutes. Not investment advice.")


if __name__ == "__main__":
    st.set_page_config(page_title="Nimbus | Company Comparison", layout="wide")
    show_company_comparison()
