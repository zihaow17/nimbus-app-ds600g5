"""Opening splash screen for the Nimbus app."""

import base64
from pathlib import Path
import time

import streamlit as st


SPLASH_DURATION = 3
LOADING_SCREEN_SHOWN_KEY = "loading_screen_shown"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOADING_ANIMATION_PATH = PROJECT_ROOT / "assets" / "loading_animation.mp4"


def _loading_screen_html(video_data: str) -> str:
    """Build the full-screen overlay containing the looping video."""
    return f"""
        <div class="nimbus-loading-screen">
            <video autoplay loop muted playsinline aria-label="Loading Nimbus">
                <source src="data:video/mp4;base64,{video_data}" type="video/mp4" />
            </video>
        </div>
        <style>
            .nimbus-loading-screen {{
                position: fixed;
                inset: 0;
                z-index: 1000000;
                display: flex;
                align-items: center;
                justify-content: center;
                background: #000000;
            }}
            .nimbus-loading-screen video {{
                display: block;
                width: min(80vw, 520px);
                max-height: 80vh;
                object-fit: contain;
            }}
        </style>
    """


def show_loading_screen() -> None:
    """Show the opening animation once per Streamlit user session."""
    if st.session_state.get(LOADING_SCREEN_SHOWN_KEY, False):
        return

    if not LOADING_ANIMATION_PATH.is_file():
        st.warning("Splash screen skipped: loading_animation.mp4 was not found.")
        st.session_state[LOADING_SCREEN_SHOWN_KEY] = True
        return

    try:
        video_data = base64.b64encode(LOADING_ANIMATION_PATH.read_bytes()).decode("ascii")
    except OSError as error:
        st.warning(f"Splash screen skipped: could not read the loading video ({error}).")
        st.session_state[LOADING_SCREEN_SHOWN_KEY] = True
        return

    overlay = st.empty()
    overlay.markdown(_loading_screen_html(video_data), unsafe_allow_html=True)
    time.sleep(SPLASH_DURATION)
    overlay.empty()
    st.session_state[LOADING_SCREEN_SHOWN_KEY] = True
