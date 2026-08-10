"""Cleaning and validation helpers for ingested feedback data."""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from src.config import (
    INTERNAL_COLUMNS,
    MAX_RATING,
    MIN_RATING,
    OPTIONAL_CSV_COLUMNS,
    ROW_STATUS_ERROR,
    ROW_STATUS_VALID,
    ROW_STATUS_WARNING,
)
from src.data_loader import CsvReadResult
from src.schemas import DataQualityReport, RowIssue

OUTPUT_COLUMNS = (
    "_row_number",
    "row_status",
    "validation_errors",
    "date_normalized",
    *INTERNAL_COLUMNS,
)


def _is_missing(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _as_clean_string(value: object) -> str | None:
    if _is_missing(value):
        return None
    return str(value).strip()


def _parse_rating(value: object) -> tuple[float | None, str | None]:
    if _is_missing(value):
        return None, None
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None, f"Rating '{value}' is not numeric."
    if rating < MIN_RATING or rating > MAX_RATING:
        return None, f"Rating '{value}' is outside the allowed range {MIN_RATING:g}-{MAX_RATING:g}."
    return rating, None


def _parse_date(value: object) -> tuple[str | None, str | None]:
    if _is_missing(value):
        return None, None
    original = str(value).strip()
    parsed = pd.to_datetime(original, errors="coerce", utc=False)
    if pd.isna(parsed):
        return None, f"Date '{original}' could not be parsed."
    return parsed.date().isoformat(), None


def _issue(
    row_number: int,
    feedback_id: str | None,
    issue_type: str,
    message: str,
    severity: str,
) -> RowIssue:
    return RowIssue(
        row_number=row_number,
        feedback_id=feedback_id,
        issue_type=issue_type,
        message=message,
        severity=severity,  # type: ignore[arg-type]
    )


def clean_feedback_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[RowIssue]]:
    """Clean mapped feedback rows and return all rows, valid rows, and row issues."""
    working = df.copy()
    for column in INTERNAL_COLUMNS:
        if column not in working.columns:
            working[column] = None

    row_issues: list[RowIssue] = []
    statuses: list[str] = []
    error_messages: list[list[str]] = []

    normalized_ids: list[str | None] = []
    normalized_texts: list[str | None] = []
    normalized_ratings: list[float | None] = []
    normalized_dates: list[str | None] = []
    date_normalized_values: list[str | None] = []

    for index, row in working.iterrows():
        row_number = int(index) + 2  # account for header row and zero-based index
        messages: list[str] = []
        severity = ROW_STATUS_VALID

        feedback_id = _as_clean_string(row.get("feedback_id"))
        feedback_text = _as_clean_string(row.get("feedback_text"))

        if feedback_id is None:
            messages.append("feedback_id is empty.")
            severity = ROW_STATUS_ERROR
            row_issues.append(
                _issue(row_number, None, "empty_feedback_id", messages[-1], ROW_STATUS_ERROR)
            )

        if feedback_text is None:
            messages.append("feedback_text is empty or whitespace-only.")
            severity = ROW_STATUS_ERROR
            row_issues.append(
                _issue(
                    row_number,
                    feedback_id,
                    "empty_feedback_text",
                    messages[-1],
                    ROW_STATUS_ERROR,
                )
            )

        rating_value, rating_error = _parse_rating(row.get("rating"))
        if rating_error:
            messages.append(rating_error)
            severity = ROW_STATUS_ERROR
            row_issues.append(
                _issue(row_number, feedback_id, "invalid_rating", rating_error, ROW_STATUS_ERROR)
            )

        date_value, date_error = _parse_date(row.get("date"))
        if date_error:
            messages.append(date_error)
            if severity != ROW_STATUS_ERROR:
                severity = ROW_STATUS_WARNING
            row_issues.append(
                _issue(row_number, feedback_id, "invalid_date", date_error, ROW_STATUS_WARNING)
            )

        normalized_ids.append(feedback_id)
        normalized_texts.append(feedback_text)
        normalized_ratings.append(rating_value)
        normalized_dates.append(_as_clean_string(row.get("date")))
        date_normalized_values.append(date_value)

        statuses.append(severity)
        error_messages.append(messages)

    cleaned = working.copy()
    cleaned.insert(0, "_row_number", [int(index) + 2 for index in working.index])
    cleaned["feedback_id"] = normalized_ids
    cleaned["feedback_text"] = normalized_texts
    cleaned["rating"] = normalized_ratings
    cleaned["date"] = normalized_dates
    cleaned["date_normalized"] = date_normalized_values

    for optional_column in OPTIONAL_CSV_COLUMNS:
        if optional_column in cleaned.columns and optional_column not in {"date", "rating"}:
            cleaned[optional_column] = cleaned[optional_column].apply(
                lambda value: _as_clean_string(value)
            )

    cleaned["row_status"] = statuses
    cleaned["validation_errors"] = [
        "; ".join(messages) if messages else "" for messages in error_messages
    ]

    _append_duplicate_issues(cleaned, row_issues)

    duplicate_error_rows = {
        issue.row_number for issue in row_issues if issue.issue_type == "duplicate_feedback_id"
    }
    for idx, row_number in enumerate(cleaned["_row_number"].tolist()):
        if row_number in duplicate_error_rows and cleaned.at[cleaned.index[idx], "row_status"] != ROW_STATUS_ERROR:
            cleaned.at[cleaned.index[idx], "row_status"] = ROW_STATUS_ERROR
            existing = cleaned.at[cleaned.index[idx], "validation_errors"]
            duplicate_message = "Duplicate feedback_id detected."
            cleaned.at[cleaned.index[idx], "validation_errors"] = (
                f"{existing}; {duplicate_message}" if existing else duplicate_message
            )

    valid_rows = cleaned[cleaned["row_status"] != ROW_STATUS_ERROR].copy()
    cleaned = cleaned[list(OUTPUT_COLUMNS)].copy()
    valid_rows = valid_rows[list(OUTPUT_COLUMNS)].copy()
    return cleaned, valid_rows, row_issues


