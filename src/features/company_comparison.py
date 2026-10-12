
"""Side-by-side comparison of two companies."""

from datetime import datetime, timezone

import pandas as pd
import streamlit as st
import yfinance as yf



def get_company_info(ticker):
    """Get company information from Yahoo Finance."""
    info = yf.Ticker(ticker).info

    if not info or not info.get("symbol"):
        raise ValueError(f"No financial data found for {ticker}")

    return info


def format_value(value, metric):
    """Format financial values for display."""
    if value is None or not isinstance(value, (int, float)):
        return "N/A"

    if metric in ["Market Capitalization", "Revenue"]:
        return f"${value / 1_000_000_000:,.2f}B"

    if metric in ["Profit Margin", "Return on Equity", "Dividend Yield"]:
        return f"{value * 100:.2f}%"

    if metric == "Stock Price":
        return f"${value:,.2f}"

    return f"{value:,.2f}"


def show_company_comparison():
    """Render the Company Comparison feature."""

    st.subheader("Company Comparison")
    st.write("Compare two publicly listed companies side by side.")

    with st.form("comparison_form"):
        col1, col2 = st.columns(2)

        with col1:
            ticker1 = st.text_input(
                "Company A",
                value="AAPL"
            ).strip().upper()

        with col2:
            ticker2 = st.text_input(
                "Company B",
                value="MSFT"
            ).strip().upper()

        compare = st.form_submit_button("Compare →")

    if not compare:
        return

    if not ticker1 or not ticker2:
        st.warning("Please enter both company tickers.")
        return

    if ticker1 == ticker2:
        st.warning("Please choose two different companies.")
        return

    try:
        with st.spinner("Retrieving financial data..."):
            company1 = get_company_info(ticker1)
            company2 = get_company_info(ticker2)

        name1 = company1.get("shortName") or ticker1
        name2 = company2.get("shortName") or ticker2

        metrics = {
            "Stock Price": "currentPrice",
            "Market Capitalization": "marketCap",
            "P/E Ratio": "trailingPE",
            "Revenue": "totalRevenue",
            "Profit Margin": "profitMargins",
            "Return on Equity": "returnOnEquity",
            "Dividend Yield": "dividendYield",
        }

        comparison = []

        for metric, field in metrics.items():
            comparison.append({
                "Metric": metric,
                ticker1: format_value(company1.get(field), metric),
                ticker2: format_value(company2.get(field), metric),
            })

        st.subheader(f"{name1} vs {name2}")

        df = pd.DataFrame(comparison)

        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True
        )

        st.caption("Source: Yahoo Finance")
        st.caption(
            "Retrieved: "
            + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            + " (data may be cached for 15 minutes)"
        )

    except Exception as error:
        st.error("Could not retrieve company information.")
        st.caption(str(error))
