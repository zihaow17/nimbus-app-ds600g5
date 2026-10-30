
"""Nimbus Financial Statements dashboard."""

import math
import re
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf


# ============================================================
# THEME
# ============================================================

BLUE = "#56A9FF"
GREEN = "#35C994"
YELLOW = "#FFD166"
RED = "#FF6475"

BACKGROUND = "#121820"
TEXT = "#EAF0F7"
MUTED = "#9AA9BB"
GRID = "#303B49"


# ============================================================
# NUMBER FORMATTING
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


def compact(value):
    """Format large numbers using T, B, M and K."""
    if not valid(value):
        return "N/A"

    value = float(value)

    for divisor, suffix in [
        (1e12, "T"),
        (1e9, "B"),
        (1e6, "M"),
        (1e3, "K"),
    ]:
        if abs(value) >= divisor:
            return f"{value / divisor:,.2f}{suffix}"

    return f"{value:,.2f}"


def metric_type(name):
    """Identify the correct unit of a financial metric."""
    label = str(name).lower().strip()

    if any(
        keyword in label
        for keyword in [
            "tax rate",
            "margin",
            "percentage",
            "percent",
        ]
    ):
        return "percent"

    if "eps" in label or "per share" in label:
        return "per_share"

    if (
        "shares" in label
        or "share issued" in label
        or "share count" in label
    ):
        return "shares"

    # Word boundary avoids mistaking "operation" for "ratio".
    if re.search(r"\bratio\b|\bmultiple\b", label):
        return "ratio"

    return "money"


def format_value(value, metric, currency="USD"):
    """Format one statement value for display."""
    if not valid(value):
        return "N/A"

    number = float(value)
    kind = metric_type(metric)

    if kind == "percent":
        return f"{number * 100:,.2f}%"

    if kind == "per_share":
        sign = "-" if number < 0 else ""
        return f"{sign}{currency} {abs(number):,.2f}"

    if kind == "shares":
        return f"{compact(number)} shares"

    if kind == "ratio":
        return f"{number:,.2f}x"

    sign = "-" if number < 0 else ""
    return f"{sign}{currency} {compact(abs(number))}"


def period_label(value, reporting_period):
    """Generate readable annual or quarterly date headings."""
    try:
        date = pd.Timestamp(value)

        if reporting_period == "Quarterly":
            return f"Q{date.quarter} {date.year}"

        return f"FY{date.year}"

    except (ValueError, TypeError):
        return str(value)


def calculate_change(current, previous):
    """Calculate the change between two financial values."""
    if not valid(current) or not valid(previous):
        return None

    current = float(current)
    previous = float(previous)

    if previous == 0:
        return None

    return (current - previous) / abs(previous) * 100


def calculate_rate_change(current, previous):
    """Calculate percentage-point changes for rates."""
    if not valid(current) or not valid(previous):
        return None

    return (
        float(current) - float(previous)
    ) * 100


# ============================================================
# FINANCIAL DATA
# ============================================================

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_statements(ticker, reporting_period):
    """Fetch financial statements from Yahoo Finance."""

    stock = yf.Ticker(ticker)

    if reporting_period == "Quarterly":
        attributes = {
            "Income Statement": "quarterly_financials",
            "Balance Sheet": "quarterly_balance_sheet",
            "Cash Flow": "quarterly_cashflow",
        }

    else:
        attributes = {
            "Income Statement": "financials",
            "Balance Sheet": "balance_sheet",
            "Cash Flow": "cashflow",
        }

    statements = {}

    for section, attribute in attributes.items():
        try:
            data = getattr(stock, attribute)

            if isinstance(data, pd.DataFrame):
                statements[section] = data.copy()
            else:
                statements[section] = pd.DataFrame()

        except Exception:
            statements[section] = pd.DataFrame()

    return statements


def prepare_data(data):
    """Sort financial periods newest first."""

    if not isinstance(data, pd.DataFrame):
        return pd.DataFrame()

    result = data.copy()

    if result.empty:
        return result

    try:
        ordered_columns = sorted(
            result.columns,
            key=lambda col: pd.Timestamp(col),
            reverse=True,
        )

        result = result.loc[:, ordered_columns]

    except (ValueError, TypeError):
        pass

    return result


def find_metric(data, possible_names):
    """Find an existing financial metric by its exact row label."""

    if data is None or data.empty:
        return None, None

    for candidate in possible_names:
        matches = [
            index
            for index, row_name in enumerate(data.index)
            if str(row_name).lower().strip()
            == candidate.lower().strip()
        ]

        if matches:
            position = matches[0]
            return (
                str(data.index[position]),
                data.iloc[position],
            )

    return None, None


# ============================================================
# STATEMENT CONFIGURATION
# ============================================================

