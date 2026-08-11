"""Tests for Streamlit UI helper utilities."""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import PRIORITY_SCORE_WARNING, SAMPLE_FEEDBACK_PATH
from src.data_loader import load_and_validate_feedback
from src.ui_helpers import (
    SESSION_KEYS,
    build_feedback_explorer_dataframe,
    build_mapping_from_selections,
    clear_session_data,
    count_evidence_warnings,
    count_pii_entity_types,
    default_session_values,
    filter_feedback_explorer,
    format_review_status_label,
    format_theme_label,
    get_review_status,
    get_reviewer_note,
    get_safe_feedback_text,
    init_session_state,
    insight_display_warnings,
    pii_summary_metrics,
    priority_disclaimer,
    run_analysis_pipeline,
    set_review_status,
    set_reviewer_note,
    sync_review_store_to_session,
    theme_insights_table_rows,
    try_infer_column_mapping,
    validate_csv_filename,
)


class TestFormatting:
    def test_format_theme_label(self) -> None:
        assert format_theme_label("payment_failure") == "Payment Failure"
        assert format_theme_label("unknown") == "Unknown"

    def test_format_review_status_label(self) -> None:
        assert format_review_status_label("needs_more_evidence") == "Needs more evidence"

    def test_priority_disclaimer(self) -> None:
        assert PRIORITY_SCORE_WARNING in priority_disclaimer()


class TestSessionState:
    def test_default_session_values_cover_all_keys(self) -> None:
        defaults = default_session_values()
        assert set(defaults.keys()) == set(SESSION_KEYS)

    def test_init_and_clear_session_state(self) -> None:
        session: dict = {}
        init_session_state(session)
        session["upload_bytes"] = b"test"
        session["analysis_complete"] = True
        clear_session_data(session)
        assert session["upload_bytes"] is None
        assert session["analysis_complete"] is False


class TestColumnMapping:
    def test_try_infer_column_mapping_sample_csv(self) -> None:
        df = pd.read_csv(SAMPLE_FEEDBACK_PATH)
        mapping, error = try_infer_column_mapping(df)
        assert error is None
        assert mapping is not None
        assert "feedback_id" in mapping.values()
        assert "feedback_text" in mapping.values()

    def test_build_mapping_from_selections_requires_required_fields(self) -> None:
        with pytest.raises(ValueError, match="Missing required column mapping"):
            build_mapping_from_selections({"feedback_id": "id"})


class TestPiiSummary:
    def test_pii_summary_empty(self) -> None:
        assert pii_summary_metrics(pd.DataFrame())["records_checked"] == 0

    def test_count_pii_entity_types(self) -> None:
        df = pd.DataFrame(
            {
                "pii_entity_types": [["EMAIL"], ["EMAIL", "PHONE"], []],
            }
        )
        counts = count_pii_entity_types(df)
        assert counts["EMAIL"] == 2
        assert counts["PHONE"] == 1


class TestSafeText:
    def test_prefers_masked_text(self) -> None:
        row = pd.Series(
            {
                "masked_text": "Payment failed [EMAIL_REDACTED]",
                "feedback_text": "Payment failed user@example.com",
                "pii_detected": True,
            }
        )
        assert get_safe_feedback_text(row) == "Payment failed [EMAIL_REDACTED]"

    def test_never_returns_original_text_even_if_no_pii(self) -> None:
        row = pd.Series(
            {
                "masked_text": "Refund is slow [MASKED]",
                "feedback_text": "Refund is slow raw text user@example.com",
                "pii_detected": False,
            }
        )
        assert get_safe_feedback_text(row, prefer_masked=False) == "Refund is slow [MASKED]"


class TestFeedbackExplorer:
    @pytest.fixture()
    def pipeline_bundle(self):
        loaded = load_and_validate_feedback(SAMPLE_FEEDBACK_PATH)
        from src.pii_detector import mask_dataframe_feedback

        masked = mask_dataframe_feedback(loaded.valid_rows)
        return run_analysis_pipeline(masked)

    def test_build_explorer_excludes_original_text(self, pipeline_bundle) -> None:
        df = build_feedback_explorer_dataframe(
            pipeline_bundle.analysis,
            pipeline_bundle.masked_df,
        )
        assert "original_text" not in df.columns
        assert "masked_text" in df.columns
        assert not df.empty

    def test_filter_by_theme_and_search(self, pipeline_bundle) -> None:
        df = build_feedback_explorer_dataframe(
            pipeline_bundle.analysis,
            pipeline_bundle.masked_df,
        )
        themes = df["primary_theme"].dropna().unique().tolist()
        filtered = filter_feedback_explorer(
            df,
            primary_themes=[themes[0]],
            search_query=themes[0],
        )
        assert not filtered.empty
        assert (filtered["primary_theme"] == themes[0]).all()


