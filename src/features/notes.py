"""Floating, locally persisted notes for company searches and comparisons."""

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
            history_id TEXT,
            context_key TEXT NOT NULL,
            context_label TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(notes)").fetchall()
    }
    if "history_id" not in columns:
        connection.execute("ALTER TABLE notes ADD COLUMN history_id TEXT")
        connection.commit()
    return connection


def _active_context() -> Optional[dict[str, str]]:
    """Return the active search context, including its history record ID."""
    selected_page = st.session_state.get("nimbus_page")
    search_result = st.session_state.get("company_search_results")
    comparison = st.session_state.get("nimbus_comparison_results")
    history_id = st.session_state.get("current_history_id", "")

    if selected_page == "Company Comparison" and comparison and len(comparison) >= 4:
        ticker_one = str(comparison[0] or "").strip().upper()
        ticker_two = str(comparison[2] or "").strip().upper()
        if ticker_one and ticker_two:
            name_one = str(comparison[1].get("shortName") or ticker_one).strip()
            name_two = str(comparison[3].get("shortName") or ticker_two).strip()
            return {
                "history_id": history_id,
                "key": f"comparison:{ticker_one}:{ticker_two}",
                "label": f"{name_one} vs {name_two}",
            }

    if selected_page == "Company Search" and search_result:
        ticker = str(search_result.get("ticker") or "").strip().upper()
        if ticker:
            company_name = str(search_result.get("company_name") or ticker).strip()
            return {
                "history_id": history_id,
                "key": f"company:{ticker}",
                "label": f"{company_name} ({ticker})",
            }

    return None


