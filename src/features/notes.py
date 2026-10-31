"""User-scoped notes saved explicitly against individual search records."""

from __future__ import annotations

from uuid import UUID, uuid4

import mysql.connector
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
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT note_id, title, body, created_at, updated_at
                FROM notes
                WHERE search_id = %s AND user_id = %s
                ORDER BY updated_at DESC, note_id
                """,
                (str(search_uuid), user_id),
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


def load_all_saved_notes(user_id: str) -> list[dict]:
    """Return all saved notes belonging to one demo user."""
    if user_id not in DEMO_USERS:
        raise ValueError("A valid demo user is required to access search notes.")
    ensure_schema()
    with connect() as connection:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT n.note_id, n.search_id, n.title, n.body,
                       n.created_at, n.updated_at,
                       h.search_type, h.primary_ticker, h.secondary_ticker,
                       h.primary_name, h.secondary_name
                FROM notes AS n
                INNER JOIN search_history AS h
                    ON h.search_id = n.search_id AND h.user_id = n.user_id
                WHERE n.user_id = %s
                ORDER BY n.updated_at DESC, n.note_id
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
    return [
        {
            **row,
            "note_id": str(row["note_id"]),
            "search_id": str(row["search_id"]),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }
        for row in rows
    ]


def get_history_note_count(record: dict) -> int:
    """Count notes only for the owner and search represented by a history row."""
    search_uuid = _validate_owner(record.get("search_id"), record.get("user_id"))
    ensure_schema()
    with connect() as connection:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS note_count
                FROM notes
                WHERE search_id = %s AND user_id = %s
                """,
                (str(search_uuid), record["user_id"]),
            )
            result = cursor.fetchone()
    return int(result["note_count"])


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
        with connection.cursor(dictionary=True) as cursor:
            if update_existing:
                cursor.execute(
                    """
                    SELECT note_id
                    FROM notes
                    WHERE note_id = %s AND search_id = %s AND user_id = %s
                    FOR UPDATE
                    """,
                    (str(note_uuid), str(search_uuid), user_id),
                )
                if cursor.fetchone() is None:
                    raise ValueError("This note does not belong to the selected user and search.")
                cursor.execute(
                    """
                    UPDATE notes
                    SET title = %s, body = %s, updated_at = UTC_TIMESTAMP(6)
                    WHERE note_id = %s AND search_id = %s AND user_id = %s
                    """,
                    (
                        normalized_title,
                        body or "",
                        str(note_uuid),
                        str(search_uuid),
                        user_id,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO notes (note_id, search_id, user_id, title, body)
                    SELECT %s, search_id, user_id, %s, %s
                    FROM search_history
                    WHERE search_id = %s AND user_id = %s
                    """,
                    (
                        str(note_uuid),
                        normalized_title,
                        body or "",
                        str(search_uuid),
                        user_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("This search does not belong to the selected user.")
            connection.commit()
    return str(note_uuid)


def delete_note(note_id: str, search_id: str, user_id: str) -> None:
    """Delete a saved note only when it belongs to the selected user and search."""
    search_uuid = _validate_owner(search_id, user_id)
    note_uuid = UUID(note_id)
    ensure_schema()
    with connect() as connection:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                DELETE FROM notes
                WHERE note_id = %s AND search_id = %s AND user_id = %s
                """,
                (str(note_uuid), str(search_uuid), user_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("This note does not belong to the selected user and search.")
            connection.commit()


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
    st.session_state["notes_popover_context"] = context
    st.session_state["notes_show_all"] = False


def _cache_note_draft(context: dict[str, str], note_id: str) -> None:
    """Copy current widget values into session state without writing to MySQL."""
    drafts = st.session_state.setdefault("nimbus_note_drafts", {})
    key = _draft_key(context["search_id"], context["user_id"], note_id)
    draft = drafts.setdefault(key, {"saved": False})
    draft["title"] = st.session_state.get(_widget_key("title", context["search_id"], note_id), "")
    draft["body"] = st.session_state.get(_widget_key("body", context["search_id"], note_id), "")


def _note_context(note: dict, user_id: str) -> dict[str, str]:
    """Build the user-scoped editor context represented by an all-notes row."""
    if note.get("search_type") == "Company comparison":
        name_one = note.get("primary_name") or note.get("primary_ticker") or "Company"
        name_two = note.get("secondary_name") or note.get("secondary_ticker") or "Company"
        label = f"{name_one} vs {name_two}"
    else:
        ticker = note.get("primary_ticker") or ""
        label = f'{note.get("primary_name") or ticker} ({ticker})'
    return {
        "search_id": note["search_id"],
        "user_id": user_id,
        "label": label,
    }


def _select_all_note(note: dict, user_id: str) -> None:
    """Select an all-notes row without changing its owning search."""
    context = _note_context(note, user_id)
    st.session_state["notes_popover_context"] = context
    st.session_state[f"nimbus_active_note_{context['search_id']}"] = note["note_id"]
    st.session_state[f"nimbus_note_selector_{context['search_id']}"] = note["note_id"]
    st.session_state["notes_show_all"] = False


def _show_notes_editor(context: dict[str, str]) -> None:
    """Render selectable notes and drafts, persisting only explicit actions."""
    st.caption(context["label"])
    try:
        saved_notes = load_saved_notes(context["search_id"], context["user_id"])
    except (mysql.connector.Error, ValueError) as error:
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
            placeholder="Title",
            label_visibility="collapsed",
            on_change=_cache_note_draft,
            args=(context, active_id),
        )
        st.text_area(
            "Note",
            key=body_key,
            height=180,
            placeholder="Write your thoughts...",
            label_visibility="collapsed",
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
            except (mysql.connector.Error, ValueError) as error:
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
            except (mysql.connector.Error, ValueError) as error:
                st.error(f"Could not delete note: {error}")
            else:
                drafts.pop(draft_key, None)
                st.session_state.pop(title_key, None)
                st.session_state.pop(body_key, None)
                st.session_state[active_key] = None
                st.session_state[f"nimbus_note_status_{context['search_id']}"] = ""
                st.rerun()

    status = st.session_state.get(f"nimbus_note_status_{context['search_id']}")
    if status:
        st.success(status)


def show_saved_notes(search_id: str, user_id: str) -> None:
    """Display saved notes read-only in a Recently Viewed result dialog."""
    try:
        notes = load_saved_notes(search_id, user_id)
    except (mysql.connector.Error, ValueError) as error:
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
    """Show a floating, user-scoped notes popover for the active saved search."""
    context = _context_for_current_search()
    if context is None:
        return

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
        help="Open notes for the active search.",
        width=320,
    ):
        user_id = context["user_id"]
        selected_context = st.session_state.get("notes_popover_context")
        if not selected_context or selected_context["user_id"] != user_id:
            selected_context = context
            st.session_state["notes_popover_context"] = context

        st.caption(selected_context["label"])
        toolbar = st.container(horizontal=True, horizontal_alignment="left")
        with toolbar:
            show_all = st.button(
                "☰",
                key="notes_show_all_button",
                help="Show all saved notes for this user.",
            )
            st.button(
                "+",
                key="notes_new_note",
                help="Start a fresh note for the active search.",
                on_click=_new_note_draft,
                args=(context,),
            )

        if show_all:
            st.session_state["notes_show_all"] = not st.session_state.get(
                "notes_show_all", False
            )
            if not st.session_state["notes_show_all"]:
                st.session_state["notes_popover_context"] = context
                selected_context = context

        if st.session_state.get("notes_show_all"):
            try:
                all_notes = load_all_saved_notes(user_id)
            except (mysql.connector.Error, ValueError) as error:
                st.error(f"Could not load all notes: {error}")
                return
            if not all_notes:
                st.caption("No saved notes yet.")
            for note in all_notes:
                label = note["title"] or "Untitled note"
                note_context = _note_context(note, user_id)
                st.button(
                    f"{label} · {note_context['label']}",
                    key=f"all_note_{note['note_id']}",
                    width="stretch",
                    on_click=_select_all_note,
                    args=(note, user_id),
                )
            selected_context = st.session_state.get("notes_popover_context")
            if not selected_context:
                return

        _show_notes_editor(selected_context)
