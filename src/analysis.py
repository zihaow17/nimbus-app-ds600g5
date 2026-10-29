"""Reusable financial-data functions for Nimbus."""

from numbers import Number

import pandas as pd
import yfinance as yf


def get_financials(ticker):
    """Return recent income statement, balance sheet, and cash flow data."""
    stock = yf.Ticker(ticker)
    return {
        "Income Statement": stock.financials.head(),
        "Balance Sheet": stock.balance_sheet.head(),
        "Cash Flow": stock.cashflow.head(),
    }


def get_news(ticker):
    """Return up to five recent news articles for a ticker."""
    articles = []

    for article in (yf.Ticker(ticker).news or [])[:5]:
        content = article.get("content") or {}
        title = content.get("title") or "No title"
        description = content.get("description") or "No description"

        articles.append(
            {
                "Title": title,
                "Description": str(description)[:200],
            }
        )

    return pd.DataFrame(
        articles,
        columns=["Title", "Description"],
    )


def get_price(ticker):
    """Return the latest price reported by Yahoo Finance."""
    return yf.Ticker(ticker).info.get("currentPrice")


def get_analyst_ratings(ticker):
    """Return the ten most recent analyst recommendation rows."""
    recommendations = yf.Ticker(ticker).recommendations

    if recommendations is None:
        return pd.DataFrame()

    return recommendations.tail(10)


# ============================================================
# FINANCIAL REPORTING CURRENCY
# ============================================================

def get_financial_currency(ticker):
    """Get the reporting currency for financial statements."""
    try:
        info = yf.Ticker(ticker).info or {}
        return info.get("financialCurrency")
    except Exception:
        return None


# ============================================================
# STANDARDISED NUMBER FORMATTING
# ============================================================

def format_compact_number(value, decimals=2):
    """Format a number using B, M, or K."""

    if pd.isna(value):
        return "N/A"

    number = float(value)
    absolute = abs(number)

    if absolute >= 1_000_000_000:
        return f"{number / 1_000_000_000:,.{decimals}f}B"

    if absolute >= 1_000_000:
        return f"{number / 1_000_000:,.{decimals}f}M"

    if absolute >= 1_000:
        return f"{number / 1_000:,.{decimals}f}K"

    return f"{number:,.{decimals}f}"


def format_financial_statement(df, currency=None):
    """
    Format financial statement values for display.

    Monetary values: B, M, K
    Percentages: 15.60%
    Ratios: 32.50x
    Per-share values: USD 6.42
    Share counts: 14.77B shares
    Missing values: N/A

    Original financial data remains unchanged.
    """

    if df is None or df.empty:
        return df

    formatted = pd.DataFrame(
        index=df.index,
        columns=df.columns,
        dtype=object,
    )

    currency_label = f"{currency} " if currency else ""

    def format_value(value, row_name):
        if pd.isna(value):
            return "N/A"

        if not isinstance(value, Number):
            return str(value)

        number = float(value)
        name = str(row_name).lower().strip()

        # Percentages and rates
        percentage_keywords = (
            "tax rate",
            "margin",
            "percentage",
            "percent",
            "effective tax rate",
        )

        if any(word in name for word in percentage_keywords):
            return f"{number * 100:,.2f}%"

        # EPS and other per-share figures
        if "eps" in name or "per share" in name:
            sign = "-" if number < 0 else ""
            return f"{sign}{currency_label}{abs(number):,.2f}"

        # Share counts
        share_keywords = (
            "shares",
            "share issued",
            "share count",
            "treasury share",
            "share outstanding",
        )

        if any(word in name for word in share_keywords):
            return f"{format_compact_number(number)} shares"

        # Non-monetary ratios
        ratio_keywords = (
            "ratio",
            "multiple",
        )

        if any(word in name for word in ratio_keywords):
            return f"{number:,.2f}x"

        # Monetary values
        sign = "-" if number < 0 else ""

        return (
            f"{sign}{currency_label}"
            f"{format_compact_number(abs(number))}"
        )

    for row_name in df.index:
        for column in df.columns:
            formatted.at[row_name, column] = format_value(
                df.at[row_name, column],
                row_name,
            )

    # Clean financial-year headings
    formatted.columns = [
        f"FY{column.year}"
        if isinstance(column, pd.Timestamp)
        else str(column)
        for column in formatted.columns
    ]

    return formatted
