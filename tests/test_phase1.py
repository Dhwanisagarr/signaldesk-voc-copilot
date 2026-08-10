"""Phase 1 foundation tests for SignalDesk."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from src.config import (
    EVALUATION_CSV_COLUMNS,
    EVALUATION_SET_PATH,
    REQUIRED_CSV_COLUMNS,
    SAMPLE_FEEDBACK_PATH,
)
from src.schemas import (
    AnalysisResult,
    EvaluationRecord,
    FeedbackRecord,
    ThemeInsight,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestSampleFeedbackCsv:
    def test_sample_feedback_can_be_read(self) -> None:
        df = pd.read_csv(SAMPLE_FEEDBACK_PATH)
        assert not df.empty

    def test_sample_feedback_has_required_columns(self) -> None:
        df = pd.read_csv(SAMPLE_FEEDBACK_PATH)
        for column in REQUIRED_CSV_COLUMNS:
            assert column in df.columns, f"Missing required column: {column}"

    def test_sample_feedback_ids_are_unique(self) -> None:
        df = pd.read_csv(SAMPLE_FEEDBACK_PATH)
        assert df["feedback_id"].is_unique

    def test_sample_feedback_text_not_empty(self) -> None:
        df = pd.read_csv(SAMPLE_FEEDBACK_PATH)
        assert df["feedback_text"].notna().all()
        assert (df["feedback_text"].astype(str).str.strip() != "").all()


class TestEvaluationSetCsv:
    def test_evaluation_set_can_be_read(self) -> None:
        df = pd.read_csv(EVALUATION_SET_PATH)
        assert not df.empty

    def test_evaluation_set_has_required_columns(self) -> None:
        df = pd.read_csv(EVALUATION_SET_PATH)
        for column in EVALUATION_CSV_COLUMNS:
            assert column in df.columns, f"Missing evaluation column: {column}"

    def test_evaluation_feedback_ids_are_unique(self) -> None:
        df = pd.read_csv(EVALUATION_SET_PATH)
        assert df["feedback_id"].is_unique

    def test_evaluation_feedback_text_not_empty(self) -> None:
        df = pd.read_csv(EVALUATION_SET_PATH)
        assert df["feedback_text"].notna().all()
        assert (df["feedback_text"].astype(str).str.strip() != "").all()


class TestFeedbackRecordSchema:
    def test_valid_feedback_record(self) -> None:
        record = FeedbackRecord(
            feedback_id="FB-001",
            feedback_text="Payment failed during checkout.",
            source="in_app",
            rating=2.0,
        )
        assert record.feedback_id == "FB-001"
        assert record.feedback_text == "Payment failed during checkout."

    def test_empty_feedback_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRecord(feedback_id="FB-001", feedback_text="   ")

    def test_empty_feedback_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRecord(feedback_id="", feedback_text="Valid text.")

    def test_invalid_rating_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRecord(feedback_id="FB-001", feedback_text="Valid text.", rating=6.0)

    def test_rating_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRecord(feedback_id="FB-001", feedback_text="Valid text.", rating=0)

    def test_rating_one_and_five_valid(self) -> None:
        low = FeedbackRecord(feedback_id="FB-001", feedback_text="Valid text.", rating=1)
        high = FeedbackRecord(feedback_id="FB-002", feedback_text="Valid text.", rating=5)
        assert low.rating == 1
        assert high.rating == 5

    def test_missing_rating_valid(self) -> None:
        record = FeedbackRecord(feedback_id="FB-001", feedback_text="Valid text.")
        assert record.rating is None


class TestEvaluationRecordSchema:
    def test_valid_evaluation_record(self) -> None:
        record = EvaluationRecord(
            feedback_id="EV-001",
            feedback_text="Payment failed at checkout.",
            expected_theme="payment_failure",
            expected_sentiment="negative",
            expected_severity="high",
            expected_product_area="payments",
        )
        assert record.expected_sentiment == "negative"
        assert record.expected_severity == "high"

    def test_invalid_sentiment_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EvaluationRecord(
                feedback_id="EV-001",
                feedback_text="Some feedback.",
                expected_theme="payment_failure",
                expected_sentiment="angry",
                expected_severity="high",
                expected_product_area="payments",
            )

    def test_invalid_severity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EvaluationRecord(
                feedback_id="EV-001",
                feedback_text="Some feedback.",
                expected_theme="payment_failure",
                expected_sentiment="negative",
                expected_severity="urgent",
                expected_product_area="payments",
            )


class TestPlaceholderSchemas:
    def test_analysis_result_validates_sentiment_and_severity(self) -> None:
        result = AnalysisResult(
            feedback_id="FB-001",
            sentiment="negative",
            theme="payment_failure",
            primary_theme="payment_failure",
            severity="high",
            confidence=0.75,
            analysis_method="local_rule_based",
        )
        assert result.confidence == 0.75

    def test_analysis_result_rejects_invalid_confidence(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisResult(
                feedback_id="FB-001",
                confidence=1.5,
            )

    def test_analysis_result_rejects_invalid_sentiment(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisResult(feedback_id="FB-001", sentiment="furious")

    def test_theme_insight_validates_percentage_and_confidence(self) -> None:
        insight = ThemeInsight(
            theme_name="payment_failure",
            mention_count=10,
            feedback_percentage=20.0,
            confidence=0.8,
        )
        assert insight.feedback_count == 10
        assert insight.mention_count == 10

    def test_theme_insight_rejects_invalid_percentage(self) -> None:
        with pytest.raises(ValidationError):
            ThemeInsight(
                theme_name="payment_failure",
                mention_count=10,
                feedback_percentage=150.0,
            )

    def test_theme_insight_rejects_negative_mention_count(self) -> None:
        with pytest.raises(ValidationError):
            ThemeInsight(
                theme_name="payment_failure",
                mention_count=-1,
                feedback_percentage=0.0,
            )


class TestProjectPaths:
    def test_data_files_exist_relative_to_project_root(self) -> None:
        assert (PROJECT_ROOT / "data" / "sample_feedback.csv").exists()
        assert (PROJECT_ROOT / "data" / "evaluation_set.csv").exists()

    def test_sample_feedback_has_at_least_50_records(self) -> None:
        df = pd.read_csv(PROJECT_ROOT / "data" / "sample_feedback.csv")
        assert len(df) >= 50

    def test_evaluation_set_has_at_least_30_records(self) -> None:
        df = pd.read_csv(PROJECT_ROOT / "data" / "evaluation_set.csv")
        assert len(df) >= 30