CONFIG = {
    "Income Statement": {
        "highlights": [
            (
                "Total Revenue",
                ["Total Revenue", "Operating Revenue"],
            ),
            (
                "Net Income",
                [
                    "Net Income",
                    "Net Income Common Stockholders",
                    "Net Income From Continuing Operation Net Minority Interest",
                ],
            ),
            (
                "EBITDA",
                ["Normalized EBITDA", "EBITDA"],
            ),
            (
                "Tax Rate",
                ["Tax Rate For Calcs", "Effective Tax Rate"],
            ),
        ],
        "chart": [
            (
                "Revenue",
                ["Total Revenue", "Operating Revenue"],
                BLUE,
            ),
            (
                "Net Income",
                [
                    "Net Income",
                    "Net Income Common Stockholders",
                    "Net Income From Continuing Operation Net Minority Interest",
                ],
                GREEN,
            ),
        ],
    },

    "Balance Sheet": {
        "highlights": [
            (
                "Total Assets",
                ["Total Assets"],
            ),
            (
                "Total Debt",
                ["Total Debt"],
            ),
            (
                "Cash",
                [
                    "Cash And Cash Equivalents",
                    "Cash Cash Equivalents And Short Term Investments",
                    "Cash And Short Term Investments",
                ],
            ),
            (
                "Stockholders' Equity",
                [
                    "Stockholders Equity",
                    "Total Equity Gross Minority Interest",
                    "Common Stock Equity",
                ],
            ),
        ],
        "chart": [
            (
                "Total Assets",
                ["Total Assets"],
                BLUE,
            ),
            (
                "Total Debt",
                ["Total Debt"],
                YELLOW,
            ),
        ],
    },

    "Cash Flow": {
        "highlights": [
            (
                "Operating Cash Flow",
                [
                    "Operating Cash Flow",
                    "Cash Flow From Continuing Operating Activities",
                ],
            ),
            (
                "Free Cash Flow",
                ["Free Cash Flow"],
            ),
            (
                "Capital Expenditure",
                ["Capital Expenditure"],
            ),
            (
                "Stock Repurchases",
                [
                    "Repurchase Of Capital Stock",
                    "Common Stock Repurchase",
                ],
            ),
        ],
        "chart": [
            (
                "Operating Cash Flow",
                [
                    "Operating Cash Flow",
                    "Cash Flow From Continuing Operating Activities",
                ],
                BLUE,
            ),
            (
                "Free Cash Flow",
                ["Free Cash Flow"],
                GREEN,
            ),
        ],
    },
}


# ============================================================
# TOP INFORMATION BAR
# ============================================================

def show_compact_info_bar(
    currency,
    latest_period,
    total_metrics,
):

    cards = [
        ("Currency", currency),
        ("Display unit", "Auto B / M / K"),
        ("Latest period", latest_period),
        ("Metrics", str(total_metrics)),
    ]

    columns = st.columns(
        4,
        gap="small",
    )

    for column, (label, value) in zip(columns, cards):
        with column:
            safe_label = escape(str(label))
            safe_value = escape(str(value))

            html = (
                '<div class="nimbus-mini-info">'
                f'<div class="nimbus-mini-label">{safe_label}</div>'
                f'<div class="nimbus-mini-value">{safe_value}</div>'
                '</div>'
            )

            st.markdown(
                html,
                unsafe_allow_html=True,
            )


# ============================================================
# FINANCIAL HIGHLIGHT CARDS
# ============================================================

def show_highlights(
    data,
    section,
    currency,
    reporting_period,
):
    st.markdown("#### Financial Highlights")

    columns = st.columns(
        4,
        gap="small",
    )

    for column, (title, names) in zip(
        columns,
        CONFIG[section]["highlights"],
    ):
        metric_name, row = find_metric(
            data,
            names,
        )

        with column:
            with st.container(border=True):
                st.caption(title)

                if row is None or row.empty:
                    st.markdown("### N/A")
                    st.caption("Not reported")
                    continue

                current = row.iloc[0]

                previous = (
                    row.iloc[1]
                    if len(row) > 1
                    else None
                )

                st.markdown(
                    "### "
                    + format_value(
                        current,
                        metric_name,
                        currency,
                    )
                )

                if metric_type(metric_name) == "percent":
                    difference = calculate_rate_change(
                        current,
                        previous,
                    )

                    if difference is None:
                        st.caption("Previous period unavailable")
                    else:
                        st.caption(
                            f"{difference:+.2f} pp vs. previous period"
                        )

                else:
                    difference = calculate_change(
                        current,
                        previous,
                    )

                    if difference is None:
                        st.caption("Previous period unavailable")
                    else:
                        st.caption(
                            f"{difference:+.2f}% vs. previous period"
                        )

    st.caption(
        "Changes compare the latest two reported periods. "
        "An increase does not always indicate an improvement."
    )


