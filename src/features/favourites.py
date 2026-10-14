"""Favourites page placeholder."""

import streamlit as st


def show_favourites_page() -> None:
    """Render the current placeholder for the future favourites feature."""
    st.markdown('<h2 class="content-section-title">⭐ Favourite Companies</h2>', unsafe_allow_html=True)
    st.markdown('<div class="reserved-space" aria-hidden="true"></div>', unsafe_allow_html=True)