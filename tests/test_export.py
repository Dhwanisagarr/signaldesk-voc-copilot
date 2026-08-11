"""Unit tests for export functions and privacy validation (src/export.py)."""

from __future__ import annotations

import json
import pytest
import pandas as pd

from src.config import SAMPLE_FEEDBACK_PATH
from src.data_loader import load_and_validate_feedback
from src.export import (
    ExportPrivacyError,
    export_analyzed_records_csv,
    export_markdown_report,
    export_theme_insights_csv,
    export_theme_insights_json,
    validate_export_privacy,
)
from src.pii_detector import mask_dataframe_feedback
from src.ui_helpers import run_analysis_pipeline


@pytest.fixture()
def sample_bundle():
    loaded = load_and_validate_feedback(SAMPLE_FEEDBACK_PATH)
    masked = mask_dataframe_feedback(loaded.valid_rows)
    bundle = run_analysis_pipeline(masked)
    return bundle, masked


class TestExport:
    def test_masked_analyzed_records_csv_export(self, sample_bundle) -> None:
        bundle, masked = sample_bundle
        csv_str = export_analyzed_records_csv(bundle.analysis, masked)
        assert isinstance(csv_str, str)
        assert "feedback_id" in csv_str
        assert "masked_text" in csv_str
        assert "original_text" not in csv_str
        assert "feedback_text" not in csv_str

    def test_masked_theme_insights_csv_export(self, sample_bundle) -> None:
        bundle, _ = sample_bundle
        csv_str = export_theme_insights_csv(bundle.insights)
        assert isinstance(csv_str, str)
        assert "theme_name" in csv_str
        assert "priority_score" in csv_str

    def test_masked_insight_json_export(self, sample_bundle) -> None:
        bundle, _ = sample_bundle
        json_str = export_theme_insights_json(bundle.insights, bundle.aggregation)
        parsed = json.loads(json_str)
        assert "meta" in parsed
        assert "insights" in parsed
        assert "disclaimer" in parsed["meta"]
        assert len(parsed["insights"]) > 0

    def test_masked_markdown_report_export(self, sample_bundle) -> None:
        bundle, masked = sample_bundle
        md_str = export_markdown_report(
            bundle.insights,
            analysis=bundle.analysis,
            masked_df=masked,
            aggregation=bundle.aggregation,
        )
        assert "# SignalDesk – Voice-of-Customer Executive Report" in md_str
        assert "## Dataset Summary" in md_str
        assert "## Theme Insights Overview" in md_str
        assert "## Detailed Theme Breakdown" in md_str
        assert "## Privacy Statement" in md_str
        assert "Results describe patterns in the uploaded dataset only" in md_str

    def test_empty_result_export(self, sample_bundle) -> None:
        bundle, masked = sample_bundle
        empty_analysis = bundle.analysis.model_copy(update={"results": []})
        records_csv = export_analyzed_records_csv(empty_analysis, masked)
        assert records_csv.strip() == ""

        empty_theme_csv = export_theme_insights_csv([])
        assert empty_theme_csv.strip() == ""

    def test_missing_optional_columns(self, sample_bundle) -> None:
        bundle, masked = sample_bundle
        minimal_masked = masked[["feedback_id", "masked_text"]].copy()
        csv_str = export_analyzed_records_csv(bundle.analysis, minimal_masked)
        assert "feedback_id" in csv_str
        assert "masked_text" in csv_str

    def test_preserved_feedback_ids(self, sample_bundle) -> None:
        bundle, masked = sample_bundle
        csv_str = export_analyzed_records_csv(bundle.analysis, masked)
        first_id = bundle.analysis.results[0].feedback_id
        assert first_id in csv_str

    def test_preserved_evidence_feedback_ids(self, sample_bundle) -> None:
        bundle, _ = sample_bundle
        json_str = export_theme_insights_json(bundle.insights, bundle.aggregation)
        parsed = json.loads(json_str)
        first_insight = parsed["insights"][0]
        assert "source_feedback_ids" in first_insight
        assert isinstance(first_insight["source_feedback_ids"], list)

    def test_exclusion_of_original_text(self, sample_bundle) -> None:
        bundle, masked = sample_bundle
        csv_records = export_analyzed_records_csv(bundle.analysis, masked)
        json_insights = export_theme_insights_json(bundle.insights, bundle.aggregation)
        md_report = export_markdown_report(bundle.insights, bundle.analysis, masked)

        assert "original_text" not in csv_records
        assert "original_text" not in json_insights
        assert "original_text" not in md_report

    def test_rejection_of_unmasked_email(self) -> None:
        unsafe_payload = {"text": "Contact user@example.com for help."}
        with pytest.raises(ExportPrivacyError, match="EMAIL"):
            validate_export_privacy(unsafe_payload)

    def test_rejection_of_unmasked_phone_number(self) -> None:
        unsafe_payload = {"text": "Call me at +919876543210 immediately."}
        with pytest.raises(ExportPrivacyError, match="PHONE"):
            validate_export_privacy(unsafe_payload)

    def test_rejection_of_unmasked_upi_id(self) -> None:
        unsafe_payload = {"text": "Send payment to customer@upi"}
        with pytest.raises(ExportPrivacyError, match="UPI"):
            validate_export_privacy(unsafe_payload)

    def test_acceptance_of_masking_tokens(self) -> None:
        safe_payload = {
            "text": "Contact [EMAIL_REDACTED] or [PHONE_REDACTED] or [UPI_REDACTED]."
        }
        # Should not raise any error
        validate_export_privacy(safe_payload)

    def test_inclusion_of_suggested_action_disclaimers(self, sample_bundle) -> None:
        bundle, _ = sample_bundle
        json_str = export_theme_insights_json(bundle.insights)
        parsed = json.loads(json_str)
        assert "disclaimer" in parsed["meta"]
        assert "require product-manager validation" in parsed["meta"]["disclaimer"]

    def test_inclusion_of_priority_components(self, sample_bundle) -> None:
        bundle, _ = sample_bundle
        csv_str = export_theme_insights_csv(bundle.insights)
        assert "frequency_score" in csv_str
        assert "severity_score" in csv_str
        assert "confidence_score" in csv_str

    def test_inclusion_of_review_status(self, sample_bundle) -> None:
        bundle, _ = sample_bundle
        decisions = {"payment_failure": {"status": "approved", "reviewer_note": "Approved Note"}}
        csv_str = export_theme_insights_csv(bundle.insights, decisions)
        assert "approved" in csv_str
        assert "Approved Note" in csv_str

    def test_no_raw_feedback_text_in_any_export(self, sample_bundle) -> None:
        bundle, masked = sample_bundle
        csv_records = export_analyzed_records_csv(bundle.analysis, masked)
        csv_themes = export_theme_insights_csv(bundle.insights)
        json_themes = export_theme_insights_json(bundle.insights)
        md_doc = export_markdown_report(bundle.insights)

        assert "feedback_text" not in csv_records
        assert "feedback_text" not in csv_themes
        assert "feedback_text" not in json_themes
        assert "feedback_text" not in md_doc

    def test_no_original_pii_in_any_export(self, sample_bundle) -> None:
        bundle, masked = sample_bundle
        csv_records = export_analyzed_records_csv(bundle.analysis, masked)
        # Check that synthetic email from raw sample data does not appear in export
        assert "user@example.com" not in csv_records