# ============================================================
# FINANCIAL TREND CHART
# ============================================================

def show_financial_trend(
    data,
    section,
    currency,
    reporting_period,
):
    st.markdown("#### Financial Trend")

    if data is None or data.empty:
        st.info("Trend data is unavailable.")
        return

    dates = list(reversed(data.columns))

    labels = [
        period_label(date, reporting_period)
        for date in dates
    ]

    fig = go.Figure()
    series_found = 0

    for title, possible_names, color in CONFIG[section]["chart"]:
        name, row = find_metric(
            data,
            possible_names,
        )

        if row is None:
            continue

        values = (
            pd.to_numeric(
                row.iloc[::-1],
                errors="coerce",
            ) / 1e9
        )

        if values.isna().all():
            continue

        fig.add_trace(
            go.Bar(
                x=labels,
                y=values.to_numpy(),
                name=title,
                marker_color=color,
                hovertemplate=(
                    "%{x}<br>"
                    f"{title}: {currency} "
                    "%{y:,.2f}B"
                    "<extra></extra>"
                ),
            )
        )

        series_found += 1

    if series_found == 0:
        st.info(
            "Not enough reported data to show this chart."
        )
        return

    fig.update_layout(
        height=325,
        barmode="group",
        paper_bgcolor=BACKGROUND,
        plot_bgcolor=BACKGROUND,
        font=dict(color=TEXT, size=12),
        margin=dict(l=12, r=12, t=25, b=12),
        legend=dict(
            orientation="h",
            y=1.15,
            x=0,
        ),
        xaxis=dict(
            type="category",
            showgrid=False,
        ),
        yaxis=dict(
            title=f"{currency} billions",
            gridcolor=GRID,
            zerolinecolor=GRID,
        ),
        bargap=0.28,
        hovermode="x unified",
    )

    with st.container(border=True):
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displaylogo": False,
            },
        )


# ============================================================
# CLEAN FINANCIAL TABLE
# ============================================================

def build_financial_table(
    data,
    currency,
    reporting_period,
):
    """
    Build display values from raw financial data.

    Does not use Pandas Styler.
    Handles duplicate financial metric names safely.
    """

    if data is None or data.empty:
        return pd.DataFrame()

    rows = []

    for position in range(len(data)):
        row_name = str(data.index[position])
        original = data.iloc[position]

        output_row = {
            "Financial Metric": row_name,
        }

        for col_position, column in enumerate(data.columns):
            label = period_label(
                column,
                reporting_period,
            )

            output_row[label] = format_value(
                original.iloc[col_position],
                row_name,
                currency,
            )

        if len(data.columns) >= 2:
            current = original.iloc[0]
            previous = original.iloc[1]

            if metric_type(row_name) == "percent":
                change = calculate_rate_change(
                    current,
                    previous,
                )

                change_display = (
                    f"{change:+.2f} pp"
                    if change is not None
                    else "—"
                )

            else:
                change = calculate_change(
                    current,
                    previous,
                )

                change_display = (
                    f"{change:+.2f}%"
                    if change is not None
                    else "—"
                )

            change_column = (
                "QoQ Change"
                if reporting_period == "Quarterly"
                else "YoY Change"
            )

            output_row[change_column] = change_display

        rows.append(output_row)

    table = pd.DataFrame(rows)

    # Guarantee a unique row index.
    table = table.reset_index(drop=True)

    # Guarantee unique column labels.
    seen = {}
    unique_columns = []

    for column in table.columns:
        label = str(column)
        seen[label] = seen.get(label, 0) + 1

        if seen[label] > 1:
            unique_columns.append(
                f"{label} ({seen[label]})"
            )
        else:
            unique_columns.append(label)

    table.columns = unique_columns

    return table


def show_financial_table(
    data,
    section,
    currency,
    reporting_period,
):
    st.markdown(
        f"#### {section} Details"
    )

    table = build_financial_table(
        data,
        currency,
        reporting_period,
    )

    if table.empty:
        st.info("Financial data is unavailable.")
        return

    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        height=min(
            575,
            85 + len(table) * 35,
        ),
        column_config={
            "Financial Metric": st.column_config.TextColumn(
                "Financial Metric",
                width="large",
            ),
        },
    )

    raw_data = data.copy()
    raw_data.index.name = "Financial Metric"

    file_name = (
        section.lower().replace(" ", "_")
        + "_"
        + reporting_period.lower()
        + ".csv"
    )

    st.download_button(
        "Download CSV",
        data=raw_data.to_csv().encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
        key=f"financial_download_{section}_{reporting_period}",
    )

    st.caption(
        "Numbers are rounded for display. "
        "CSV downloads contain the original values."
    )


# ============================================================
# SINGLE STATEMENT TAB
# ============================================================


