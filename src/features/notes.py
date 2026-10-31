"""User-scoped notes saved explicitly against individual search records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import psycopg
import streamlit as st

from database import DEMO_USERS, connect, ensure_schema


def _validate_owner(search_id: str, user_id: str) -> UUID:
    """Validate the selected demo owner and parse the search identifier."""
    if user_id not in DEMO_USERS:
        raise ValueError("A valid demo user is required to access search notes.")
    try:
        return UUID(search_id)
    except (TypeError, ValueError) as error:
        raise ValueError("A valid saved search ID is required to access notes.") from error


def load_saved_notes(search_id: str, user_id: str) -> list[dict]:
    """Return saved notes belonging to this user and search."""
    search_uuid = _validate_owner(search_id, user_id)
    ensure_schema()
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT note_id, title, body, created_at, updated_at
                FROM notes
                WHERE search_id = %s AND user_id = %s
                ORDER BY updated_at DESC, note_id
                """,
                (search_uuid, user_id),
            )
            rows = cursor.fetchall()
    return [
        {
            **row,
            "note_id": str(row["note_id"]),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }
        for row in rows
    ]


def save_note(
    search_id: str,
    user_id: str,
    title: str,
    body: str,
    note_id: str,
    update_existing: bool,
) -> str:
    """Insert a new note or update one, only when the user explicitly saves."""
    search_uuid = _validate_owner(search_id, user_id)
    note_uuid = UUID(note_id)
    normalized_title = (title or "").strip() or "Untitled note"
    ensure_schema()
    with connect() as connection:
        with connection.cursor() as cursor:
            if update_existing:
                cursor.execute(
                    """
                    UPDATE notes
                    SET title = %s, body = %s, updated_at = %s
                    WHERE note_id = %s AND search_id = %s AND user_id = %s
                    """,
                    (
                        normalized_title,
                        body or "",
                        datetime.now().astimezone(),
                        note_uuid,
                        search_uuid,
                        user_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("This note does not belong to the selected user and search.")
            else:
                cursor.execute(
                    """
                    INSERT INTO notes (note_id, search_id, user_id, title, body)
                    SELECT %s, search_id, user_id, %s, %s
                    FROM search_history
                    WHERE search_id = %s AND user_id = %s
                    """,
                    (
                        note_uuid,
                        normalized_title,
                        body or "",
                        search_uuid,
                        user_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("This search does not belong to the selected user.")
    return str(note_uuid)


def delete_note(note_id: str, search_id: str, user_id: str) -> None:
    """Delete a saved note only when it belongs to the selected user and search."""
    search_uuid = _validate_owner(search_id, user_id)
    note_uuid = UUID(note_id)
    ensure_schema()
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM notes
                WHERE note_id = %s AND search_id = %s AND user_id = %s
                """,
                (note_uuid, search_uuid, user_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("This note does not belong to the selected user and search.")


def _context_for_current_search() -> dict[str, str] | None:
    """Return a notes context only when the current result belongs to this user."""
    user_id = st.session_state.get("current_user_id")
    selected_page = st.session_state.get("nimbus_page")

    if selected_page == "Company Search":
        result = st.session_state.get("company_search_results")
        search_id = st.session_state.get("company_search_history_id")
        owner_id = st.session_state.get("company_search_user_id")
        if result and search_id and owner_id == user_id:
            ticker = result["ticker"]
            return {
                "search_id": search_id,
                "user_id": user_id,
                "label": f'{result.get("company_name") or ticker} ({ticker})',
            }

    if selected_page == "Company Comparison":
        comparison = st.session_state.get("nimbus_comparison_results")
        search_id = st.session_state.get("nimbus_comparison_history_id")
        owner_id = st.session_state.get("nimbus_comparison_user_id")
        if comparison and search_id and owner_id == user_id:
            ticker_one, info_one, ticker_two, info_two = comparison
            name_one = info_one.get("shortName") or ticker_one
            name_two = info_two.get("shortName") or ticker_two
            return {
                "search_id": search_id,
                "user_id": user_id,
                "label": f"{name_one} vs {name_two}",
            }

    return None


def _draft_key(search_id: str, user_id: str, note_id: str) -> str:
    """Create a session-state key that keeps note drafts isolated by user and search."""
    return f"{user_id}:{search_id}:{note_id}"


def _widget_key(field: str, search_id: str, note_id: str) -> str:
    """Return a stable widget key for one note field."""
    return f"nimbus_note_{field}_{search_id}_{note_id}"


def _new_note_draft(context: dict[str, str]) -> None:
    """Add an unsaved note draft to this browser session and select it."""
    note_id = str(uuid4())
    drafts = st.session_state.setdefault("nimbus_note_drafts", {})
    drafts[_draft_key(context["search_id"], context["user_id"], note_id)] = {
        "title": "Untitled note",
        "body": "",
        "saved": False,
    }
    st.session_state[f"nimbus_active_note_{context['search_id']}"] = note_id
    st.session_state[f"nimbus_note_selector_{context['search_id']}"] = note_id
    st.session_state[f"nimbus_note_status_{context['search_id']}"] = ""


def _cache_note_draft(context: dict[str, str], note_id: str) -> None:
    """Copy current widget values into session state without writing to PostgreSQL."""
    drafts = st.session_state.setdefault("nimbus_note_drafts", {})
    key = _draft_key(context["search_id"], context["user_id"], note_id)
    draft = drafts.setdefault(key, {"saved": False})
    draft["title"] = st.session_state.get(_widget_key("title", context["search_id"], note_id), "")
    draft["body"] = st.session_state.get(_widget_key("body", context["search_id"], note_id), "")


def _show_notes_dialog(context: dict[str, str]) -> None:
    """Render selectable saved notes and drafts, persisting only explicit actions."""
    st.caption(context["label"])
    try:
        saved_notes = load_saved_notes(context["search_id"], context["user_id"])
    except (psycopg.Error, ValueError) as error:
        st.error(f"Could not load notes: {error}")
        return

    drafts = st.session_state.setdefault("nimbus_note_drafts", {})
    draft_prefix = f"{context['user_id']}:{context['search_id']}:"
    draft_notes = {
        key.rsplit(":", 1)[-1]: value
        for key, value in drafts.items()
        if key.startswith(draft_prefix)
    }
    saved_by_id = {note["note_id"]: note for note in saved_notes}
    notes_by_id = dict(saved_by_id)
    notes_by_id.update({
        note_id: {
            "note_id": note_id,
            "title": draft.get("title") or "Untitled note",
            "body": draft.get("body") or "",
            "saved": draft.get("saved", False),
        }
        for note_id, draft in draft_notes.items()
    })

    active_key = f"nimbus_active_note_{context['search_id']}"
    active_id = st.session_state.get(active_key)
    options = list(notes_by_id)
    if active_id not in options:
        active_id = options[0] if options else None
        st.session_state[active_key] = active_id

    if options:
        selector_key = f"nimbus_note_selector_{context['search_id']}"
        if st.session_state.get(selector_key) not in options:
            st.session_state[selector_key] = active_id
        active_id = st.selectbox(
            "Saved notes and drafts",
            options,
            index=options.index(st.session_state[selector_key]),
            format_func=lambda note_id: notes_by_id[note_id]["title"],
            key=selector_key,
        )
        st.session_state[active_key] = active_id
        note = notes_by_id[active_id]
        draft_key = _draft_key(context["search_id"], context["user_id"], active_id)
        if draft_key not in drafts:
            drafts[draft_key] = {
                "title": note["title"],
                "body": note["body"],
                "saved": True,
            }
        title_key = _widget_key("title", context["search_id"], active_id)
        body_key = _widget_key("body", context["search_id"], active_id)
        if title_key not in st.session_state:
            st.session_state[title_key] = drafts[draft_key]["title"]
        if body_key not in st.session_state:
            st.session_state[body_key] = drafts[draft_key]["body"]
        st.text_input(
            "Title",
            key=title_key,
            on_change=_cache_note_draft,
            args=(context, active_id),
        )
        st.text_area(
            "Note",
            key=body_key,
            height=220,
            placeholder="Write your thoughts about this search...",
            on_change=_cache_note_draft,
            args=(context, active_id),
        )
        _cache_note_draft(context, active_id)

        if st.button("Save", key=f"nimbus_note_save_{context['search_id']}"):
            try:
                saved_id = save_note(
                    context["search_id"],
                    context["user_id"],
                    st.session_state[title_key],
                    st.session_state[body_key],
                    note_id=active_id,
                    update_existing=drafts[draft_key].get("saved", False),
                )
            except (psycopg.Error, ValueError) as error:
                st.error(f"Could not save note: {error}")
            else:
                drafts[draft_key]["saved"] = True
                st.session_state[f"nimbus_note_status_{context['search_id']}"] = "Saved."
                st.rerun()

        if drafts[draft_key].get("saved") and st.button(
            "Delete note",
            key=f"nimbus_note_delete_{context['search_id']}_{active_id}",
            type="secondary",
        ):
            try:
                delete_note(active_id, context["search_id"], context["user_id"])
            except (psycopg.Error, ValueError) as error:
                st.error(f"Could not delete note: {error}")
            else:
                drafts.pop(draft_key, None)
                st.session_state.pop(title_key, None)
                st.session_state.pop(body_key, None)
                st.session_state[active_key] = None
                st.session_state[f"nimbus_note_status_{context['search_id']}"] = ""
                st.rerun()

    st.button(
        "＋ New note",
        key=f"nimbus_note_new_{context['search_id']}",
        on_click=_new_note_draft,
        args=(context,),
    )

    status = st.session_state.get(f"nimbus_note_status_{context['search_id']}")
    if status:
        st.success(status)


def _close_notes_dialog() -> None:
    """Reset dialog state after the user dismisses the notes drawer."""
    st.session_state["notes_dialog_open"] = False
    st.session_state.pop("notes_context_key", None)


@st.dialog(
    "Notes",
    width="small",
    position="right",
    on_dismiss=_close_notes_dialog,
)
def _show_notes_dialog_modal(context: dict[str, str]) -> None:
    """Display the notes editor in a dismissible side drawer."""
    _show_notes_dialog(context)


def show_saved_notes(search_id: str, user_id: str) -> None:
    """Display saved notes read-only in a Recently Viewed result dialog."""
    try:
        notes = load_saved_notes(search_id, user_id)
    except (psycopg.Error, ValueError) as error:
        st.error(f"Could not load notes for this search: {error}")
        return

    st.subheader("Saved notes")
    if not notes:
        st.info("No notes have been saved for this search.")
        return
    for note in notes:
        with st.container(border=True):
            st.markdown(f"**{note['title']}**")
            st.write(note["body"])
            st.caption(f"Updated {note['updated_at']}")


def show_notes_feature() -> None:
    """Show the Notes button only for a successfully saved current search."""
    context = _context_for_current_search()
    if context is None:
        return

    button_column = st.columns([1, 5, 1])[1]
    with button_column:
        if st.button(
            "📝 Notes",
            key="open_notes",
            width="stretch",
            help="Draft notes for this search and save them when ready.",
        ):
            st.session_state["notes_context_key"] = context["search_id"]
            st.session_state["notes_dialog_open"] = True

    if (
        st.session_state.get("notes_dialog_open")
        and st.session_state.get("notes_context_key") == context["search_id"]
    ):
        _show_notes_dialog_modal(context)
