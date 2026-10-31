"""PostgreSQL connection and schema management for Nimbus."""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
import psycopg
import streamlit as st
from psycopg.rows import dict_row

DEMO_USERS = {
    "demo_user_1": "Demo user 1",
    "demo_user_2": "Demo user 2",
    "demo_user_3": "Demo user 3",
}


@st.cache_data(ttl=300, show_spinner=False)
def _load_database_secret(secret_arn: str, region: str) -> dict[str, str]:
    """Retrieve and briefly cache the JSON database credentials from Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_arn)
    secret_string = response.get("SecretString")
    if not secret_string:
        raise RuntimeError("The configured database secret has no SecretString.")
    secret = json.loads(secret_string)
    if not isinstance(secret, dict):
        raise RuntimeError("The configured database secret must contain a JSON object.")
    return secret


def _connection_settings() -> dict[str, Any]:
    """Build connection arguments from AWS secret settings or local environment values."""
    host = os.environ.get("NIMBUS_DB_HOST", "").strip()
    database_name = os.environ.get("NIMBUS_DB_NAME", "").strip()
    if not host or not database_name:
        raise RuntimeError(
            "Database configuration is missing. Set NIMBUS_DB_HOST and NIMBUS_DB_NAME."
        )

    secret_arn = os.environ.get("NIMBUS_DB_SECRET_ARN", "").strip()
    if secret_arn:
        region = os.environ.get("NIMBUS_AWS_REGION", "").strip()
        if not region:
            raise RuntimeError("NIMBUS_AWS_REGION is required when using Secrets Manager.")
        secret = _load_database_secret(secret_arn, region)
        username = str(secret.get("username") or "").strip()
        password = str(secret.get("password") or "")
    else:
        username = os.environ.get("NIMBUS_DB_USER", "").strip()
        password = os.environ.get("NIMBUS_DB_PASSWORD", "")

    if not username or not password:
        raise RuntimeError(
            "Database credentials are missing. Configure a Secrets Manager secret or "
            "set NIMBUS_DB_USER and NIMBUS_DB_PASSWORD."
        )

    return {
        "host": host,
        "port": int(os.environ.get("NIMBUS_DB_PORT", "5432")),
        "dbname": database_name,
        "user": username,
        "password": password,
        "sslmode": os.environ.get("NIMBUS_DB_SSLMODE", "require"),
        "connect_timeout": 10,
        "row_factory": dict_row,
    }


def connect() -> psycopg.Connection:
    """Open a PostgreSQL connection using environment config and AWS credentials."""
    return psycopg.connect(**_connection_settings())


@st.cache_resource(show_spinner=False)
def ensure_schema() -> bool:
    """Create tables, indexes, and demo users once per Streamlit process.

    This initializes a fresh schema; it is not a versioned migration system for
    changing an already-deployed schema.
    """
    statements = (
        """
        CREATE TABLE IF NOT EXISTS demo_users (
            user_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS search_history (
            search_id UUID PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES demo_users(user_id),
            timestamp_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            search_type TEXT NOT NULL CHECK (search_type IN ('single', 'comparison')),
            primary_ticker TEXT NOT NULL,
            secondary_ticker TEXT NOT NULL DEFAULT '',
            primary_name TEXT NOT NULL DEFAULT '',
            secondary_name TEXT NOT NULL DEFAULT '',
            analysis_type TEXT NOT NULL DEFAULT '',
            result_json JSONB,
            UNIQUE (search_id, user_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS search_history_user_timestamp_idx
            ON search_history (user_id, timestamp_utc DESC)
        """,
        """
        CREATE TABLE IF NOT EXISTS notes (
            note_id UUID PRIMARY KEY,
            search_id UUID NOT NULL,
            user_id TEXT NOT NULL REFERENCES demo_users(user_id),
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            FOREIGN KEY (search_id, user_id)
                REFERENCES search_history(search_id, user_id) ON DELETE CASCADE
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS notes_user_search_updated_idx
            ON notes (user_id, search_id, updated_at DESC)
        """,
    )
    with connect() as connection:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
            cursor.executemany(
                """
                INSERT INTO demo_users (user_id, display_name)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                list(DEMO_USERS.items()),
            )
    return True
