"""Nimbus two-company comparison page. Run through src/app.py or this file directly."""
from datetime import datetime, timezone
from html import escape
import math

import pandas as pd
import streamlit as st
import yfinance as yf


CSS = """
<style>
.nimbus-title {font-size:2.65rem;font-weight:800;letter-spacing:-.045em;line-height:1.15;margin:.4rem 0;}
.nimbus-title span {background:linear-gradient(95deg,#45b8ff,#8576ff);color:transparent;background-clip:text;-webkit-background-clip:text;}
.nimbus-muted {color:#9daec3;font-size:.92rem;margin:0 0 1.2rem;}
.nimbus-kicker {font-size:.75rem;color:#7a9ccc;letter-spacing:.16em;font-weight:700;}
.nimbus-company {display:flex;gap:13px;align-items:center;margin-bottom:10px;}
.nimbus-mark {width:47px;height:47px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:1.05rem;background:linear-gradient(135deg,#223c64,#225da3);border:1px solid #405a79;}
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


@st.cache_data(ttl=900, show_spinner=False)
def company_news(ticker):
    raw = yf.Ticker(ticker).news or []
    items = []
    for article in raw[:5]:
        c = article.get("content") or {}
        title = c.get("title") or article.get("title")
        provider = (c.get("provider") or {}).get("displayName") if isinstance(c.get("provider"), dict) else article.get("publisher")
        link = (c.get("canonicalUrl") or {}).get("url") if isinstance(c.get("canonicalUrl"), dict) else article.get("link")
        if title:
            items.append((str(title), str(provider or "News"), link))
    return items


@st.cache_data(ttl=900, show_spinner=False)
def company_statements(ticker):
    stock = yf.Ticker(ticker)
    return {"Income statement": stock.income_stmt, "Balance sheet": stock.balance_sheet, "Cash flow": stock.cashflow}


def _profile(ticker, info, period):
    name = escape(str(info.get("shortName") or info.get("longName") or ticker))
    currency = str(info.get("currency") or "USD")
    mark = escape(ticker[:2])
    with st.container(border=True):
        st.markdown(f'<div class="nimbus-company"><div class="nimbus-mark">{mark}</div><div><div class="nimbus-name">{name}</div><div class="nimbus-symbol">{escape(ticker)} · {escape(str(info.get("exchange") or "Listed company"))}</div></div></div>', unsafe_allow_html=True)
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
        ("Dividend yield", "dividendYield", lambda v, c: _percent(v)),
    ]
    result = []
    for label, key, format_fn in rows:
        result.append({"Metric": label, t1: format_fn(i1.get(key), c1), t2: format_fn(i2.get(key), c2)})
    st.dataframe(pd.DataFrame(result), hide_index=True, use_container_width=True, height=425)
    if c1 != c2:
        st.warning(f"Currencies differ ({c1} versus {c2}); values are not FX-converted.")


def _analysts(ticker, info):
    score = info.get("recommendationMean")
    label = info.get("recommendationKey")
    analyst_count = info.get("numberOfAnalystOpinions")
    with st.container(border=True):
        st.markdown('<div class="nimbus-section">Analyst ratings</div>', unsafe_allow_html=True)
        st.caption(f"{ticker} · Yahoo Finance analyst consensus")
        if label:
            st.metric("Recommendation", str(label).replace("_", " ").title())
        else:
            st.info("Analyst recommendation is unavailable.")
        c1, c2 = st.columns(2)
        c1.metric("Consensus score", _number(score))
        c2.metric("Analyst opinions", str(analyst_count) if analyst_count is not None else "N/A")
        st.caption("Yahoo recommendation scores typically range from 1 (strong buy) to 5 (sell). Availability varies.")


def _statement_panel(ticker):
    with st.container(border=True):
        st.markdown('<div class="nimbus-section">Financial statements</div>', unsafe_allow_html=True)
        with st.spinner("Loading financial statements..."):
            try:
                statements = company_statements(ticker)
            except Exception as exc:
                st.info(f"Statements unavailable: {exc}")
                return
        tab1, tab2, tab3 = st.tabs(list(statements))
        for tab, data in zip((tab1, tab2, tab3), statements.values()):
            with tab:
                if data is None or data.empty:
                    st.info("No financial statement data available.")
                else:
                    table = data.head(8).copy()
                    table.columns = [str(x.date()) if hasattr(x, "date") else str(x) for x in table.columns]
                    st.dataframe(table, use_container_width=True)
                    st.caption("As reported by Yahoo Finance; units follow the source statement.")


def _news_panel(ticker):
    with st.container(border=True):
        st.markdown('<div class="nimbus-section">Recent news</div>', unsafe_allow_html=True)
        try:
            stories = company_news(ticker)
            if not stories:
                st.info("No recent news found.")
            for title, provider, url in stories:
                st.markdown(f"**{escape(title)}**")
                st.caption(provider)
                if isinstance(url, str) and url.startswith(("https://", "http://")):
                    st.link_button("Read article ↗", url)
                st.divider()
        except Exception as exc:
            st.info(f"News unavailable: {exc}")


def show_company_comparison():
    """Render the complete Nimbus comparison interface."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="nimbus-kicker">NIMBUS / FINANCIAL INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="nimbus-title">Company <span>Comparison</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="nimbus-muted">Compare companies side by side with price histories, financial ratios, statements and recent news.</div>', unsafe_allow_html=True)

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
    c1, c2, c3 = st.columns([1.25, 1.25, 1.1], gap="medium")
    with c1:
        _profile(t1, i1, period or "1y")
    with c2:
        _profile(t2, i2, period or "1y")
    with c3:
        with st.container(border=True):
            st.markdown('<div class="nimbus-section">Key metrics comparison</div>', unsafe_allow_html=True)
            _comparison(t1, i1, t2, i2)

    lower1, lower2, lower3 = st.columns([1, 1.35, 1], gap="medium")
    with lower1:
        analyst_ticker = st.selectbox("Analyst data for", [t1, t2], key="nimbus_analyst_choice")
        _analysts(analyst_ticker, i1 if analyst_ticker == t1 else i2)
    with lower2:
        statement_ticker = st.selectbox("Statements for", [t1, t2], key="nimbus_statement_choice")
        _statement_panel(statement_ticker)
    with lower3:
        news_ticker = st.selectbox("News for", [t1, t2], key="nimbus_news_choice")
        _news_panel(news_ticker)

    st.caption(f"Source: Yahoo Finance (via yfinance). Viewed {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Data may be delayed, incomplete, or cached for up to 15 minutes. Not investment advice.")


if __name__ == "__main__":
    st.set_page_config(page_title="Nimbus | Company Comparison", layout="wide")
    show_company_comparison()
