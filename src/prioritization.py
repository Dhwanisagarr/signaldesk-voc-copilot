"""Transparent prototype prioritization for theme insights."""

from __future__ import annotations

from src.analysis_config import SEVERITY_SCORES
from src.config import PRIORITY_SCORE_WARNING
from src.schemas import PriorityComponents, ThemeInsight

KNOWN_SEVERITIES: tuple[str, ...] = ("low", "medium", "high", "critical")


def _average_known_severity(severity_distribution: dict[str, int]) -> float:
    """Average severity using known labels only; unknown values are excluded."""
    total_score = 0.0
    total_count = 0
    for severity, count in severity_distribution.items():
        if severity not in KNOWN_SEVERITIES:
            continue
        total_score += SEVERITY_SCORES[severity] * count
        total_count += count
    if total_count == 0:
        return 0.0
    return total_score / total_count


def calculate_theme_priority(
    insight: ThemeInsight,
    total_valid_feedback_records: int,
) -> PriorityComponents:
    """Calculate a transparent prototype priority score for one theme insight."""
    if total_valid_feedback_records <= 0 or insight.mention_count <= 0:
        return PriorityComponents(
            priority_score=0.0,
            frequency_score=0.0,
            severity_score=0.0,
            confidence_score=0.0,
            priority_method="frequency_x_severity_x_confidence",
            priority_warning=PRIORITY_SCORE_WARNING,
        )

    frequency_score = insight.mention_count / total_valid_feedback_records
    average_severity = _average_known_severity(insight.severity_distribution)
    severity_score = average_severity / 5.0
    confidence_score = insight.confidence
    priority_score = round(frequency_score * severity_score * confidence_score, 4)

    return PriorityComponents(
        priority_score=priority_score,
        frequency_score=round(frequency_score, 4),
        severity_score=round(severity_score, 4),
        confidence_score=round(confidence_score, 4),
        priority_method="frequency_x_severity_x_confidence",
        priority_warning=PRIORITY_SCORE_WARNING,
    )


def prioritize_theme_insights(
    insights: list[ThemeInsight],
    total_valid_feedback_records: int,
) -> list[ThemeInsight]:
    """Attach transparent priority components to theme insights."""
    prioritized: list[ThemeInsight] = []
    for insight in insights:
        components = calculate_theme_priority(insight, total_valid_feedback_records)
        updated = insight.model_copy(
            update={
                "priority_score": components.priority_score,
                "priority_components": components,
            }
        )
        prioritized.append(updated)

    prioritized.sort(
        key=lambda item: (
            -(item.priority_score),
            -item.mention_count,
            item.theme_name,
        )
    )
    return prioritized
