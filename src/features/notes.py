"""Compact, locally persisted notes for the active company or comparison."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Optional
from uuid import uuid4

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
NOTES_DIR = PROJECT_ROOT / ".cache" / "nimbus"
NOTES_PATH = NOTES_DIR / "notes.db"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _connect() -> sqlite3.Connection:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(NOTES_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            note_id TEXT PRIMARY KEY,
            context_key TEXT NOT NULL,
            context_label TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


def _current_context() -> Optional[dict[str, str]]:
    """Return the company or comparison currently visible to the user."""
    selected_page = st.session_state.get("nimbus_page")
    search_result = st.session_state.get("company_search_results")
    comparison = st.session_state.get("nimbus_comparison_results")

    if selected_page == "Company Comparison" and comparison and len(comparison) >= 4:
        ticker_one = str(comparison[0] or "").strip().upper()
        ticker_two = str(comparison[2] or "").strip().upper()
        if ticker_one and ticker_two:
            name_one = str(comparison[1].get("shortName") or ticker_one).strip()
            name_two = str(comparison[3].get("shortName") or ticker_two).strip()
            return {
                "key": f"comparison:{ticker_one}:{ticker_two}",
                "label": f"{name_one} vs {name_two}",
            }

    if selected_page == "Company Search" and search_result:
        ticker = str(search_result.get("ticker") or "").strip().upper()
        if ticker:
            company_name = str(search_result.get("company_name") or ticker).strip()
            return {
                "key": f"company:{ticker}",
                "label": f"{company_name} ({ticker})",
            }

    if comparison and len(comparison) >= 4:
        ticker_one = str(comparison[0] or "").strip().upper()
        ticker_two = str(comparison[2] or "").strip().upper()
        if ticker_one and ticker_two:
            name_one = str(comparison[1].get("shortName") or ticker_one).strip()
            name_two = str(comparison[3].get("shortName") or ticker_two).strip()
            return {
                "key": f"comparison:{ticker_one}:{ticker_two}",
                "label": f"{name_one} vs {name_two}",
            }

    return None


def _load_notes(context_key: str) -> list[dict[str, str]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT note_id, context_key, context_label, title, body, created_at, updated_at
            FROM notes
            WHERE context_key = ?
            ORDER BY updated_at DESC
            """,
            (context_key,),
        ).fetchall()
    return [dict(row) for row in rows]


def _create_note(context: dict[str, str]) -> str:
    note_id = str(uuid4())
    now = _utc_now()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO notes (
                note_id, context_key, context_label, title, body, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (note_id, context["key"], context["label"], "Untitled note", "", now, now),
        )
        connection.commit()
    return note_id


def _update_note(note_id: str, title: str, body: str) -> None:
    with _connect() as connection:
        connection.execute(
            """
            UPDATE notes
            SET title = ?, body = ?, updated_at = ?
            WHERE note_id = ?
            """,
            (title.strip() or "Untitled note", body, _utc_now(), note_id),
        )
        connection.commit()


def _delete_note(note_id: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))
        connection.commit()


def _save_active_note() -> None:
    note_id = st.session_state.get("notes_active_id")
    if not note_id:
        return
    try:
        _update_note(
            note_id,
            st.session_state.get("notes_title", ""),
            st.session_state.get("notes_body", ""),
        )
        st.session_state["notes_save_status"] = "Saved just now"
    except sqlite3.Error as error:
        st.session_state["notes_save_status"] = f"Could not save note: {error}"


def _select_note(note_id: str, notes: list[dict[str, str]]) -> None:
    selected = next((note for note in notes if note["note_id"] == note_id), None)
    if selected is None:
        return
    st.session_state["notes_active_id"] = selected["note_id"]
    st.session_state["notes_title"] = selected["title"]
    st.session_state["notes_body"] = selected["body"]
    st.session_state["notes_save_status"] = ""


@st.dialog("Notes", width="small", position="right")
def _show_notes_dialog(context: dict[str, str]) -> None:
    """Render the notes drawer for one company or comparison context."""
    st.caption(context["label"])
    try:
        notes = _load_notes(context["key"])
    except sqlite3.Error as error:
        st.error(f"Could not load notes: {error}")
        return

    note_ids = {note["note_id"] for note in notes}
    active_id = st.session_state.get("notes_active_id")
    if active_id not in note_ids:
        active_id = notes[0]["note_id"] if notes else None
        if active_id:
            _select_note(active_id, notes)

    if notes:
        options = {note["note_id"]: note["title"] for note in notes}
        selected_id = st.selectbox(
            "Saved notes",
            list(options),
            index=list(options).index(active_id),
            format_func=options.get,
            key="notes_selector",
        )
        if selected_id != st.session_state.get("notes_active_id"):
            _select_note(selected_id, notes)
            st.rerun()
    else:
        st.info("No notes for this company yet.")

    if st.button("＋ New note", key="notes_new_note", use_container_width=True):
        try:
            note_id = _create_note(context)
        except sqlite3.Error as error:
            st.error(f"Could not create note: {error}")
            return
        st.session_state["notes_active_id"] = note_id
        st.session_state["notes_title"] = "Untitled note"
        st.session_state["notes_body"] = ""
        st.session_state["notes_save_status"] = "Saved just now"
        st.rerun()

    active_id = st.session_state.get("notes_active_id")
    if active_id:
        st.text_input(
            "Title",
            key="notes_title",
            on_change=_save_active_note,
        )
        st.text_area(
            "Note",
            key="notes_body",
            height=220,
            placeholder="Write your thoughts about this company...",
            on_change=_save_active_note,
        )
        status = st.session_state.get("notes_save_status")
        if status:
            st.caption(status)
        if st.button("Delete note", key="notes_delete_note", type="secondary"):
            try:
                _delete_note(active_id)
            except sqlite3.Error as error:
                st.error(f"Could not delete note: {error}")
                return
            st.session_state["notes_active_id"] = None
            st.session_state["notes_title"] = ""
            st.session_state["notes_body"] = ""
            st.session_state["notes_save_status"] = ""
            st.rerun()


def show_notes_feature() -> None:
    """Render the compact Notes trigger and its context-aware dialog."""
    context = _current_context()
    button_column = st.columns([1, 5, 1])[1]
    with button_column:
        if st.button(
            "📝 Notes",
            key="open_notes",
            use_container_width=True,
            disabled=context is None,
            help="Add private notes to the company or comparison currently displayed.",
        ):
            st.session_state["notes_context_key"] = context["key"]
            st.session_state["notes_active_id"] = None
            st.session_state["notes_save_status"] = ""
            st.session_state["notes_dialog_open"] = True

    if st.session_state.get("notes_dialog_open") and context:
        if st.session_state.get("notes_context_key") == context["key"]:
            _show_notes_dialog(context)
