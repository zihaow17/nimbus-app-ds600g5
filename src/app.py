"""Streamlit homepage for the financial data explorer."""

import streamlit as st

from analysis import get_analyst_ratings, get_financials, get_news, get_price


st.set_page_config(page_title="Nimbus | Financial Intelligence", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background: #111315;
        color: #f0f1ef;
        font-family: "SFMono-Regular", Menlo, Consolas, monospace;
    }
    .stApp .block-container {
        max-width: 1160px;
        padding: 1.5rem clamp(1rem, 4vw, 3rem) 3rem;
    }
    .stApp [data-testid="stHeader"] {
        background: transparent;
    }
    .stApp [data-testid="stMarkdownContainer"] {
        color: #f0f1ef;
        font-family: "SFMono-Regular", Menlo, Consolas, monospace;
    }
    .topbar-brand {
        color: #f4f5f2;
        font-size: 1.05rem;
        font-weight: 700;
    }
    .topbar-action {
        color: #c5c9c9;
        font-size: 0.85rem;
        text-align: right;
        white-space: nowrap;
    }
    .header-rule {
        border-top: 1px solid #383d40;
        margin: 0.5rem 0 0;
    }
    .hero {
        padding: 3.5rem 1rem 2rem;
        text-align: center;
    }
    .hero-name {
        color: #f6f7f4;
        font-size: 2.35rem;
        font-weight: 700;
        line-height: 1.2;
        margin: 0 0 0.65rem;
    }
    .hero-title {
        color: #e1e3e1;
        font-size: 1.2rem;
        line-height: 1.5;
        margin: 0 0 0.75rem;
    }
    .hero-description {
        color: #aeb3b4;
        font-size: 0.95rem;
        line-height: 1.6;
        margin: 0;
    }
    .stApp [data-testid="stForm"] {
        background: transparent;
        border: 0;
        margin: 0 auto;
        max-width: 620px;
        padding: 0;
    }
    .stApp [data-testid="stTextInput"] input {
        background: #141719;
        border: 1px solid #666d70;
        border-radius: 2px;
        color: #f0f1ef;
        min-height: 3.4rem;
        font-family: "SFMono-Regular", Menlo, Consolas, monospace;
        font-size: 1rem;
    }
    .stApp [data-testid="stTextInput"] input::placeholder {
        color: #aeb3b4;
        opacity: 1;
    }
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div {
        background: #141719;
        border-color: #4b5154;
        border-radius: 2px;
        color: #e4e6e4;
    }
    .stApp [data-testid="stCaptionContainer"] p {
        color: #969d9f;
        font-size: 0.8rem;
    }
    .stApp [data-testid="stFormSubmitButton"] button,
    .stApp [data-testid="stButton"] button {
        background: transparent;
        border: 1px solid #737a7d;
        border-radius: 2px;
        color: #f0f1ef;
        font-family: "SFMono-Regular", Menlo, Consolas, monospace;
        min-height: 2.7rem;
        transition: none;
    }
    .stApp [data-testid="stFormSubmitButton"] button:hover,
    .stApp [data-testid="stButton"] button:hover {
        background: #202426;
        border-color: #aeb4b6;
        color: #ffffff;
    }
    .stApp [data-testid="stButton"] button:disabled {
        background: transparent;
        border-color: #4b5154;
        color: #92999b;
        opacity: 1;
    }
    .or-divider {
        color: #969d9f;
        font-size: 0.85rem;
        margin: 1.6rem 0 0.7rem;
        text-align: center;
    }
    .compare-title {
        color: #e1e3e1;
        font-size: 1rem;
        margin: 0 0 0.9rem;
        text-align: center;
    }
    .content-section-title {
        color: #e9ebe8;
        font-size: 1rem;
        font-weight: 600;
        margin: 0;
    }
    .reserved-space {
        min-height: 7rem;
    }
    .recent-space {
        min-height: 5rem;
    }
    @media (max-width: 700px) {
        .stApp .block-container {
            padding: 1rem 1rem 2rem;
        }
        .hero {
            padding: 2.5rem 0.25rem 1.5rem;
        }
        .hero-name {
            font-size: 2rem;
        }
        .hero-title {
            font-size: 1.05rem;
        }
        .topbar-action {
            font-size: 0.75rem;
        }
        .reserved-space {
            min-height: 5rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

brand_column, spacer_column, account_column, settings_column = st.columns(
    [5, 5.5, 1.2, 0.5]
)
with brand_column:
    st.markdown('<div class="topbar-brand">NIMBUS</div>', unsafe_allow_html=True)
with account_column:
    st.markdown('<div class="topbar-action">👤 Account</div>', unsafe_allow_html=True)
with settings_column:
    st.markdown('<div class="topbar-action">⚙</div>', unsafe_allow_html=True)

st.markdown('<div class="header-rule"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <section class="hero">
        <h1 class="hero-name">NIMBUS</h1>
        <div class="hero-title">Financial Intelligence Dashboard</div>
        <p class="hero-description">Search for a company to explore its financial data</p>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.form("analysis_form"):
    ticker = st.text_input(
        "Company or ticker",
        placeholder="🔍  Search company or ticker",
        label_visibility="collapsed",
        help="Enter a ticker symbol, for example AAPL or MSFT.",
    )
    st.caption("e.g. Apple, AAPL, Microsoft, MSFT")
    analysis_type = st.selectbox(
        "Data to explore",
        ("filings", "news", "stock price ratings"),
        format_func=lambda value: {
            "filings": "Financial statements",
            "news": "Recent news",
            "stock price ratings": "Stock price and analyst ratings",
        }[value],
    )
    button_left, button_center, button_right = st.columns([1, 1, 1])
    with button_center:
        run_analysis = st.form_submit_button("Search")

if run_analysis:
    ticker = ticker.strip().upper()
    if not ticker:
        st.error("Enter a ticker symbol before running an analysis.")
    else:
        try:
            with st.spinner(f"Loading {analysis_type} for {ticker}..."):
                if analysis_type == "filings":
                    results = get_financials(ticker)
                    for section, data in results.items():
                        st.subheader(section)
                        if data.empty:
                            st.info(f"No {section.lower()} data was found for {ticker}.")
                        else:
                            st.dataframe(data, use_container_width=True)

                elif analysis_type == "news":
                    st.subheader(f"Recent news for {ticker}")
                    articles = get_news(ticker)
                    if articles.empty:
                        st.info(f"No recent news was found for {ticker}.")
                    else:
                        st.dataframe(articles, use_container_width=True, hide_index=True)

                else:
                    st.subheader(f"Stock price and analyst ratings for {ticker}")
                    price = get_price(ticker)
                    if price is None:
                        st.metric("Current price", "Not available")
                    else:
                        st.metric("Current price", f"${price:,.2f}")

                    ratings = get_analyst_ratings(ticker)
                    if ratings.empty:
                        st.info(f"No analyst recommendations were found for {ticker}.")
                    else:
                        st.dataframe(ratings, use_container_width=True)
        except Exception as error:
            st.error(f"Could not load data for {ticker}. Check the symbol and try again.")
            st.caption(f"Details: {error}")

st.markdown('<div class="or-divider">— OR —</div>', unsafe_allow_html=True)
st.markdown('<div class="compare-title">Compare two companies</div>', unsafe_allow_html=True)
compare_left, compare_center, compare_right = st.columns([1, 2, 1])
with compare_center:
    st.button("Compare Companies →", disabled=True, help="Company comparison is not available yet.")

st.markdown('<div class="header-rule"></div>', unsafe_allow_html=True)
st.markdown('<h2 class="content-section-title">⭐ Favourite Companies</h2>', unsafe_allow_html=True)
st.markdown('<div class="reserved-space" aria-hidden="true"></div>', unsafe_allow_html=True)

st.markdown('<h2 class="content-section-title">Recently Viewed</h2>', unsafe_allow_html=True)
st.markdown('<div class="recent-space" aria-hidden="true"></div>', unsafe_allow_html=True)