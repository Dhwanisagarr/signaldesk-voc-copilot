"""Tests for CSV ingestion utilities."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pytest

from src.config import MAX_UPLOAD_SIZE_BYTES, SAMPLE_FEEDBACK_PATH
from src.data_loader import (
    AmbiguousMappingError,
    EmptyFileError,
    EncodingError,
    FileTooLargeError,
    MissingColumnError,
    apply_column_mapping,
    infer_column_mapping,
    load_and_validate_feedback,
    load_feedback_csv,
    normalize_column_names,
    read_csv_input,
    validate_column_mapping,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _csv_bytes(content: str, encoding: str = "utf-8") -> bytes:
    return content.encode(encoding)


@pytest.fixture
def sample_csv_path() -> Path:
    return SAMPLE_FEEDBACK_PATH


class TestReadCsvInput:
    def test_read_sample_csv_from_path(self, sample_csv_path: Path) -> None:
        result = read_csv_input(sample_csv_path)
        assert not result.dataframe.empty
        assert result.encoding == "utf-8"
        assert result.file_size_bytes > 0
        assert result.source_name == "sample_feedback.csv"

    def test_read_sample_csv_from_bytesio(self, sample_csv_path: Path) -> None:
        payload = sample_csv_path.read_bytes()
        buffer = io.BytesIO(payload)
        result = read_csv_input(buffer)
        assert len(result.dataframe) == 55

    def test_read_utf8_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "utf8.csv"
        csv_path.write_text(
            "feedback_id,feedback_text\nFB-1,Payment failed.\n",
            encoding="utf-8",
        )
        result = read_csv_input(csv_path)
        assert result.encoding == "utf-8"

    def test_read_utf8_bom_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "bom.csv"
        csv_path.write_bytes(
            _csv_bytes("feedback_id,feedback_text\nFB-1,Payment failed.\n", "utf-8-sig")
        )
        result = read_csv_input(csv_path)
        assert result.encoding == "utf-8"
        assert len(result.dataframe) == 1

    def test_reject_empty_file(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "empty.csv"
        csv_path.write_bytes(b"")
        with pytest.raises(EmptyFileError):
            read_csv_input(csv_path)

    def test_reject_header_only_file(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "header_only.csv"
        csv_path.write_text("feedback_id,feedback_text\n", encoding="utf-8")
        with pytest.raises(EmptyFileError):
            load_feedback_csv(csv_path)

    def test_reject_invalid_encoding(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "latin1.csv"
        csv_path.write_bytes("feedback_id,feedback_text\nFB-1,Caf\xe9\n".encode("latin-1"))
        with pytest.raises(EncodingError):
            read_csv_input(csv_path)

    def test_reject_oversized_input(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "large.csv"
        csv_path.write_bytes(b"x" * (MAX_UPLOAD_SIZE_BYTES + 1))
        with pytest.raises(FileTooLargeError):
            read_csv_input(csv_path)


class TestColumnMapping:
    def test_map_common_alternative_column_names(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "aliases.csv"
        csv_path.write_text(
            "ticket_id,comment,channel,created_at,score,segment,city,category,lang\n"
            "T-1,Refund delayed,email,2025-01-01,2,retail,Mumbai,refunds,English\n",
            encoding="utf-8",
        )
        result = load_and_validate_feedback(csv_path)
        assert "feedback_id" in result.valid_rows.columns
        assert "feedback_text" in result.valid_rows.columns
        assert result.valid_rows.iloc[0]["feedback_id"] == "T-1"
        assert result.valid_rows.iloc[0]["source"] == "email"

    def test_detect_missing_feedback_id_column(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "missing_id.csv"
        csv_path.write_text("feedback_text\nSome feedback\n", encoding="utf-8")
        with pytest.raises(MissingColumnError):
            load_feedback_csv(csv_path)

    def test_detect_missing_feedback_text_column(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "missing_text.csv"
        csv_path.write_text("feedback_id\nFB-1\n", encoding="utf-8")
        with pytest.raises(MissingColumnError):
            load_feedback_csv(csv_path)

    def test_reject_ambiguous_column_mappings(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "ambiguous.csv"
        csv_path.write_text(
            "comment,message\nFirst,Second\n",
            encoding="utf-8",
        )
        df = read_csv_input(csv_path).dataframe
        with pytest.raises(AmbiguousMappingError):
            infer_column_mapping(df)

    def test_explicit_mapping_can_resolve_aliases(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "explicit.csv"
        csv_path.write_text(
            "comment,message\nFirst comment,Second message\n",
            encoding="utf-8",
        )
        with pytest.raises(AmbiguousMappingError):
            load_feedback_csv(csv_path)

        with pytest.raises(MissingColumnError):
            load_and_validate_feedback(
                csv_path,
                column_mapping={"comment": "feedback_text", "message": "source"},
            )

    def test_validate_column_mapping_requires_required_fields(self) -> None:
        df = pd.DataFrame({"feedback_text": ["Hello"]})
        mapping = {"feedback_text": "feedback_text"}
        with pytest.raises(MissingColumnError):
            validate_column_mapping(df, mapping)

    def test_apply_column_mapping_keeps_internal_columns(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1"],
                "feedback_text": ["Payment failed"],
                "source": ["in_app"],
            }
        )
        mapped = apply_column_mapping(df, {"feedback_id": "feedback_id", "feedback_text": "feedback_text"})
        assert list(mapped.columns) == ["feedback_id", "feedback_text", "source"]


class TestLoadAndValidateFeedback:
    def test_load_sample_csv_end_to_end(self, sample_csv_path: Path) -> None:
        result = load_and_validate_feedback(sample_csv_path)
        assert result.report.total_rows == 55
        assert result.report.valid_rows == 55
        assert result.report.invalid_rows == 0
        assert result.report.duplicate_id_rows == 0
        assert result.report.duplicate_text_rows == 0

    def test_detect_blank_feedback_text(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "blank_text.csv"
        csv_path.write_text(
            "feedback_id,feedback_text\nFB-1,   \nFB-2,Valid text\n",
            encoding="utf-8",
        )
        result = load_and_validate_feedback(csv_path)
        assert result.report.total_rows == 2
        assert result.report.valid_rows == 1
        assert result.report.invalid_rows == 1
        assert result.report.empty_feedback_rows == 1
        assert any(issue.issue_type == "empty_feedback_text" for issue in result.report.row_issues)

    def test_detect_duplicate_feedback_ids(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "dup_ids.csv"
        csv_path.write_text(
            "feedback_id,feedback_text\nFB-1,First\nFB-1,Second\nFB-2,Third\n",
            encoding="utf-8",
        )
        result = load_and_validate_feedback(csv_path)
        assert result.report.duplicate_id_rows == 2
        assert result.report.valid_rows == 1
        assert result.report.invalid_rows == 2

    def test_detect_duplicate_feedback_text(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "dup_text.csv"
        csv_path.write_text(
            "feedback_id,feedback_text\nFB-1,Same text\nFB-2,Same text\nFB-3,Unique\n",
            encoding="utf-8",
        )
        result = load_and_validate_feedback(csv_path)
        assert result.report.duplicate_text_rows == 2
        assert result.report.valid_rows == 3
        assert result.report.warnings

    def test_accept_valid_ratings(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "ratings.csv"
        csv_path.write_text(
            "feedback_id,feedback_text,rating\n"
            "FB-1,Good,5\nFB-2,Okay,3\nFB-3,Bad,1\n",
            encoding="utf-8",
        )
        result = load_and_validate_feedback(csv_path)
        assert result.report.invalid_rating_rows == 0
        assert result.report.valid_rows == 3

    def test_detect_invalid_ratings(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "bad_ratings.csv"
        csv_path.write_text(
            "feedback_id,feedback_text,rating\n"
            "FB-1,Bad rating,6\nFB-2,Not numeric,abc\n",
            encoding="utf-8",
        )
        result = load_and_validate_feedback(csv_path)
        assert result.report.invalid_rating_rows == 2
        assert result.report.valid_rows == 0

    def test_accept_valid_dates(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "dates.csv"
        csv_path.write_text(
            "feedback_id,feedback_text,date\nFB-1,Payment failed,2025-01-15\n",
            encoding="utf-8",
        )
        result = load_and_validate_feedback(csv_path)
        assert result.report.invalid_date_rows == 0
        assert result.valid_rows.iloc[0]["date_normalized"] == "2025-01-15"

    def test_detect_invalid_dates(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "bad_dates.csv"
        csv_path.write_text(
            "feedback_id,feedback_text,date\n"
            "FB-1,Payment failed,not-a-date\n",
            encoding="utf-8",
        )
        result = load_and_validate_feedback(csv_path)
        assert result.report.invalid_date_rows == 1
        assert result.report.valid_rows == 1

    def test_missing_optional_columns_do_not_fail(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "required_only.csv"
        csv_path.write_text(
            "feedback_id,feedback_text\nFB-1,Payment failed\n",
            encoding="utf-8",
        )
        result = load_and_validate_feedback(csv_path)
        assert result.report.valid_rows == 1
        assert "source" in result.report.missing_optional_columns

    def test_preserve_row_level_issue_details(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "issues.csv"
        csv_path.write_text(
            "feedback_id,feedback_text,rating\n"
            "FB-1, ,6\n"
            "FB-2,Valid,3\n",
            encoding="utf-8",
        )
        result = load_and_validate_feedback(csv_path)
        assert len(result.report.row_issues) >= 2
        assert result.all_rows.shape[0] == result.report.total_rows
        invalid_row = result.all_rows[result.all_rows["feedback_id"] == "FB-1"].iloc[0]
        assert invalid_row["row_status"] == "error"
        assert invalid_row["validation_errors"]

    def test_no_silent_row_removal(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "mixed.csv"
        csv_path.write_text(
            "feedback_id,feedback_text\n"
            "FB-1,Valid row\n"
            "FB-2, \n"
            "FB-3,Another valid row\n",
            encoding="utf-8",
        )
        result = load_and_validate_feedback(csv_path)
        assert len(result.all_rows) == 3
        assert result.report.valid_rows == 2
        assert result.report.invalid_rows == 1

    def test_cleaned_dataframe_has_expected_internal_columns(self, sample_csv_path: Path) -> None:
        result = load_and_validate_feedback(sample_csv_path)
        expected = {
            "_row_number",
            "row_status",
            "validation_errors",
            "date_normalized",
            "feedback_id",
            "feedback_text",
            "source",
            "date",
            "rating",
            "user_type",
            "region",
            "product_area",
            "language",
        }
        assert expected.issubset(set(result.all_rows.columns))


class TestNormalizeColumnNames:
    def test_normalize_column_names_lowercases_and_trims(self) -> None:
        df = pd.DataFrame({" Feedback-ID ": [1], "Comment Text": ["hello"]})
        normalized = normalize_column_names(df)
        assert list(normalized.columns) == ["feedback_id", "comment_text"]

    def test_duplicate_column_names_raise_error(self) -> None:
        df = pd.DataFrame([[1, 2]], columns=["feedback_id", "feedback_id"])
        with pytest.raises(Exception):
            normalize_column_names(df)