class TestThemeInsightsTable:
    @pytest.fixture()
    def insights(self):
        loaded = load_and_validate_feedback(SAMPLE_FEEDBACK_PATH)
        from src.pii_detector import mask_dataframe_feedback

        masked = mask_dataframe_feedback(loaded.valid_rows)
        bundle = run_analysis_pipeline(masked)
        return bundle.insights

    def test_theme_insights_table_rows(self, insights) -> None:
        rows = theme_insights_table_rows(insights)
        assert rows
        assert "priority_score" in rows[0]
        assert "mention_count" in rows[0]

    def test_insight_display_warnings_small_sample(self, insights) -> None:
        small = next(item for item in insights if item.mention_count < 3)
        warnings = insight_display_warnings(small)
        assert any("three supporting records" in warning for warning in warnings)


class TestReviewHelpers:
    def test_set_review_status(self, tmp_path) -> None:
        db_file = tmp_path / "reviews.db"
        session: dict = {}
        init_session_state(session)
        set_review_status(session, "refund_delay", "approved", db_path=db_file)
        assert session["review_statuses"]["refund_delay"] == "approved"

    def test_review_decisions_reload_from_sqlite(self, tmp_path) -> None:
        db_file = tmp_path / "reviews.db"
        session1: dict = {}
        init_session_state(session1)
        set_review_status(session1, "kyc_problem", "rejected", db_path=db_file)
        set_reviewer_note(session1, "kyc_problem", "Note for KYC", db_path=db_file)

        session2: dict = {}
        init_session_state(session2)
        sync_review_store_to_session(session2, db_path=db_file)
        assert get_review_status(session2, "kyc_problem", db_path=db_file) == "rejected"
        assert get_reviewer_note(session2, "kyc_problem", db_path=db_file) == "Note for KYC"

    def test_clearing_session_data_does_not_delete_sqlite_db(self, tmp_path) -> None:
        db_file = tmp_path / "reviews.db"
        session: dict = {}
        init_session_state(session)
        set_review_status(session, "fees", "approved", db_path=db_file)

        # Clear session data (browser reset)
        clear_session_data(session)
        assert session["review_statuses"] == {}

        # Re-sync from SQLite DB
        sync_review_store_to_session(session, db_path=db_file)
        assert get_review_status(session, "fees", db_path=db_file) == "approved"

    def test_clear_review_store_explicit_call(self, tmp_path) -> None:
        db_file = tmp_path / "reviews.db"
        session: dict = {}
        init_session_state(session)
        set_review_status(session, "fees", "approved", db_path=db_file)

        from src.ui_helpers import clear_review_store

        cleared_count = clear_review_store(session, db_path=db_file)
        assert cleared_count == 1
        assert session["review_statuses"] == {}
        assert get_review_status(session, "fees", db_path=db_file) == "pending"


class TestPipelineIntegration:
    def test_run_analysis_pipeline_requires_masked_text(self) -> None:
        loaded = load_and_validate_feedback(SAMPLE_FEEDBACK_PATH)
        with pytest.raises(KeyError, match="masked_text"):
            run_analysis_pipeline(loaded.valid_rows)

    def test_run_analysis_pipeline_end_to_end(self) -> None:
        loaded = load_and_validate_feedback(SAMPLE_FEEDBACK_PATH)
        from src.pii_detector import mask_dataframe_feedback

        masked = mask_dataframe_feedback(loaded.valid_rows)
        bundle = run_analysis_pipeline(masked)
        assert bundle.analysis.analyzed_records > 0
        assert bundle.insights
        assert count_evidence_warnings(bundle.aggregation) >= 0


class TestUploadValidation:
    def test_validate_csv_filename(self) -> None:
        assert validate_csv_filename("feedback.csv")
        assert not validate_csv_filename("feedback.xlsx")
        assert not validate_csv_filename(None)
