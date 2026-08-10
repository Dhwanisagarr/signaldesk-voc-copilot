"""Tests for feedback cleaning and data-quality reporting."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.cleaner import build_data_quality_report, clean_feedback_dataframe
from src.config import ROW_STATUS_ERROR, ROW_STATUS_VALID, ROW_STATUS_WARNING
from src.data_loader import CsvReadResult, read_csv_input
from src.schemas import DataQualityReport, RowIssue

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def mapped_sample_df() -> pd.DataFrame:
    csv_path = PROJECT_ROOT / "data" / "sample_feedback.csv"
    return pd.read_csv(csv_path)


class TestCleanFeedbackDataframe:
    def test_clean_sample_dataframe(self, mapped_sample_df: pd.DataFrame) -> None:
        all_rows, valid_rows, issues = clean_feedback_dataframe(mapped_sample_df)
        assert len(all_rows) == len(mapped_sample_df)
        assert len(valid_rows) == len(mapped_sample_df)
        assert issues == []

    def test_blank_feedback_text_marked_invalid(self) -> None:
        df = pd.DataFrame({"feedback_id": ["FB-1"], "feedback_text": ["   "]})
        all_rows, valid_rows, issues = clean_feedback_dataframe(df)
        assert len(valid_rows) == 0
        assert all_rows.iloc[0]["row_status"] == ROW_STATUS_ERROR
        assert any(issue.issue_type == "empty_feedback_text" for issue in issues)

    def test_duplicate_id_marks_all_duplicate_rows_invalid(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1", "FB-1", "FB-2"],
                "feedback_text": ["A", "B", "C"],
            }
        )
        all_rows, valid_rows, issues = clean_feedback_dataframe(df)
        assert len(valid_rows) == 1
        assert sum(1 for issue in issues if issue.issue_type == "duplicate_feedback_id") == 2

    def test_duplicate_text_is_warning_only(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1", "FB-2"],
                "feedback_text": ["Same issue", "Same issue"],
            }
        )
        all_rows, valid_rows, issues = clean_feedback_dataframe(df)
        assert len(valid_rows) == 2
        assert all_rows.iloc[0]["row_status"] == ROW_STATUS_WARNING
        assert any(issue.issue_type == "duplicate_feedback_text" for issue in issues)

    def test_invalid_rating_marks_row_invalid(self) -> None:
        df = pd.DataFrame(
            {"feedback_id": ["FB-1"], "feedback_text": ["Bad rating"], "rating": [9]}
        )
        all_rows, valid_rows, issues = clean_feedback_dataframe(df)
        assert len(valid_rows) == 0
        assert any(issue.issue_type == "invalid_rating" for issue in issues)

    def test_valid_rating_parsed(self) -> None:
        df = pd.DataFrame(
            {"feedback_id": ["FB-1"], "feedback_text": ["Good"], "rating": ["4"]}
        )
        all_rows, valid_rows, issues = clean_feedback_dataframe(df)
        assert valid_rows.iloc[0]["rating"] == 4.0
        assert issues == []

    def test_invalid_date_is_warning(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1"],
                "feedback_text": ["Date issue"],
                "date": ["not-a-date"],
            }
        )
        all_rows, valid_rows, issues = clean_feedback_dataframe(df)
        assert len(valid_rows) == 1
        assert all_rows.iloc[0]["row_status"] == ROW_STATUS_WARNING
        assert any(issue.issue_type == "invalid_date" for issue in issues)

    def test_valid_date_normalized(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1"],
                "feedback_text": ["Date ok"],
                "date": ["2025-03-01"],
            }
        )
        all_rows, valid_rows, issues = clean_feedback_dataframe(df)
        assert valid_rows.iloc[0]["date_normalized"] == "2025-03-01"

    def test_all_rows_retained_with_status_columns(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1", "FB-2"],
                "feedback_text": ["Valid", "   "],
            }
        )
        all_rows, valid_rows, _ = clean_feedback_dataframe(df)
        assert len(all_rows) == 2
        assert "_row_number" in all_rows.columns
        assert "row_status" in all_rows.columns
        assert "validation_errors" in all_rows.columns


class TestBuildDataQualityReport:
    def test_report_counts_and_serializes(self, mapped_sample_df: pd.DataFrame) -> None:
        read_result = read_csv_input(PROJECT_ROOT / "data" / "sample_feedback.csv")
        all_rows, valid_rows, issues = clean_feedback_dataframe(mapped_sample_df)
        report = build_data_quality_report(
            all_rows=all_rows,
            valid_rows=valid_rows,
            row_issues=issues,
            read_result=read_result,
            mapping={"feedback_id": "feedback_id", "feedback_text": "feedback_text"},
            original_columns=["feedback_id", "feedback_text"],
        )
        assert isinstance(report, DataQualityReport)
        assert report.total_rows == len(mapped_sample_df)
        assert report.valid_rows == len(valid_rows)
        assert report.invalid_rows == report.total_rows - report.valid_rows
        payload = report.to_dict()
        assert payload["total_rows"] == report.total_rows
        assert "row_issues" in payload

    def test_report_includes_row_issues(self) -> None:
        issue = RowIssue(
            row_number=2,
            feedback_id="FB-1",
            issue_type="empty_feedback_text",
            message="feedback_text is empty.",
            severity="error",
        )
        read_result = CsvReadResult(
            dataframe=pd.DataFrame(),
            encoding="utf-8",
            file_size_bytes=10,
            source_name="test.csv",
        )
        all_rows = pd.DataFrame(
            {
                "_row_number": [2],
                "row_status": [ROW_STATUS_ERROR],
                "validation_errors": ["feedback_text is empty."],
                "date_normalized": [None],
                "feedback_id": ["FB-1"],
                "feedback_text": [None],
            }
        )
        report = build_data_quality_report(
            all_rows=all_rows,
            valid_rows=all_rows.iloc[0:0],
            row_issues=[issue],
            read_result=read_result,
            mapping={"feedback_id": "feedback_id", "feedback_text": "feedback_text"},
            original_columns=["feedback_id", "feedback_text"],
        )
        assert report.invalid_rows == 1
        assert report.row_issues[0].issue_type == "empty_feedback_text"