def _append_duplicate_issues(df: pd.DataFrame, row_issues: list[RowIssue]) -> None:
    """Detect duplicate IDs and duplicate text, appending issues for each affected row."""
    id_series = df["feedback_id"]
    non_null_ids = id_series.dropna()
    duplicate_ids = set(non_null_ids[non_null_ids.duplicated(keep=False)].tolist())

    for index, feedback_id in id_series.items():
        if feedback_id in duplicate_ids:
            row_number = int(index) + 2
            row_issues.append(
                _issue(
                    row_number,
                    feedback_id,
                    "duplicate_feedback_id",
                    f"Duplicate feedback_id '{feedback_id}' detected.",
                    ROW_STATUS_ERROR,
                )
            )

    text_series = df["feedback_text"].fillna("").astype(str).str.strip().str.lower()
    non_null_text = text_series[text_series != ""]
    duplicate_texts = set(non_null_text[non_null_text.duplicated(keep=False)].tolist())

    for index, feedback_text in text_series.items():
        if pd.isna(feedback_text):
            continue
        if feedback_text in duplicate_texts:
            row_number = int(index) + 2
            feedback_id = _as_clean_string(df.at[index, "feedback_id"])
            row_issues.append(
                _issue(
                    row_number,
                    feedback_id,
                    "duplicate_feedback_text",
                    "Duplicate feedback_text detected.",
                    ROW_STATUS_WARNING,
                )
            )
            if df.at[index, "row_status"] == ROW_STATUS_VALID:
                df.at[index, "row_status"] = ROW_STATUS_WARNING
                existing = df.at[index, "validation_errors"]
                warning = "Duplicate feedback_text detected."
                df.at[index, "validation_errors"] = f"{existing}; {warning}" if existing else warning


def build_data_quality_report(
    all_rows: pd.DataFrame,
    valid_rows: pd.DataFrame,
    row_issues: Iterable[RowIssue],
    read_result: CsvReadResult,
    mapping: dict[str, str],
    original_columns: list[str],
) -> DataQualityReport:
    """Build a structured data-quality report from cleaned rows and issues."""
    issues = list(row_issues)
    total_rows = len(all_rows)
    valid_count = len(valid_rows)
    invalid_count = total_rows - valid_count

    empty_feedback_rows = sum(
        1 for issue in issues if issue.issue_type == "empty_feedback_text"
    )
    duplicate_id_rows = sum(
        1 for issue in issues if issue.issue_type == "duplicate_feedback_id"
    )
    duplicate_text_rows = sum(
        1 for issue in issues if issue.issue_type == "duplicate_feedback_text"
    )
    invalid_rating_rows = sum(1 for issue in issues if issue.issue_type == "invalid_rating")
    invalid_date_rows = sum(1 for issue in issues if issue.issue_type == "invalid_date")

    mapped_internal = set(mapping.values())
    missing_required = [
        column for column in ("feedback_id", "feedback_text") if column not in mapped_internal
    ]
    missing_optional = [
        column for column in OPTIONAL_CSV_COLUMNS if column not in mapped_internal
    ]

    warnings = sorted({issue.message for issue in issues if issue.severity == ROW_STATUS_WARNING})
    errors = sorted({issue.message for issue in issues if issue.severity == ROW_STATUS_ERROR})

    return DataQualityReport(
        total_rows=total_rows,
        valid_rows=valid_count,
        invalid_rows=invalid_count,
        empty_feedback_rows=empty_feedback_rows,
        duplicate_id_rows=duplicate_id_rows,
        duplicate_text_rows=duplicate_text_rows,
        missing_required_columns=missing_required,
        missing_optional_columns=missing_optional,
        invalid_rating_rows=invalid_rating_rows,
        invalid_date_rows=invalid_date_rows,
        detected_encoding=read_result.encoding,
        file_size_bytes=read_result.file_size_bytes,
        source_name=read_result.source_name,
        warnings=warnings,
        errors=errors,
        row_issues=issues,
        detected_columns=original_columns,
        mapped_columns=dict(mapping),
    )
