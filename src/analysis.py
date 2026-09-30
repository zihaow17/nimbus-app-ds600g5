"""Reusable financial-data functions based on the project notebooks."""

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
    return pd.DataFrame(articles, columns=["Title", "Description"])


def get_price(ticker):
    """Return the latest price reported by Yahoo Finance, if available."""
    return yf.Ticker(ticker).info.get("currentPrice")


def get_analyst_ratings(ticker):
    """Return the ten most recent analyst recommendation rows."""
    recommendations = yf.Ticker(ticker).recommendations
    if recommendations is None:
        return pd.DataFrame()
    return recommendations.tail(10)