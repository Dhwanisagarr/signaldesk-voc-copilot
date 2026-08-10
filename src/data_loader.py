"""CSV ingestion utilities for SignalDesk feedback data."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Mapping

import pandas as pd

from src.config import (
    COLUMN_ALIASES,
    INTERNAL_COLUMNS,
    MAX_UPLOAD_SIZE_BYTES,
    OPTIONAL_CSV_COLUMNS,
    REQUIRED_CSV_COLUMNS,
    SUPPORTED_CSV_ENCODINGS,
    SUPPORTED_CSV_EXTENSIONS,
)
from src.schemas import DataQualityReport

PathLike = str | Path


class DataLoaderError(Exception):
    """Base exception for CSV ingestion errors."""


class FileTooLargeError(DataLoaderError):
    """Raised when an uploaded file exceeds the configured size limit."""


class EmptyFileError(DataLoaderError):
    """Raised when a CSV file is empty or contains only headers."""


class EncodingError(DataLoaderError):
    """Raised when CSV bytes cannot be decoded as UTF-8."""


class MissingColumnError(DataLoaderError):
    """Raised when required columns are missing after mapping."""


class AmbiguousMappingError(DataLoaderError):
    """Raised when column mapping cannot be inferred unambiguously."""


class InvalidFileTypeError(DataLoaderError):
    """Raised when the file extension is not supported."""


class MalformedCsvError(DataLoaderError):
    """Raised when CSV content cannot be parsed."""


@dataclass
class CsvReadResult:
    """Raw CSV read metadata before validation."""

    dataframe: pd.DataFrame
    encoding: str
    file_size_bytes: int
    source_name: str


@dataclass
class LoadValidationResult:
    """Complete result of loading and validating a feedback CSV."""

    all_rows: pd.DataFrame
    valid_rows: pd.DataFrame
    report: DataQualityReport


def _normalize_single_column(name: str) -> str:
    """Normalize a single column name for alias matching."""
    normalized = str(name).strip().lower()
    normalized = re.sub(r"[\s\-]+", "_", normalized)
    return normalized


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with normalized, unique column names."""
    if df.columns.duplicated().any():
        duplicated = df.columns[df.columns.duplicated()].tolist()
        raise DataLoaderError(
            f"Duplicate column names detected: {duplicated}. "
            "Please rename columns before uploading."
        )

    renamed = df.copy()
    renamed.columns = [_normalize_single_column(col) for col in renamed.columns]

    if renamed.columns.duplicated().any():
        duplicated = renamed.columns[renamed.columns.duplicated()].tolist()
        raise DataLoaderError(
            f"Column names are ambiguous after normalization: {duplicated}. "
            "Provide an explicit column mapping."
        )
    return renamed


def _resolve_source_name(source: PathLike | bytes | BinaryIO) -> str:
    if isinstance(source, (str, Path)):
        return Path(source).name
    if isinstance(source, bytes):
        return "<bytes>"
    if hasattr(source, "name") and getattr(source, "name", None):
        return Path(str(source.name)).name
    return "<memory>"


def _get_byte_size(source: PathLike | bytes | BinaryIO) -> int:
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return path.stat().st_size

    if isinstance(source, bytes):
        return len(source)

    if hasattr(source, "getvalue"):
        return len(source.getvalue())  # type: ignore[union-attr]

    if hasattr(source, "seek") and hasattr(source, "tell"):
        current = source.tell()
        source.seek(0, io.SEEK_END)
        size = source.tell()
        source.seek(current)
        return size

    raise DataLoaderError("Unable to determine size for the provided input source.")


def _read_bytes(source: PathLike | bytes | BinaryIO) -> tuple[bytes, str]:
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes(), Path(source).name

    if isinstance(source, bytes):
        return source, "<bytes>"

    if hasattr(source, "read"):
        if hasattr(source, "seek"):
            current = source.tell()
            source.seek(0)
            payload = source.read()
            source.seek(current)
        else:
            payload = source.read()
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        return payload, _resolve_source_name(source)

    raise DataLoaderError("Unsupported input source type for CSV reading.")


def _validate_extension(source_name: str) -> None:
    suffix = Path(source_name).suffix.lower()
    if suffix and suffix not in SUPPORTED_CSV_EXTENSIONS:
        raise InvalidFileTypeError(
            f"Unsupported file type '{suffix}'. Supported extensions: "
            f"{', '.join(SUPPORTED_CSV_EXTENSIONS)}."
        )


