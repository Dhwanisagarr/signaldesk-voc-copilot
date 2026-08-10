"""Tests for Phase 5 transparent prioritization."""

from __future__ import annotations

import pandas as pd

from src.config import PRIORITY_SCORE_WARNING
from src.evidence import aggregate_theme_insights
from src.prioritization import calculate_theme_priority, prioritize_theme_insights
from src.schemas import AnalysisResult, ThemeInsight


def _insight(
    *,
    mention_count: int = 5,
    severity_distribution: dict[str, int] | None = None,
    confidence: float = 0.8,
) -> ThemeInsight:
    return ThemeInsight(
        theme_name="refund_delay",
        mention_count=mention_count,
        feedback_percentage=50.0,
        severity_distribution=severity_distribution or {"high": mention_count},
        confidence=confidence,
    )


class TestPrioritization:
    def test_higher_frequency_increases_score(self) -> None:
        total = 10
        low = calculate_theme_priority(_insight(mention_count=2), total)
        high = calculate_theme_priority(_insight(mention_count=8), total)
        assert high.priority_score > low.priority_score

    def test_higher_severity_increases_score(self) -> None:
        total = 10
        low = calculate_theme_priority(
            _insight(severity_distribution={"low": 5}),
            total,
        )
        high = calculate_theme_priority(
            _insight(severity_distribution={"critical": 5}),
            total,
        )
        assert high.priority_score > low.priority_score

    def test_higher_confidence_increases_score(self) -> None:
        total = 10
        low = calculate_theme_priority(_insight(confidence=0.3), total)
        high = calculate_theme_priority(_insight(confidence=0.9), total)
        assert high.priority_score > low.priority_score

    def test_zero_records_no_division_by_zero(self) -> None:
        result = calculate_theme_priority(_insight(mention_count=0), 0)
        assert result.priority_score == 0.0
        assert result.frequency_score == 0.0

    def test_empty_theme_safe_result(self) -> None:
        result = calculate_theme_priority(
            ThemeInsight(theme_name="refund_delay", mention_count=0),
            10,
        )
        assert result.priority_score == 0.0

    def test_unknown_severity_excluded_from_average(self) -> None:
        with_unknown = calculate_theme_priority(
            _insight(severity_distribution={"unknown": 5}),
            10,
        )
        with_high = calculate_theme_priority(
            _insight(severity_distribution={"high": 5}),
            10,
        )
        assert with_unknown.severity_score == 0.0
        assert with_unknown.priority_score == 0.0
        assert with_high.severity_score > 0.0

    def test_score_is_deterministic(self) -> None:
        insight = _insight()
        first = calculate_theme_priority(insight, 10)
        second = calculate_theme_priority(insight, 10)
        assert first.model_dump() == second.model_dump()

    def test_component_values_returned(self) -> None:
        result = calculate_theme_priority(_insight(), 10)
        assert result.frequency_score == 0.5
        assert result.severity_score == 0.8
        assert result.confidence_score == 0.8

    def test_method_and_warning_returned(self) -> None:
        result = calculate_theme_priority(_insight(), 10)
        assert result.priority_method == "frequency_x_severity_x_confidence"
        assert result.priority_warning == PRIORITY_SCORE_WARNING

    def test_score_not_represented_as_objective_truth(self) -> None:
        result = calculate_theme_priority(_insight(), 10)
        assert "requires PM judgment" in result.priority_warning

    def test_prioritize_theme_insights_attaches_components(self) -> None:
        insights = [_insight(), _insight(mention_count=2, confidence=0.4)]
        prioritized = prioritize_theme_insights(insights, total_valid_feedback_records=10)
        assert prioritized[0].priority_components is not None
        assert prioritized[0].priority_score >= prioritized[1].priority_score

    def test_cluster_id_does_not_affect_priority(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1", "FB-2"],
                "masked_text": ["Refund pending.", "Refund delayed."],
            }
        )
        base = AnalysisResult(
            feedback_id="FB-1",
            primary_theme="refund_delay",
            primary_confidence=0.8,
            severity="high",
            confidence=0.8,
            cluster_id=None,
        )
        clustered = base.model_copy(update={"cluster_id": 99})
        aggregation_base = aggregate_theme_insights([base, clustered.model_copy(update={"feedback_id": "FB-2"})], df)
        aggregation_clustered = aggregate_theme_insights(
            [clustered, clustered.model_copy(update={"feedback_id": "FB-2"})],
            df,
        )
        priority_base = calculate_theme_priority(aggregation_base.insights[0], 2)
        priority_clustered = calculate_theme_priority(aggregation_clustered.insights[0], 2)
        assert priority_base.priority_score == priority_clustered.priority_score
