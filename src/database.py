"""MySQL connection and schema management for Nimbus."""

from __future__ import annotations

import os
from typing import Any

import mysql.connector
import streamlit as st

DEMO_USERS = {
    "demo_user_1": "Demo user 1",
    "demo_user_2": "Demo user 2",
    "demo_user_3": "Demo user 3",
}


def _connection_settings() -> dict[str, Any]:
    """Build MySQL connection settings from environment configuration."""
    host = os.environ.get("NIMBUS_DB_HOST", "").strip()
    database_name = os.environ.get("NIMBUS_DB_NAME", "").strip()
    if not host or not database_name:
        raise RuntimeError(
            "Database configuration is missing. Set NIMBUS_DB_HOST and NIMBUS_DB_NAME."
        )

    port = int(os.environ.get("NIMBUS_DB_PORT", "3306"))
    username = os.environ.get("NIMBUS_DB_USER", "").strip()
    password = os.environ.get("NIMBUS_DB_PASSWORD", "")

    if not username or not password:
        raise RuntimeError(
            "Database credentials are missing. Set NIMBUS_DB_USER and NIMBUS_DB_PASSWORD."
        )

    settings = {
        "host": host,
        "port": port,
        "database": database_name,
        "user": username,
        "password": password,
        "connection_timeout": 10,
    }
    ca_file = os.environ.get("NIMBUS_DB_SSL_CA", "").strip()
    if ca_file:
        settings.update(
            ssl_ca=ca_file,
            ssl_verify_cert=True,
            ssl_verify_identity=True,
        )
    return settings


def connect() -> mysql.connector.MySQLConnection:
    """Open a MySQL connection using the configured database credentials."""
    return mysql.connector.connect(**_connection_settings())


@st.cache_resource(show_spinner=False)
def ensure_schema() -> bool:
    """Create MySQL tables, indexes, and demo users once per Streamlit process.

    This initializes a fresh schema; it is not a versioned migration system for
    changing an already-deployed schema.
    """
    statements = (
        """
        CREATE TABLE IF NOT EXISTS demo_users (
            user_id VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
            display_name VARCHAR(80) NOT NULL
        ) ENGINE=InnoDB
        """,
        """
        CREATE TABLE IF NOT EXISTS search_history (
            search_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
            user_id VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            timestamp_utc DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            search_type VARCHAR(16) NOT NULL,
            primary_ticker VARCHAR(32) NOT NULL,
            secondary_ticker VARCHAR(32) NOT NULL DEFAULT '',
            primary_name VARCHAR(255) NOT NULL DEFAULT '',
            secondary_name VARCHAR(255) NOT NULL DEFAULT '',
            analysis_type VARCHAR(64) NOT NULL DEFAULT '',
            result_json JSON,
            UNIQUE KEY search_history_search_user_uq (search_id, user_id),
            KEY search_history_user_timestamp_idx (user_id, timestamp_utc),
            CONSTRAINT search_history_user_fk
                FOREIGN KEY (user_id) REFERENCES demo_users(user_id)
        ) ENGINE=InnoDB
        """,
        """
        CREATE TABLE IF NOT EXISTS notes (
            note_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
            search_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            user_id VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            title VARCHAR(255) NOT NULL,
            body TEXT NOT NULL,
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            KEY notes_user_search_updated_idx (user_id, search_id, updated_at),
            CONSTRAINT notes_user_fk
                FOREIGN KEY (user_id) REFERENCES demo_users(user_id),
            CONSTRAINT notes_search_user_fk
                FOREIGN KEY (search_id, user_id)
                REFERENCES search_history(search_id, user_id) ON DELETE CASCADE
        ) ENGINE=InnoDB
        """,
    )
    with connect() as connection:
        with connection.cursor(dictionary=True) as cursor:
            for statement in statements:
                cursor.execute(statement)
            cursor.executemany(
                """
                INSERT IGNORE INTO demo_users (user_id, display_name)
                VALUES (%s, %s)
                """,
                list(DEMO_USERS.items()),
            )
            connection.commit()
    return True