def read_csv_input(source: PathLike | bytes | BinaryIO) -> CsvReadResult:
    """Read CSV content from a path, bytes object, or file-like object."""
    source_name = _resolve_source_name(source)
    _validate_extension(source_name)

    file_size_bytes = _get_byte_size(source)
    if file_size_bytes == 0:
        raise EmptyFileError("The uploaded file is empty.")

    if file_size_bytes > MAX_UPLOAD_SIZE_BYTES:
        raise FileTooLargeError(
            f"File size {file_size_bytes} bytes exceeds the maximum allowed "
            f"size of {MAX_UPLOAD_SIZE_BYTES} bytes."
        )

    raw_bytes, resolved_name = _read_bytes(source)
    last_decode_error: Exception | None = None

    for encoding in SUPPORTED_CSV_ENCODINGS:
        try:
            text = raw_bytes.decode(encoding)
            dataframe = pd.read_csv(io.StringIO(text))
            return CsvReadResult(
                dataframe=dataframe,
                encoding="utf-8" if encoding == "utf-8-sig" else encoding,
                file_size_bytes=file_size_bytes,
                source_name=resolved_name,
            )
        except UnicodeDecodeError as exc:
            last_decode_error = exc
        except pd.errors.EmptyDataError as exc:
            raise EmptyFileError("The uploaded file is empty.") from exc
        except pd.errors.ParserError as exc:
            raise MalformedCsvError(f"Malformed CSV file: {exc}") from exc

    message = (
        "Unable to decode CSV using supported UTF-8 encodings. "
        "Please save the file as UTF-8 or UTF-8 with BOM."
    )
    if last_decode_error is not None:
        message = f"{message} Details: {last_decode_error}"
    raise EncodingError(message)


def infer_column_mapping(df: pd.DataFrame) -> dict[str, str]:
    """Infer a mapping from source columns to internal schema fields."""
    normalized_df = normalize_column_names(df)
    source_columns = list(normalized_df.columns)

    candidates: dict[str, list[str]] = {field: [] for field in INTERNAL_COLUMNS}

    for source_col in source_columns:
        matched_fields = [
            internal_field
            for internal_field, aliases in COLUMN_ALIASES.items()
            if source_col in aliases
        ]
        if len(matched_fields) > 1:
            raise AmbiguousMappingError(
                f"Column '{source_col}' matches multiple internal fields: "
                f"{matched_fields}. Provide an explicit column mapping."
            )
        if len(matched_fields) == 1:
            candidates[matched_fields[0]].append(source_col)

    mapping: dict[str, str] = {}
    for internal_field, matched_sources in candidates.items():
        if len(matched_sources) > 1:
            raise AmbiguousMappingError(
                f"Multiple columns map to '{internal_field}': {matched_sources}. "
                "Provide an explicit column mapping."
            )
        if matched_sources:
            mapping[matched_sources[0]] = internal_field

    return mapping


def validate_column_mapping(
    df: pd.DataFrame,
    mapping: Mapping[str, str],
) -> None:
    """Validate that a column mapping covers required internal fields."""
    normalized_columns = set(normalize_column_names(df).columns)
    missing_sources = [source for source in mapping if source not in normalized_columns]
    if missing_sources:
        raise MissingColumnError(
            f"Mapping references columns not found in CSV: {missing_sources}."
        )

    mapped_internal = set(mapping.values())
    missing_required = [
        column for column in REQUIRED_CSV_COLUMNS if column not in mapped_internal
    ]
    if missing_required:
        raise MissingColumnError(
            f"Missing required columns after mapping: {missing_required}."
        )

    invalid_targets = [
        target for target in mapping.values() if target not in INTERNAL_COLUMNS
    ]
    if invalid_targets:
        raise DataLoaderError(
            f"Mapping contains unknown internal fields: {invalid_targets}."
        )

    if len(set(mapping.values())) != len(mapping.values()):
        raise AmbiguousMappingError(
            "Multiple source columns map to the same internal field."
        )


def apply_column_mapping(df: pd.DataFrame, mapping: Mapping[str, str]) -> pd.DataFrame:
    """Apply a validated mapping and retain only recognized internal columns."""
    normalized_df = normalize_column_names(df)
    validate_column_mapping(normalized_df, mapping)

    renamed = normalized_df.rename(columns=dict(mapping))
    keep_columns = [column for column in INTERNAL_COLUMNS if column in renamed.columns]
    return renamed[keep_columns].copy()


def load_feedback_csv(
    source: PathLike | bytes | BinaryIO,
    column_mapping: Mapping[str, str] | None = None,
) -> tuple[pd.DataFrame, CsvReadResult, dict[str, str]]:
    """Load a feedback CSV and apply column mapping."""
    read_result = read_csv_input(source)
    if read_result.dataframe.empty:
        raise EmptyFileError("The uploaded file contains headers only or no data rows.")

    normalized_df = normalize_column_names(read_result.dataframe)
    mapping = dict(column_mapping) if column_mapping else infer_column_mapping(normalized_df)
    mapped_df = apply_column_mapping(normalized_df, mapping)
    return mapped_df, read_result, mapping


def load_and_validate_feedback(
    source: PathLike | bytes | BinaryIO,
    column_mapping: Mapping[str, str] | None = None,
) -> LoadValidationResult:
    """Load, map, clean, and validate feedback CSV data."""
    from src.cleaner import build_data_quality_report, clean_feedback_dataframe

    mapped_df, read_result, mapping = load_feedback_csv(source, column_mapping)
    all_rows, valid_rows, row_issues = clean_feedback_dataframe(mapped_df)
    report = build_data_quality_report(
        all_rows=all_rows,
        valid_rows=valid_rows,
        row_issues=row_issues,
        read_result=read_result,
        mapping=mapping,
        original_columns=list(normalize_column_names(read_result.dataframe).columns),
    )
    return LoadValidationResult(all_rows=all_rows, valid_rows=valid_rows, report=report)
