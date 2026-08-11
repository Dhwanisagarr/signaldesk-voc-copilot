"""SQLite storage module for SignalDesk human-review decisions."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Any

from src.config import DEFAULT_DB_PATH, SUPPORTED_REVIEW_STATUSES


class ReviewStoreError(Exception):
    """Raised when SQLite review store operations fail."""


def _resolve_path(db_path: str | Path | None = None) -> Path:
    if db_path is None:
        path = DEFAULT_DB_PATH
    elif isinstance(db_path, Path):
        path = db_path
    else:
        path = Path(db_path)
    return path.resolve()


def _get_connection(db_path: Path) -> sqlite3.Connection:
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as exc:
        raise ReviewStoreError(f"Failed to connect to database at {db_path}: {exc}") from exc


def initialize_review_store(db_path: str | Path | None = None) -> Path:
    """Initialize the SQLite review store table if it does not exist."""
    path = _resolve_path(db_path)
    try:
        with _get_connection(path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_decisions (
                    theme_name TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    reviewer_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        return path
    except ReviewStoreError:
        raise
    except sqlite3.Error as exc:
        raise ReviewStoreError(f"Failed to initialize review store table: {exc}") from exc


def _validate_inputs(theme_name: str, status: str) -> None:
    if not isinstance(theme_name, str) or not theme_name.strip():
        raise ValueError("Theme name must be a non-empty string.")
    if status not in SUPPORTED_REVIEW_STATUSES:
        raise ValueError(
            f"Invalid review status: '{status}'. Allowed statuses: {SUPPORTED_REVIEW_STATUSES}"
        )


def save_review_decision(
    db_path: str | Path | None = None,
    theme_name: str = "",
    status: str = "pending",
    reviewer_note: str = "",
) -> dict[str, str]:
    """Save or update a human review decision in SQLite."""
    _validate_inputs(theme_name, status)
    path = initialize_review_store(db_path)
    theme = theme_name.strip()
    note = str(reviewer_note) if reviewer_note is not None else ""
    now_str = datetime.now(timezone.utc).isoformat()

    try:
        with _get_connection(path) as conn:
            existing = conn.execute(
                "SELECT created_at FROM review_decisions WHERE theme_name = ?",
                (theme,),
            ).fetchone()

            if existing:
                created_at = existing["created_at"]
                conn.execute(
                    """
                    UPDATE review_decisions
                    SET status = ?, reviewer_note = ?, updated_at = ?
                    WHERE theme_name = ?
                    """,
                    (status, note, now_str, theme),
                )
            else:
                created_at = now_str
                conn.execute(
                    """
                    INSERT INTO review_decisions (theme_name, status, reviewer_note, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (theme, status, note, created_at, now_str),
                )
            conn.commit()

        return {
            "theme_name": theme,
            "status": status,
            "reviewer_note": note,
            "created_at": created_at,
            "updated_at": now_str,
        }
    except sqlite3.Error as exc:
        raise ReviewStoreError(f"Failed to save review decision for '{theme}': {exc}") from exc


def get_review_decision(
    db_path: str | Path | None = None,
    theme_name: str = "",
) -> dict[str, str] | None:
    """Retrieve a single review decision by theme name."""
    if not isinstance(theme_name, str) or not theme_name.strip():
        raise ValueError("Theme name must be a non-empty string.")
    path = initialize_review_store(db_path)
    theme = theme_name.strip()

    try:
        with _get_connection(path) as conn:
            row = conn.execute(
                "SELECT theme_name, status, reviewer_note, created_at, updated_at FROM review_decisions WHERE theme_name = ?",
                (theme,),
            ).fetchone()
            if row is None:
                return None
            return dict(row)
    except sqlite3.Error as exc:
        raise ReviewStoreError(f"Failed to retrieve review decision for '{theme}': {exc}") from exc


def get_all_review_decisions(
    db_path: str | Path | None = None,
) -> dict[str, dict[str, str]]:
    """Retrieve all review decisions as a map of theme_name -> decision dict."""
    path = initialize_review_store(db_path)
    try:
        with _get_connection(path) as conn:
            rows = conn.execute(
                "SELECT theme_name, status, reviewer_note, created_at, updated_at FROM review_decisions"
            ).fetchall()
            return {row["theme_name"]: dict(row) for row in rows}
    except sqlite3.Error as exc:
        raise ReviewStoreError(f"Failed to retrieve all review decisions: {exc}") from exc


def delete_review_decision(
    db_path: str | Path | None = None,
    theme_name: str = "",
) -> bool:
    """Delete a single review decision by theme name."""
    if not isinstance(theme_name, str) or not theme_name.strip():
        raise ValueError("Theme name must be a non-empty string.")
    path = initialize_review_store(db_path)
    theme = theme_name.strip()

    try:
        with _get_connection(path) as conn:
            cursor = conn.execute(
                "DELETE FROM review_decisions WHERE theme_name = ?",
                (theme,),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as exc:
        raise ReviewStoreError(f"Failed to delete review decision for '{theme}': {exc}") from exc


def clear_review_decisions(db_path: str | Path | None = None) -> int:
    """Clear all review decisions from the store."""
    path = initialize_review_store(db_path)
    try:
        with _get_connection(path) as conn:
            cursor = conn.execute("DELETE FROM review_decisions")
            conn.commit()
            return cursor.rowcount
    except sqlite3.Error as exc:
        raise ReviewStoreError(f"Failed to clear review decisions: {exc}") from exc
