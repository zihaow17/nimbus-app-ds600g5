"""Fixed favourite-company cards for the Company Search page."""

from typing import Optional

import streamlit as st

from analysis import get_price


FAVOURITE_TICKERS = ("AAPL", "NVDA", "MU")


@st.cache_data(ttl=300, show_spinner=False)
def _get_favourite_price(ticker: str):
    """Fetch a favourite's latest price, caching it briefly between reruns."""
    return get_price(ticker)


def show_favourite_companies() -> Optional[str]:
    """Render compact inline favourite buttons and return a selected ticker."""
    st.markdown(
        """
        <style>
        .st-key-favourites-row {
            margin: -0.35rem auto 0;
            max-width: 620px;
        }
        .favourites-label {
            color: #e9ebe8;
            font-family: Consolas, monospace;
            font-size: 0.9rem;
            font-weight: 600;
            white-space: nowrap;
        }
        .st-key-favourite_aapl button,
        .st-key-favourite_nvda button,
        .st-key-favourite_mu button {
            min-height: 2.7rem;
            width: 100%;
            white-space: nowrap;
            font-size: 0.85rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    selected_ticker = None
    with st.container(key="favourites-row"):
        columns = st.columns(
            [1.45, 0.8, 0.35, 0.8, 0.35, 0.8],
            vertical_alignment="center",
        )
        with columns[0]:
            st.markdown('<div class="favourites-label">Favourites:</div>', unsafe_allow_html=True)

        button_columns = (columns[1], columns[3], columns[5])
        for column, ticker in zip(button_columns, FAVOURITE_TICKERS):
            try:
                price = _get_favourite_price(ticker)
                price_label = f"${price:,.2f}" if isinstance(price, (int, float)) else "N/A"
            except Exception:
                price_label = "N/A"

            with column:
                if st.button(
                    f"{ticker} {price_label}",
                    key=f"favourite_{ticker.lower()}",
                    use_container_width=True,
                ):
                    selected_ticker = ticker

    return selected_ticker