def _load_notes(history_id: str = "", context_key: str = "") -> list[dict[str, str]]:
    with _connect() as connection:
        if history_id:
            rows = connection.execute(
                """
                SELECT note_id, history_id, context_key, context_label, title, body,
                       created_at, updated_at
                FROM notes
                WHERE (
                    history_id = ?
                    OR (history_id IS NULL AND context_key = ?)
                )
                AND (TRIM(body) <> '' OR (TRIM(title) <> '' AND title <> 'Untitled note'))
                ORDER BY updated_at DESC
                """,
                (history_id, context_key),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT note_id, history_id, context_key, context_label, title, body,
                       created_at, updated_at
                FROM notes
                WHERE TRIM(body) <> ''
                   OR (TRIM(title) <> '' AND title <> 'Untitled note')
                ORDER BY updated_at DESC
                """
            ).fetchall()
    return [dict(row) for row in rows]


def _create_note(context: dict[str, str]) -> str:
    note_id = str(uuid4())
    now = _utc_now()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO notes (
                note_id, history_id, context_key, context_label, title, body,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                context.get("history_id") or None,
                context["key"],
                context["label"],
                "",
                "",
                now,
                now,
            ),
        )
        connection.commit()
    return note_id


def _update_note(note_id: str, title: str, body: str) -> None:
    normalized_body = body.strip()
    normalized_title = title.strip() or (
        normalized_body.splitlines()[0].strip() if normalized_body else "Untitled note"
    )
    with _connect() as connection:
        connection.execute(
            """
            UPDATE notes
            SET title = ?, body = ?, updated_at = ?
            WHERE note_id = ?
            """,
            (normalized_title, body, _utc_now(), note_id),
        )
        connection.commit()


def _delete_note(note_id: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))
        connection.commit()


def _discard_active_note() -> None:
    """Delete the selected note or discard the current unsaved draft."""
    note_id = st.session_state.get("notes_active_id")
    if note_id:
        try:
            _delete_note(note_id)
        except sqlite3.Error as error:
            st.session_state["notes_save_status"] = f"Delete failed: {error}"
            return
        st.session_state["notes_save_status"] = "Note deleted"
    else:
        st.session_state["notes_save_status"] = "Draft discarded"
    st.session_state["notes_active_id"] = None
    st.session_state["notes_title"] = ""
    st.session_state["notes_body"] = ""
    st.session_state["notes_draft"] = False


def _save_active_note() -> None:
    note_id = st.session_state.get("notes_active_id")
    title = st.session_state.get("notes_title", "")
    body = st.session_state.get("notes_body", "")
    if not note_id and not (title.strip() or body.strip()):
        st.session_state["notes_save_status"] = "Nothing to save"
        return
    try:
        if not note_id:
            context = st.session_state.get("notes_pending_context")
            if not context:
                st.session_state["notes_save_status"] = "No note context is active"
                return
            note_id = _create_note(context)
            st.session_state["notes_active_id"] = note_id
        _update_note(note_id, title, body)
        st.session_state["notes_draft"] = False
        st.session_state["notes_save_status"] = "Saved"
    except sqlite3.Error as error:
        st.session_state["notes_save_status"] = f"Save failed: {error}"


def _select_note(note: dict[str, str]) -> None:
    st.session_state["notes_active_id"] = note["note_id"]
    st.session_state["notes_active_context_key"] = (
        note.get("history_id") or note["context_key"]
    )
    st.session_state["notes_pending_context"] = {
        "history_id": note.get("history_id") or "",
        "key": note["context_key"],
        "label": note["context_label"],
    }
    st.session_state["notes_title"] = note["title"]
    st.session_state["notes_body"] = note["body"]
    st.session_state["notes_draft"] = False
    st.session_state["notes_save_status"] = ""
    st.session_state["notes_show_all"] = False


def _new_note(context: dict[str, str]) -> None:
    st.session_state["notes_active_id"] = None
    st.session_state["notes_pending_context"] = context
    st.session_state["notes_active_context_key"] = context.get("history_id") or context["key"]
    st.session_state["notes_title"] = ""
    st.session_state["notes_body"] = ""
    st.session_state["notes_draft"] = True
    st.session_state["notes_save_status"] = "Unsaved"


def _context_for_history(record: dict[str, str]) -> dict[str, str]:
    if record.get("search_type") == "Company comparison":
        label = record.get("company_name") or record.get("ticker_value") or "Comparison"
        key = (
            f"comparison:{record.get('primary_ticker', '')}:"
            f"{record.get('secondary_ticker', '')}"
        )
    else:
        ticker = record.get("primary_ticker") or record.get("ticker_value") or ""
        label = record.get("company_name") or ticker
        key = f"company:{ticker}"
    return {
        "history_id": record.get("history_id", ""),
        "key": key,
        "label": label,
    }


def get_notes_for_history_record(record: dict[str, str]) -> list[dict[str, str]]:
    """Return notes linked to a history row, including legacy context matches."""
    context = _context_for_history(record)
    return _load_notes(context["history_id"], context["key"])


def get_history_note_count(record: dict[str, str]) -> int:
    """Return the number of notes associated with a Recently Viewed row."""
    return len(get_notes_for_history_record(record))


def _render_editor(context: dict[str, str]) -> None:
    with st.form("notes_editor_form", clear_on_submit=False):
        st.text_input(
            "Title",
            key="notes_title",
            placeholder="Title",
            label_visibility="collapsed",
        )
        st.text_area(
            "Note body",
            key="notes_body",
            height=180,
            placeholder="Write your thoughts...",
            label_visibility="collapsed",
        )
        save = st.form_submit_button("Save (Ctrl+Enter)", type="primary")
        if save:
            _save_active_note()
            st.rerun()
    status = st.session_state.get("notes_save_status")
    if status:
        st.caption(status)
    st.button(
        "Delete",
        key="notes_delete_note",
        type="secondary",
        on_click=_discard_active_note,
    )


def _render_notes_popover(context: Optional[dict[str, str]]) -> None:
    """Render the compact non-blocking notes popover."""
    st.markdown(
        """
        <style>
        .st-key-notes_popover_control {
            position: fixed;
            top: 5.25rem;
            right: 1.5rem;
            z-index: 999999;
            width: 3.2rem;
        }
        .st-key-notes_popover_control button {
            width: 3.2rem;
            height: 3.2rem;
            min-height: 3.2rem;
            padding: 0;
            border-radius: 50%;
            border: 1px solid #6f9ed0;
            background: #173457;
            color: #f5f8ff;
            font-size: 1.35rem;
            box-shadow: 0 5px 18px rgba(0, 0, 0, .35);
        }
        .st-key-notes_popover_control button:hover {
            background: #245486;
            border-color: #9dc8f1;
        }
        .st-key-notes_popover {
            position: fixed;
            top: 5.25rem;
            right: 5rem;
            z-index: 999998;
        }
        .st-key-notes_popover > div {
            width: min(22rem, calc(100vw - 2rem));
        }
        .st-key-notes_popover textarea {
            resize: none;
            overflow-y: auto;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.popover(
        "📝",
        key="notes_popover_control",
        disabled=context is None,
        help="Open notes for the active search.",
        width=320,
    ):
            if context is None:
                st.info("Open a company search or comparison first.")
                return

            st.caption(context["label"])
            context_id = context.get("history_id") or context["key"]
            if (
                not st.session_state.get("notes_show_all")
                and st.session_state.get("notes_active_context_key") != context_id
            ):
                st.session_state["notes_active_id"] = None
                st.session_state["notes_active_context_key"] = context_id
            toolbar = st.container(horizontal=True, horizontal_alignment="left")
            with toolbar:
                show_all = st.button(
                    "☰",
                    key="notes_show_all_button",
                    help="Show all saved notes.",
                )
                fresh = st.button("+", key="notes_new_note", help="Start a fresh note.")

            if fresh:
                _new_note(context)
            if show_all:
                st.session_state["notes_show_all"] = not st.session_state.get(
                    "notes_show_all", False
                )

            history_id = "" if st.session_state.get("notes_show_all") else context["history_id"]
            notes = _load_notes(history_id)
            if st.session_state.get("notes_show_all"):
                if not notes:
                    st.caption("No saved notes yet.")
                for note in notes:
                    label = note["title"] or "Untitled note"
                    if st.button(
                        f"{label} · {note['context_label']}",
                        key=f"note_{note['note_id']}",
                        use_container_width=True,
                    ):
                        _select_note(note)
                        st.rerun()
            elif (
                not st.session_state.get("notes_active_id")
                and not st.session_state.get("notes_draft")
            ):
                _new_note(context)

            _render_editor(context)


def show_notes_for_history_record(record: dict[str, str]) -> None:
    """Open the most recent note saved for a Recently Viewed record."""
    context = _context_for_history(record)
    notes = get_notes_for_history_record(record)
    selected_note = notes[0] if notes else None
    if selected_note:
        _select_note(selected_note)
    else:
        st.session_state["notes_active_id"] = None
        st.session_state["notes_title"] = ""
        st.session_state["notes_body"] = ""
    st.session_state["notes_pending_context"] = context
    st.session_state["notes_history_editor_open"] = True


def _render_history_editor(context: dict[str, str]) -> None:
    """Render a fixed editor opened directly from a Recently Viewed row."""
    st.markdown(
        """
        <style>
        .st-key-notes_history_editor {
            position: fixed;
            top: 5rem;
            right: 1.5rem;
            z-index: 999997;
            width: min(22rem, calc(100vw - 2rem));
            padding: 1rem;
            border: 1px solid #49627c;
            border-radius: 0.6rem;
            background: #111e30;
            box-shadow: 0 8px 28px rgba(0, 0, 0, .45);
        }
        .st-key-notes_history_editor textarea {
            resize: none;
            overflow-y: auto;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="notes_history_editor"):
        close, heading = st.columns([1, 5], vertical_alignment="center")
        with close:
            if st.button("×", key="notes_history_editor_close"):
                st.session_state["notes_history_editor_open"] = False
                st.session_state["notes_pending_context"] = None
                st.rerun(scope="app")
        with heading:
            st.caption(context["label"])
        _render_editor(context)


def show_notes_feature() -> None:
    """Render the fixed notes trigger and non-blocking notes editor."""
    pending_context = st.session_state.get("notes_pending_context")
    if st.session_state.get("notes_history_editor_open") and pending_context:
        active_context = _active_context()
        if (
            active_context
            and active_context.get("history_id")
            and active_context["history_id"] != pending_context.get("history_id")
        ):
            st.session_state["notes_history_editor_open"] = False
            st.session_state["notes_pending_context"] = None
            st.session_state["notes_active_id"] = None
            st.session_state["notes_title"] = ""
            st.session_state["notes_body"] = ""
        else:
            _render_history_editor(pending_context)
            return
    context = (
        pending_context
        if st.session_state.get("notes_active_id") and not st.session_state.get("notes_draft")
        else _active_context()
    )
    _render_notes_popover(context)
