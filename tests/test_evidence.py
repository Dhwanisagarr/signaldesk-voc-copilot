"""Tests for Phase 5 evidence validation and theme aggregation."""

from __future__ import annotations

import pandas as pd
import pytest

from src.analysis_pipeline import analyze_feedback_dataframe
from src.config import MASKED_TEXT_REQUIRED_ERROR, PII_MASK_TOKENS, SAMPLE_FEEDBACK_PATH
from src.data_loader import load_and_validate_feedback
from src.evidence import (
    aggregate_theme_insights,
    insight_contains_forbidden_pii,
    select_representative_quotes,
    validate_quote,
    validate_theme_evidence,
)
from src.pii_detector import mask_dataframe_feedback
from src.prioritization import calculate_theme_priority, prioritize_theme_insights
from src.schemas import AnalysisResult, ThemeInsight, ThemeLabel


def _feedback_df(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _analysis(
    feedback_id: str,
    *,
    primary_theme: str = "refund_delay",
    secondary: list[str] | None = None,
    sentiment: str = "negative",
    severity: str = "high",
    confidence: float = 0.8,
) -> AnalysisResult:
    secondary_themes = [
        ThemeLabel(theme=theme, confidence=0.6, severity="medium")
        for theme in (secondary or [])
    ]
    return AnalysisResult(
        feedback_id=feedback_id,
        sentiment=sentiment,
        primary_theme=primary_theme,
        primary_confidence=confidence,
        secondary_themes=secondary_themes,
        severity=severity,
        confidence=confidence,
        analysis_method="keyword_rule",
    )


class TestValidateQuote:
    def test_exact_masked_quote_accepted(self) -> None:
        df = _feedback_df(
            [{"feedback_id": "FB-1", "masked_text": "Refund is still pending after five days."}]
        )
        result = validate_quote(
            "Refund is still pending after five days.",
            "FB-1",
            df,
            theme_name="refund_delay",
            analysis_results=[_analysis("FB-1")],
        )
        assert result.validation_status == "valid"
        assert result.quote_is_exact is True

    def test_exact_contiguous_excerpt_accepted(self) -> None:
        df = _feedback_df(
            [{"feedback_id": "FB-1", "masked_text": "Refund is still pending after five days."}]
        )
        result = validate_quote(
            "still pending",
            "FB-1",
            df,
            theme_name="refund_delay",
            analysis_results=[_analysis("FB-1")],
        )
        assert result.validation_status == "valid"
        assert result.quote_is_exact is False

    def test_invented_quote_rejected(self) -> None:
        df = _feedback_df(
            [{"feedback_id": "FB-1", "masked_text": "Refund is still pending after five days."}]
        )
        result = validate_quote(
            "Customer definitely wants a refund tracker.",
            "FB-1",
            df,
            theme_name="refund_delay",
            analysis_results=[_analysis("FB-1")],
        )
        assert result.validation_status == "invalid"

    def test_missing_feedback_id_rejected(self) -> None:
        df = _feedback_df([{"feedback_id": "FB-1", "masked_text": "Refund pending."}])
        result = validate_quote("Refund pending.", None, df)
        assert result.validation_status == "missing_feedback_id"

    def test_missing_feedback_id_in_dataframe_rejected(self) -> None:
        df = _feedback_df([{"feedback_id": "FB-1", "masked_text": "Refund pending."}])
        result = validate_quote("Refund pending.", "FB-999", df)
        assert result.validation_status == "missing_source"

    def test_original_text_never_used_for_selection(self) -> None:
        df = _feedback_df(
            [
                {
                    "feedback_id": "FB-1",
                    "masked_text": "Refund pending for [EMAIL_REDACTED].",
                    "original_text": "Refund pending for user@example.com.",
                }
            ]
        )
        result = validate_quote(
            "Refund pending for user@example.com.",
            "FB-1",
            df,
        )
        assert result.validation_status == "invalid"

    def test_masking_tokens_remain_masked(self) -> None:
        masked = f"Payment failed for {PII_MASK_TOKENS['EMAIL']}."
        df = _feedback_df([{"feedback_id": "FB-1", "masked_text": masked}])
        result = validate_quote(masked, "FB-1", df)
        assert result.validation_status == "valid"
        assert PII_MASK_TOKENS["EMAIL"] in result.quote
        assert "@" not in result.quote.replace(PII_MASK_TOKENS["EMAIL"], "")


class TestThemeAggregation:
    def test_three_records_not_weak_solely_for_exactly_three(self) -> None:
        df = _feedback_df(
            [
                {"feedback_id": f"FB-{index}", "masked_text": f"Refund pending case {index}."}
                for index in range(1, 4)
            ]
        )
        results = [_analysis(f"FB-{index}", confidence=0.7) for index in range(1, 4)]
        aggregation = aggregate_theme_insights(results, df)
        insight = aggregation.insights[0]
        assert insight.mention_count == 3
        assert insight.evidence_strength in {"moderate", "strong"}

    def test_fewer_than_three_records_is_weak(self) -> None:
        df = _feedback_df(
            [
                {"feedback_id": "FB-1", "masked_text": "Refund pending one."},
                {"feedback_id": "FB-2", "masked_text": "Refund pending two."},
            ]
        )
        results = [_analysis("FB-1"), _analysis("FB-2")]
        aggregation = aggregate_theme_insights(results, df)
        assert aggregation.insights[0].evidence_strength == "weak"

    def test_duplicate_feedback_ids_counted_once(self) -> None:
        df = _feedback_df([{"feedback_id": "FB-1", "masked_text": "Refund pending."}])
        results = [_analysis("FB-1"), _analysis("FB-1")]
        aggregation = aggregate_theme_insights(results, df)
        assert aggregation.insights[0].mention_count == 1

    def test_primary_and_secondary_count_once_for_mention_count(self) -> None:
        df = _feedback_df([{"feedback_id": "FB-1", "masked_text": "Refund pending and app slow."}])
        results = [_analysis("FB-1", primary_theme="refund_delay", secondary=["app_performance"])]
        aggregation = aggregate_theme_insights(results, df)
        refund = next(item for item in aggregation.insights if item.theme_name == "refund_delay")
        perf = next(item for item in aggregation.insights if item.theme_name == "app_performance")
        assert refund.mention_count == 1
        assert perf.mention_count == 1

    def test_primary_and_secondary_counts_are_separate(self) -> None:
        df = _feedback_df(
            [
                {"feedback_id": "FB-1", "masked_text": "Refund pending."},
                {"feedback_id": "FB-2", "masked_text": "App slow but refund also delayed."},
            ]
        )
        results = [
            _analysis("FB-1", primary_theme="refund_delay"),
            _analysis("FB-2", primary_theme="app_performance", secondary=["refund_delay"]),
        ]
        aggregation = aggregate_theme_insights(results, df)
        refund = next(item for item in aggregation.insights if item.theme_name == "refund_delay")
        assert refund.primary_count == 1
        assert refund.secondary_count == 1
        assert refund.mention_count == 2

    def test_source_feedback_ids_returned(self) -> None:
        df = _feedback_df(
            [
                {"feedback_id": "FB-1", "masked_text": "Refund pending."},
                {"feedback_id": "FB-2", "masked_text": "Refund delayed again."},
            ]
        )
        results = [_analysis("FB-1"), _analysis("FB-2")]
        aggregation = aggregate_theme_insights(results, df)
        assert aggregation.insights[0].source_feedback_ids == ["FB-1", "FB-2"]

    def test_invalid_evidence_generates_warnings(self) -> None:
        df = _feedback_df([{"feedback_id": "FB-1", "masked_text": "Refund pending."}])
        results = [_analysis("FB-1")]
        aggregation = aggregate_theme_insights(results, df)
        assert any("supporting records" in warning.lower() for warning in aggregation.insights[0].warnings)

    def test_max_three_representative_quotes(self) -> None:
        df = _feedback_df(
            [
                {
                    "feedback_id": f"FB-{index}",
                    "masked_text": f"Refund pending record {index}.",
                    "source": f"source_{index % 4}",
                }
                for index in range(1, 8)
            ]
        )
        results = [_analysis(f"FB-{index}") for index in range(1, 8)]
        quotes = select_representative_quotes("refund_delay", results, df)
        assert len(quotes) <= 3
        assert all(quote.validation_status == "valid" for quote in quotes)

    def test_empty_feedback_returns_safe_result(self) -> None:
        aggregation = aggregate_theme_insights([], _feedback_df([]))
        assert aggregation.insights == []
        assert aggregation.total_valid_feedback_records == 0
        assert aggregation.warnings

    def test_missing_masked_text_raises_clear_error(self) -> None:
        df = _feedback_df([{"feedback_id": "FB-1", "feedback_text": "Refund pending."}])
        with pytest.raises(KeyError, match=MASKED_TEXT_REQUIRED_ERROR):
            aggregate_theme_insights([], df)

    def test_theme_aggregation_counts_correct(self) -> None:
        df = _feedback_df(
            [
                {"feedback_id": "FB-1", "masked_text": "Refund pending."},
                {"feedback_id": "FB-2", "masked_text": "Refund delayed."},
                {"feedback_id": "FB-3", "masked_text": "App slow."},
            ]
        )
        results = [
            _analysis("FB-1"),
            _analysis("FB-2"),
            _analysis("FB-3", primary_theme="app_performance"),
        ]
        aggregation = aggregate_theme_insights(results, df)
        refund = next(item for item in aggregation.insights if item.theme_name == "refund_delay")
        assert refund.primary_count == 2
        assert refund.mention_count == 2
        assert refund.feedback_percentage == round((2 / 3) * 100, 2)

    def test_sentiment_distribution_correct(self) -> None:
        df = _feedback_df(
            [
                {"feedback_id": "FB-1", "masked_text": "Refund pending."},
                {"feedback_id": "FB-2", "masked_text": "Refund delayed."},
            ]
        )
        results = [
            _analysis("FB-1", sentiment="negative"),
            _analysis("FB-2", sentiment="neutral"),
        ]
        aggregation = aggregate_theme_insights(results, df)
        assert aggregation.insights[0].sentiment_distribution == {"negative": 1, "neutral": 1}

    def test_severity_distribution_correct(self) -> None:
        df = _feedback_df(
            [
                {"feedback_id": "FB-1", "masked_text": "Refund pending."},
                {"feedback_id": "FB-2", "masked_text": "Refund delayed."},
            ]
        )
        results = [_analysis("FB-1", severity="high"), _analysis("FB-2", severity="medium")]
        aggregation = aggregate_theme_insights(results, df)
        assert aggregation.insights[0].severity_distribution == {"high": 1, "medium": 1}

    def test_source_distribution_when_source_exists(self) -> None:
        df = _feedback_df(
            [
                {"feedback_id": "FB-1", "masked_text": "Refund pending.", "source": "email"},
                {"feedback_id": "FB-2", "masked_text": "Refund delayed.", "source": "in_app"},
            ]
        )
        results = [_analysis("FB-1"), _analysis("FB-2")]
        aggregation = aggregate_theme_insights(results, df)
        assert aggregation.insights[0].source_distribution == {"email": 1, "in_app": 1}

    def test_missing_optional_columns_do_not_crash(self) -> None:
        df = _feedback_df([{"feedback_id": "FB-1", "masked_text": "Refund pending."}])
        aggregation = aggregate_theme_insights([_analysis("FB-1")], df)
        assert aggregation.insights[0].segment_distribution == {}

    def test_missing_analysis_feedback_ids_create_warnings(self) -> None:
        df = _feedback_df([{"feedback_id": "FB-1", "masked_text": "Refund pending."}])
        results = [_analysis("FB-1"), _analysis("FB-999")]
        aggregation = aggregate_theme_insights(results, df)
        assert aggregation.excluded_analysis_results == 1
        assert any("FB-999" in warning for warning in aggregation.warnings)


class TestIntegration:
    def test_phase4_output_passes_to_theme_aggregation(self) -> None:
        loaded = load_and_validate_feedback(SAMPLE_FEEDBACK_PATH)
        masked = mask_dataframe_feedback(loaded.valid_rows)
        analysis = analyze_feedback_dataframe(masked)
        aggregation = aggregate_theme_insights(analysis.results, masked)
        prioritized = prioritize_theme_insights(
            aggregation.insights,
            aggregation.total_valid_feedback_records,
        )
        assert aggregation.total_valid_feedback_records > 0
        assert len(prioritized) > 0

    def test_phase3_masked_text_is_used(self) -> None:
        loaded = load_and_validate_feedback(SAMPLE_FEEDBACK_PATH)
        masked = mask_dataframe_feedback(loaded.valid_rows)
        analysis = analyze_feedback_dataframe(masked)
        aggregation = aggregate_theme_insights(analysis.results, masked)
        for insight in aggregation.insights:
            for quote in insight.evidence_quotes:
                row = masked.loc[masked["feedback_id"] == quote.feedback_id].iloc[0]
                assert quote.quote in row["masked_text"]

    def test_no_original_pii_in_theme_insights(self) -> None:
        loaded = load_and_validate_feedback(SAMPLE_FEEDBACK_PATH)
        masked = mask_dataframe_feedback(loaded.valid_rows)
        analysis = analyze_feedback_dataframe(masked)
        aggregation = aggregate_theme_insights(analysis.results, masked)
        for insight in aggregation.insights:
            assert insight_contains_forbidden_pii(insight) is False
            blob = " ".join(insight.representative_quotes)
            assert "user@example.com" not in blob
            assert "9876543210" not in blob

    def test_theme_insights_are_deterministic(self) -> None:
        loaded = load_and_validate_feedback(SAMPLE_FEEDBACK_PATH)
        masked = mask_dataframe_feedback(loaded.valid_rows)
        analysis = analyze_feedback_dataframe(masked)
        first = aggregate_theme_insights(analysis.results, masked)
        second = aggregate_theme_insights(analysis.results, masked)
        assert [item.model_dump() for item in first.insights] == [
            item.model_dump() for item in second.insights
        ]

    def test_priority_values_are_deterministic(self) -> None:
        loaded = load_and_validate_feedback(SAMPLE_FEEDBACK_PATH)
        masked = mask_dataframe_feedback(loaded.valid_rows)
        analysis = analyze_feedback_dataframe(masked)
        aggregation = aggregate_theme_insights(analysis.results, masked)
        first = prioritize_theme_insights(
            aggregation.insights,
            aggregation.total_valid_feedback_records,
        )
        second = prioritize_theme_insights(
            aggregation.insights,
            aggregation.total_valid_feedback_records,
        )
        assert [item.priority_components.model_dump() for item in first] == [
            item.priority_components.model_dump() for item in second
        ]

    def test_validate_theme_evidence_revalidates_quotes(self) -> None:
        df = _feedback_df([{"feedback_id": "FB-1", "masked_text": "Refund pending."}])
        insight = ThemeInsight(
            theme_name="refund_delay",
            representative_quotes=["Refund pending."],
            evidence_quotes=[],
            source_feedback_ids=["FB-1"],
        )
        validated = validate_theme_evidence(
            insight,
            df,
            analysis_results=[_analysis("FB-1")],
        )
        assert validated.representative_quotes == []
