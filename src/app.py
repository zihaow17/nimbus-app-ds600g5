"""Streamlit homepage for the financial data explorer."""

from pathlib import Path

import streamlit as st

from features.company_comparison import show_company_comparison
from features.loading_screen import show_loading_screen
from features.company_search import show_company_search_page
from features.notes import show_notes_feature
from features.recent_history import show_recent_history_page

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ICON_PATH = PROJECT_ROOT / "assets" / "nimbus-logo-icon.png"


st.set_page_config(
    page_title="Nimbus | Financial Intelligence",
    page_icon=str(ICON_PATH),
    layout="wide",
    initial_sidebar_state="collapsed",
)

show_loading_screen()

st.markdown(
    """
    <style>
    .stApp {
        background: #111315;
        color: #f0f1ef;
    }
    .stApp .block-container {
        max-width: 1160px;
        padding: 1.5rem clamp(1rem, 4vw, 3rem) 3rem;
    }
    .stApp [data-testid="stHeader"] {
        background: transparent;
    }
    [data-testid="stSidebar"],
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"] {
        display: none;
    }
    .stApp [data-testid="stMarkdownContainer"] {
        color: #f0f1ef;
    }
    .stApp [data-testid="stMarkdownContainer"] h2.content-section-title {
        font-family: Consolas, monospace;
    }
    .topbar-brand,
    .topbar-action,
    .hero,
    .or-divider,
    .compare-title,
    .content-section-title,
    .recent-history-header,
    .recent-history-cell,
    .recent-history-reload,
    .stApp [data-testid="stForm"],
    .stApp [data-testid="stSelectbox"],
    .stApp [data-testid="stRadio"] {
        font-family: Consolas, monospace;
    }
    .st-key-nimbus_page [data-testid="stRadioGroup"] {
        align-items: stretch;
        display: flex;
        flex-direction: row;
        gap: 2rem;
    }
    .st-key-nimbus_page [data-testid="stRadioOption"] {
        align-items: center;
        background: transparent !important;
        border: 0;
        border-bottom: 2px solid transparent;
        border-radius: 0;
        color: #aeb3b4;
        cursor: pointer;
        margin: 0;
        padding: 0.7rem 0.2rem 0.55rem;
    }
    .st-key-nimbus_page [data-testid="stRadioOption"][data-selected="true"] {
        border-bottom-color: #55c7f7;
        color: #f0f1ef;
    }
    .st-key-nimbus_page [data-testid="stRadioOption"] > div > div:first-child {
        display: none;
    }
    .st-key-nimbus_page [data-testid="stRadioOption"] [data-testid="stMarkdownContainer"] p {
        font-family: Consolas, monospace;
        margin: 0;
    }
    .st-key-nimbus_page_mobile {
        display: none;
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
        display: block;
        margin: 0 auto 1.25rem;
        max-width: min(100%, 32rem);
        width: 100%;
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
        font-family: Consolas, monospace;
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
        font-family: Consolas, monospace;
    }
    .stApp .st-key-nimbus_page_mobile [role="group"] {
        background: transparent !important;
        border-color: transparent !important;
        box-shadow: none;
    }
    .stApp .st-key-nimbus_page_mobile input[role="combobox"],
    .stApp .st-key-nimbus_page_mobile button[aria-label="Open"] {
        font-family: Consolas, monospace;
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
        font-family: Consolas, monospace;
        min-height: 2.7rem;
        transition: none;
    }
    .stApp [data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"]),
    .stApp [data-testid="stElementContainer"]:has([data-testid="stButton"]) {
        width: 100%;
    }
    .stApp [data-testid="stFormSubmitButton"],
    .stApp [data-testid="stButton"] {
        display: flex;
        justify-content: center;
        width: 100%;
    }
    .stApp [data-testid="stFormSubmitButton"] button,
    .stApp [data-testid="stButton"] button {
        width: auto;
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
    .recent-history-header {
        font-weight: 700;
        color: #e9ebe8;
        padding-bottom: 0.5rem;
        margin-top: 0.15rem;
    }
    .recent-history-cell {
        color: #edf1f1;
        line-height: 1.5;
        min-height: 1.9rem;
        display: flex;
        align-items: center;
        height: 100%;
    }
    .recent-history-button-wrap {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        min-height: 1.9rem;
    }
    .recent-history-row-gap {
        height: 0.75rem;
    }
    .recent-history-row-gap-header {
        height: 0.9rem;
    }
    .recent-history-reload {
        min-height: 1.6rem;
        height: 1.6rem;
        padding: 0.1rem 0.7rem;
        border-radius: 0.45rem;
        border: 1px solid #6d7680;
        background: rgba(27, 31, 35, 0.8);
        color: #edf1f1;
        font-size: 0.72rem;
        line-height: 1;
        cursor: not-allowed;
        opacity: 0.85;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin: auto 0;
    }
    @media (max-width: 700px) {
        .stApp .block-container {
            padding: 1rem 1rem 2rem;
        }
        .st-key-nimbus_page {
            display: none;
        }
        .st-key-nimbus_page_mobile {
            display: block;
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

brand_column, spacer_column, account_column, settings_column = st.columns([5, 5.5, 1.2, 0.5])
with brand_column:
    st.markdown('<div class="topbar-brand">NIMBUS</div>', unsafe_allow_html=True)
with account_column:
    st.markdown('<div class="topbar-action">👤 Account</div>', unsafe_allow_html=True)
with settings_column:
    st.markdown('<div class="topbar-action">⚙</div>', unsafe_allow_html=True)

st.markdown('<div class="header-rule"></div>', unsafe_allow_html=True)
page_options = ("Company Search", "Company Comparison", "Recently Viewed")


def _sync_mobile_page() -> None:
    """Copy the mobile selector value into the shared page selection."""
    st.session_state["nimbus_page"] = st.session_state["nimbus_page_mobile"]


if "nimbus_page" not in st.session_state:
    st.session_state["nimbus_page"] = page_options[0]
if st.session_state["nimbus_page"] not in page_options:
    st.session_state["nimbus_page"] = page_options[0]
if st.session_state.get("nimbus_page_mobile") != st.session_state["nimbus_page"]:
    st.session_state["nimbus_page_mobile"] = st.session_state["nimbus_page"]

st.radio(
    "Pages",
    page_options,
    horizontal=True,
    key="nimbus_page",
    label_visibility="collapsed",
)
st.selectbox(
    "Pages",
    page_options,
    key="nimbus_page_mobile",
    on_change=_sync_mobile_page,
    label_visibility="collapsed",
)

selected_page = st.session_state["nimbus_page"]

if selected_page == "Company Search":
    show_company_search_page()
elif selected_page == "Company Comparison":
    show_company_comparison()
else:
    show_recent_history_page()

show_notes_feature()