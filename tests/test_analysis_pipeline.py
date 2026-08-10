"""Tests for the local analysis pipeline."""

from __future__ import annotations

import pandas as pd
import pytest

from src.analysis_pipeline import MASKED_TEXT_REQUIRED_ERROR, analyze_feedback_dataframe
from src.config import PII_MASK_TOKENS, SAMPLE_FEEDBACK_PATH
from src.data_loader import load_and_validate_feedback
from src.pii_detector import mask_dataframe_feedback

SYNTHETIC_EMAIL = "user@example.com"
SYNTHETIC_PHONE = "9876543210"


def _assert_no_pii_in_results(results) -> None:
    parts: list[str] = []
    for result in results:
        parts.extend(
            [
                str(result.customer_problem),
                " ".join(str(term) for term in result.matched_terms),
                str(result.primary_theme),
                str(result.primary_subtheme),
                str(result.product_area),
            ]
        )
    payload = " ".join(parts)
    for token in PII_MASK_TOKENS.values():
        assert token not in payload or "[REDACTED]" in token
    assert SYNTHETIC_EMAIL not in payload
    assert SYNTHETIC_PHONE not in payload


class TestAnalysisPipeline:
    def test_valid_masked_dataframe(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1"],
                "masked_text": ["Payment failed and refund is still pending."],
            }
        )
        output = analyze_feedback_dataframe(df)
        assert output.total_records == 1
        assert output.results[0].feedback_id == "FB-1"
        assert output.results[0].primary_theme != "unknown"

    def test_missing_masked_text_column(self) -> None:
        df = pd.DataFrame({"feedback_id": ["FB-1"], "feedback_text": ["Payment failed."]})
        with pytest.raises(KeyError, match="masked_text"):
            analyze_feedback_dataframe(df)

    def test_missing_masked_text_error_message(self) -> None:
        df = pd.DataFrame({"feedback_id": ["FB-1"], "feedback_text": ["Payment failed."]})
        with pytest.raises(KeyError, match=MASKED_TEXT_REQUIRED_ERROR):
            analyze_feedback_dataframe(df)

    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame(columns=["feedback_id", "masked_text"])
        output = analyze_feedback_dataframe(df)
        assert output.total_records == 0
        assert output.results == []

    def test_missing_optional_columns(self) -> None:
        df = pd.DataFrame({"feedback_id": ["FB-1"], "masked_text": ["Refund still pending."]})
        output = analyze_feedback_dataframe(df)
        assert output.results[0].primary_theme == "refund_delay"

    def test_missing_masked_text_value(self) -> None:
        df = pd.DataFrame({"feedback_id": ["FB-1"], "masked_text": [None]})
        output = analyze_feedback_dataframe(df)
        assert output.results[0].primary_theme == "unknown"
        assert output.results[0].requires_human_review is True

    def test_pii_sensitive_masked_text(self) -> None:
        masked = f"Payment failed for {PII_MASK_TOKENS['EMAIL']} and phone {PII_MASK_TOKENS['PHONE']}."
        df = pd.DataFrame({"feedback_id": ["FB-1"], "masked_text": [masked]})
        output = analyze_feedback_dataframe(df)
        _assert_no_pii_in_results(output.results)

    def test_results_retain_feedback_ids(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1", "FB-2"],
                "masked_text": ["Payment failed.", "Refund pending."],
            }
        )
        output = analyze_feedback_dataframe(df)
        assert [result.feedback_id for result in output.results] == ["FB-1", "FB-2"]

    def test_counts_are_correct(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1", "FB-2", "FB-3"],
                "masked_text": ["Payment failed.", "Refund pending.", "Okay."],
            }
        )
        output = analyze_feedback_dataframe(df)
        assert output.total_records == 3
        assert output.analyzed_records == 2
        assert output.unknown_records == 1
        assert output.human_review_records >= 1

    def test_multiple_themes_retained(self) -> None:
        text = "The app is fast, but my refund is still pending."
        df = pd.DataFrame({"feedback_id": ["FB-1"], "masked_text": [text]})
        output = analyze_feedback_dataframe(df)
        assert output.results[0].primary_theme == "refund_delay"
        assert output.results[0].secondary_themes

    def test_cluster_id_attached_without_changing_theme(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1", "FB-2"],
                "masked_text": ["Payment failed.", "Refund pending."],
            }
        )
        output = analyze_feedback_dataframe(df)
        assert output.clusters
        assert output.results[0].cluster_id is not None

    def test_end_to_end_sample_data(self) -> None:
        loaded = load_and_validate_feedback(SAMPLE_FEEDBACK_PATH)
        masked = mask_dataframe_feedback(loaded.valid_rows)
        output = analyze_feedback_dataframe(masked)
        assert output.total_records == 55
        assert output.analyzed_records > 0
        _assert_no_pii_in_results(output.results)

    def test_no_original_text_in_results_model(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1"],
                "original_text": [f"Contact {SYNTHETIC_EMAIL}"],
                "masked_text": [f"Contact {PII_MASK_TOKENS['EMAIL']}"],
            }
        )
        output = analyze_feedback_dataframe(df)
        assert "original_text" not in output.results[0].model_dump()
        _assert_no_pii_in_results(output.results)

    def test_pii_review_flag_increases_human_review(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1"],
                "masked_text": ["Payment failed."],
                "pii_review_required": [True],
            }
        )
        output = analyze_feedback_dataframe(df)
        assert output.results[0].requires_human_review is True
