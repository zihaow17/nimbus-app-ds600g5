"""Local authentication helpers for the Nimbus demo login flow."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
USERS_PATH = PROJECT_ROOT / "secrets" / "users.json"


def load_users() -> list[dict[str, str]]:
    """Return the local demo user list from the JSON secrets file."""
    if not USERS_PATH.exists():
        return []

    with USERS_PATH.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)

    users = payload.get("users") or []
    return [
        {
            "user_id": str(user.get("user_id", "")).strip(),
            "password": str(user.get("password", "")).strip(),
            "display_name": str(user.get("display_name") or user.get("user_id") or "").strip(),
        }
        for user in users
    ]


def validate_login(user_id: str, password: str) -> dict[str, str] | None:
    """Return the user record when the credentials match, otherwise None."""
    candidate_id = (user_id or "").strip()
    candidate_password = (password or "").strip()

    if not candidate_id or not candidate_password:
        return None

    for user in load_users():
        if user.get("user_id") == candidate_id and user.get("password") == candidate_password:
            return {
                "user_id": user["user_id"],
                "display_name": user.get("display_name") or user["user_id"],
            }
    return None