def show_statement_tab(
    section,
    data,
    currency,
    reporting_period,
):
    """Display financial statement without description text."""

    st.markdown(f"### {section}")

    if data is None or data.empty:
        st.info(
            "No financial data is currently available."
        )
        return

    # Financial highlight cards
    show_highlights(
        data,
        section,
        currency,
        reporting_period,
    )

    # Financial trend chart
    show_financial_trend(
        data,
        section,
        currency,
        reporting_period,
    )

    # Detailed financial table and CSV download
    show_financial_table(
        data,
        section,
        currency,
        reporting_period,
    )

# ============================================================
# MAIN FINANCIAL STATEMENTS DASHBOARD
# ============================================================

def show_financial_statements(
    ticker,
    financials=None,
    currency=None,
):
    ticker = (ticker or "").strip().upper()

    if not ticker:
        st.warning("Search for a company first.")
        return

    currency = currency or "USD"

    # --------------------------------------------------------
    # PAGE STYLING
    # --------------------------------------------------------

    st.markdown(
        """
        <style>
        .nimbus-financial-title {
            font-size: 1.75rem;
            font-weight: 750;
            color: #EAF0F7;
            letter-spacing: -0.025em;
            margin-bottom: 0.15rem;
        }

        .nimbus-financial-description {
            font-size: 0.9rem;
            color: #9AA9BB;
            margin-bottom: 0.8rem;
        }

        /* Compact summary information boxes */
        .nimbus-mini-info {
            background: #151B23;
            border: 1px solid #303B49;
            border-radius: 9px;
            padding: 9px 12px;
            min-height: 57px;
            margin-bottom: 2px;
        }

        .nimbus-mini-label {
            color: #97A4B5;
            font-size: 0.70rem;
            line-height: 1.2;
            margin-bottom: 4px;
        }

        .nimbus-mini-value {
            color: #F1F5F9;
            font-size: 0.86rem;
            font-weight: 700;
            line-height: 1.25;
        }

        div[data-testid="stTabs"] button {
            font-weight: 650;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # PAGE TITLE
    # --------------------------------------------------------

    st.markdown(
        '<div class="nimbus-financial-title">'
        'Financial Statements'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="nimbus-financial-description">'
        f'Explore financial performance for {escape(ticker)}'
        '</div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # REPORTING PERIOD
    # --------------------------------------------------------

    reporting_period = st.radio(
        "Reporting period",
        [
            "Annual",
            "Quarterly",
        ],
        horizontal=True,
        key=f"financial_period_{ticker}",
    )

    # --------------------------------------------------------
    # FETCH STATEMENTS
    # --------------------------------------------------------

    try:
        statements = fetch_statements(
            ticker,
            reporting_period,
        )

    except Exception:
        statements = {}

    if (
        reporting_period == "Annual"
        and isinstance(financials, dict)
    ):
        for section in CONFIG:
            fetched = statements.get(section)

            if fetched is None or fetched.empty:
                statements[section] = financials.get(
                    section,
                    pd.DataFrame(),
                )

    for section in CONFIG:
        statements[section] = prepare_data(
            statements.get(section)
        )

    # --------------------------------------------------------
    # LATEST PERIOD AND METRIC COUNT
    # --------------------------------------------------------

    latest_dates = []

    for statement in statements.values():
        for column in statement.columns:
            try:
                latest_dates.append(
                    pd.Timestamp(column)
                )
            except (TypeError, ValueError):
                continue

    if latest_dates:
        latest_period = period_label(
            max(latest_dates),
            reporting_period,
        )
    else:
        latest_period = "N/A"

    total_metrics = sum(
        len(statement)
        for statement in statements.values()
    )

    # --------------------------------------------------------
    # COMPACT INFORMATION BOXES
    # --------------------------------------------------------

    show_compact_info_bar(
        currency=currency,
        latest_period=latest_period,
        total_metrics=total_metrics,
    )

    st.caption(
        "B = billions · M = millions · K = thousands. "
        "Rates, EPS and share counts use their own units."
    )

    # --------------------------------------------------------
    # THREE FINANCIAL STATEMENT TABS
    # --------------------------------------------------------

    income_tab, balance_tab, cash_tab = st.tabs(
        [
            "Income Statement",
            "Balance Sheet",
            "Cash Flow",
        ]
    )

    with income_tab:
        show_statement_tab(
            "Income Statement",
            statements["Income Statement"],
            currency,
            reporting_period,
        )

    with balance_tab:
        show_statement_tab(
            "Balance Sheet",
            statements["Balance Sheet"],
            currency,
            reporting_period,
        )

    with cash_tab:
        show_statement_tab(
            "Cash Flow",
            statements["Cash Flow"],
            currency,
            reporting_period,
        )

    st.caption(
        "Source: Yahoo Finance via yfinance. "
        "Reported values and periods vary by company."
    )
