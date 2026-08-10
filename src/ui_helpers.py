"""UI helper utilities for the SignalDesk Streamlit dashboard.

Business logic for loading, masking, analysis, and aggregation remains in
the dedicated ``src`` modules. This module provides formatting, filtering,
session management, and safe display helpers only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from src.analysis_pipeline import analyze_feedback_dataframe
from src.config import (
    INTERNAL_COLUMNS,
    OPTIONAL_CSV_COLUMNS,
    PRIORITY_SCORE_WARNING,
    REQUIRED_CSV_COLUMNS,
    SUPPORTED_CSV_EXTENSIONS,
    SUPPORTED_REVIEW_STATUSES,
)
from src.data_loader import (
    AmbiguousMappingError,
    infer_column_mapping,
    load_and_validate_feedback,
    normalize_column_names,
)
from src.evidence import aggregate_theme_insights
from src.pii_detector import mask_dataframe_feedback
from src.prioritization import prioritize_theme_insights
from src.schemas import AnalysisPipelineResult, AnalysisResult, ThemeAggregationResult, ThemeInsight

# Streamlit session-state keys (documented for the dashboard).
SESSION_UPLOAD_BYTES: str = "upload_bytes"
SESSION_UPLOAD_NAME: str = "upload_name"
SESSION_COLUMN_MAPPING: str = "column_mapping"
SESSION_LOAD_RESULT: str = "load_result"
SESSION_DQ_CONTINUED: str = "dq_continued"
SESSION_MASKED_DF: str = "masked_df"
SESSION_ANALYSIS: str = "analysis_result"
SESSION_AGGREGATION: str = "aggregation_result"
SESSION_THEME_INSIGHTS: str = "theme_insights"
SESSION_REVIEW_STATUSES: str = "review_statuses"
SESSION_REVIEWER_NOTES: str = "reviewer_notes"
SESSION_ANALYSIS_COMPLETE: str = "analysis_complete"
SESSION_PIPELINE_ERROR: str = "pipeline_error"
SESSION_TEMP_WARNINGS: str = "temp_warnings"

SESSION_KEYS: tuple[str, ...] = (
    SESSION_UPLOAD_BYTES,
    SESSION_UPLOAD_NAME,
    SESSION_COLUMN_MAPPING,
    SESSION_LOAD_RESULT,
    SESSION_DQ_CONTINUED,
    SESSION_MASKED_DF,
    SESSION_ANALYSIS,
    SESSION_AGGREGATION,
    SESSION_THEME_INSIGHTS,
    SESSION_REVIEW_STATUSES,
    SESSION_REVIEWER_NOTES,
    SESSION_ANALYSIS_COMPLETE,
    SESSION_PIPELINE_ERROR,
    SESSION_TEMP_WARNINGS,
)

NOT_MAPPED_LABEL: str = "— Not mapped —"

REVIEW_STATUS_LABELS: dict[str, str] = {
    "pending": "Pending",
    "approved": "Approved",
    "rejected": "Rejected",
    "needs_more_evidence": "Needs more evidence",
}


@dataclass(frozen=True)
class PipelineBundle:
    """In-memory outputs from masking through prioritization."""

    masked_df: pd.DataFrame
    analysis: AnalysisPipelineResult
    aggregation: ThemeAggregationResult
    insights: list[ThemeInsight]


def default_session_values() -> dict[str, Any]:
    """Return default values for all managed session-state keys."""
    return {
        SESSION_UPLOAD_BYTES: None,
        SESSION_UPLOAD_NAME: None,
        SESSION_COLUMN_MAPPING: None,
        SESSION_LOAD_RESULT: None,
        SESSION_DQ_CONTINUED: False,
        SESSION_MASKED_DF: None,
        SESSION_ANALYSIS: None,
        SESSION_AGGREGATION: None,
        SESSION_THEME_INSIGHTS: None,
        SESSION_REVIEW_STATUSES: {},
        SESSION_REVIEWER_NOTES: {},
        SESSION_ANALYSIS_COMPLETE: False,
        SESSION_PIPELINE_ERROR: None,
        SESSION_TEMP_WARNINGS: [],
    }


def init_session_state(session_state: Any) -> None:
    """Initialize Streamlit session state with defaults for missing keys."""
    for key, value in default_session_values().items():
        if key not in session_state:
            session_state[key] = value if not isinstance(value, dict) else dict(value)


def clear_session_data(session_state: Any) -> None:
    """Remove uploaded data, analysis outputs, and review state from the session."""
    for key, value in default_session_values().items():
        session_state[key] = value if not isinstance(value, dict) else dict(value)


def validate_csv_filename(filename: str | None) -> bool:
    """Return True when the filename has a supported CSV extension."""
    if not filename:
        return False
    lower = filename.lower()
    return any(lower.endswith(ext) for ext in SUPPORTED_CSV_EXTENSIONS)


def format_theme_label(theme_name: str) -> str:
    """Convert an internal theme slug to a readable label."""
    if not theme_name or theme_name == "unknown":
        return "Unknown"
    return theme_name.replace("_", " ").strip().title()


def format_review_status_label(status: str) -> str:
    """Return a human-readable label for a review status code."""
    return REVIEW_STATUS_LABELS.get(status, status.replace("_", " ").title())


def try_infer_column_mapping(df: pd.DataFrame) -> tuple[dict[str, str] | None, str | None]:
    """Attempt automatic column mapping; return an error message when ambiguous."""
    try:
        normalized = normalize_column_names(df)
        return infer_column_mapping(normalized), None
    except AmbiguousMappingError as exc:
        return None, str(exc)


def build_mapping_from_selections(
    selections: Mapping[str, str | None],
) -> dict[str, str]:
    """Build a source-to-internal mapping from UI selectbox values."""
    mapping: dict[str, str] = {}
    for internal_field, source_col in selections.items():
        if source_col and source_col != NOT_MAPPED_LABEL:
            mapping[source_col] = internal_field
    missing_required = [
        column for column in REQUIRED_CSV_COLUMNS if column not in mapping.values()
    ]
    if missing_required:
        raise ValueError(
            f"Missing required column mapping: {', '.join(missing_required)}."
        )
    if len(set(mapping.values())) != len(mapping.values()):
        raise ValueError("Multiple source columns map to the same internal field.")
    return mapping


def count_pii_entity_types(masked_df: pd.DataFrame) -> dict[str, int]:
    """Count detected PII entity types across a masked feedback DataFrame."""
    counts: dict[str, int] = {}
    if masked_df is None or masked_df.empty or "pii_entity_types" not in masked_df.columns:
        return counts
    for entity_list in masked_df["pii_entity_types"].tolist():
        if not isinstance(entity_list, list):
            continue
        for entity_type in entity_list:
            counts[entity_type] = counts.get(entity_type, 0) + 1
    return dict(sorted(counts.items()))


def pii_summary_metrics(masked_df: pd.DataFrame) -> dict[str, int]:
    """Return safe PII masking summary counts."""
    if masked_df is None or masked_df.empty:
        return {
            "records_checked": 0,
            "records_with_pii": 0,
            "records_requiring_review": 0,
        }
    return {
        "records_checked": len(masked_df),
        "records_with_pii": int(masked_df.get("pii_detected", pd.Series(dtype=bool)).sum()),
        "records_requiring_review": int(
            masked_df.get("pii_review_required", pd.Series(dtype=bool)).sum()
        ),
    }


def get_safe_feedback_text(row: pd.Series, *, prefer_masked: bool = True) -> str:
    """Return masked text by default; original only when no PII was detected."""
    masked = row.get("masked_text")
    if prefer_masked and isinstance(masked, str) and masked.strip():
        return masked
    pii_detected = bool(row.get("pii_detected", False))
    if pii_detected:
        return str(masked) if masked is not None else ""
    original = row.get("feedback_text") or row.get("original_text")
    return str(original) if original is not None else ""


def _secondary_themes_string(result: AnalysisResult) -> str:
    if not result.secondary_themes:
        return ""
    return ", ".join(label.theme for label in result.secondary_themes)


def build_feedback_explorer_dataframe(
    analysis: AnalysisPipelineResult,
    masked_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build a safe feedback-level table for the explorer (no original_text)."""
    if not analysis.results:
        return pd.DataFrame()

    meta = masked_df.set_index("feedback_id", drop=False) if not masked_df.empty else pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for result in analysis.results:
        row_meta = meta.loc[result.feedback_id] if result.feedback_id in meta.index else None
        if row_meta is not None and isinstance(row_meta, pd.DataFrame):
            row_meta = row_meta.iloc[0]
        rows.append(
            {
                "feedback_id": result.feedback_id,
                "source": row_meta.get("source") if row_meta is not None else None,
                "date": row_meta.get("date") if row_meta is not None else None,
                "rating": row_meta.get("rating") if row_meta is not None else None,
                "sentiment": result.sentiment,
                "primary_theme": result.primary_theme,
                "secondary_themes": _secondary_themes_string(result),
                "severity": result.severity,
                "intent": result.intent,
                "product_area": result.product_area,
                "confidence": result.confidence,
                "requires_human_review": result.requires_human_review,
                "analysis_method": result.analysis_method,
                "cluster_id": result.cluster_id,
                "pii_detected": bool(row_meta.get("pii_detected", False))
                if row_meta is not None
                else False,
                "masked_text": row_meta.get("masked_text") if row_meta is not None else "",
            }
        )
    return pd.DataFrame(rows)


def filter_feedback_explorer(
    df: pd.DataFrame,
    *,
    primary_themes: list[str] | None = None,
    sentiments: list[str] | None = None,
    severities: list[str] | None = None,
    intents: list[str] | None = None,
    sources: list[str] | None = None,
    human_review: str | None = None,
    pii_detected: str | None = None,
    analysis_methods: list[str] | None = None,
    search_query: str = "",
) -> pd.DataFrame:
    """Apply explorer filters and masked-text search."""
    if df.empty:
        return df

    filtered = df.copy()
    if primary_themes:
        filtered = filtered[filtered["primary_theme"].isin(primary_themes)]
    if sentiments:
        filtered = filtered[filtered["sentiment"].isin(sentiments)]
    if severities:
        filtered = filtered[filtered["severity"].isin(severities)]
    if intents:
        filtered = filtered[filtered["intent"].isin(intents)]
    if sources:
        filtered = filtered[filtered["source"].isin(sources)]
    if human_review == "Yes":
        filtered = filtered[filtered["requires_human_review"]]
    elif human_review == "No":
        filtered = filtered[~filtered["requires_human_review"]]
    if pii_detected == "Yes":
        filtered = filtered[filtered["pii_detected"]]
    elif pii_detected == "No":
        filtered = filtered[~filtered["pii_detected"]]
    if analysis_methods:
        filtered = filtered[filtered["analysis_method"].isin(analysis_methods)]

    query = search_query.strip().lower()
    if query:
        mask = filtered["feedback_id"].astype(str).str.lower().str.contains(query, na=False)
        mask |= filtered["masked_text"].astype(str).str.lower().str.contains(query, na=False)
        mask |= filtered["primary_theme"].astype(str).str.lower().str.contains(query, na=False)
        mask |= filtered["secondary_themes"].astype(str).str.lower().str.contains(query, na=False)
        if "source" in filtered.columns:
            mask |= filtered["source"].astype(str).str.lower().str.contains(query, na=False)
        filtered = filtered[mask]
    return filtered


def theme_insights_table_rows(
    insights: list[ThemeInsight],
    review_statuses: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Convert theme insights to display-friendly table rows."""
    statuses = review_statuses or {}
    rows: list[dict[str, Any]] = []
    for insight in insights:
        valid_quotes = sum(
            1 for quote in insight.evidence_quotes if quote.validation_status == "valid"
        )
        rows.append(
            {
                "theme_name": insight.theme_name,
                "theme_label": format_theme_label(insight.theme_name),
                "priority_score": round(insight.priority_score, 4),
                "mention_count": insight.mention_count,
                "primary_count": insight.primary_count,
                "secondary_count": insight.secondary_count,
                "feedback_percentage": round(insight.feedback_percentage, 1),
                "average_rating": insight.average_rating,
                "evidence_strength": insight.evidence_strength,
                "confidence": round(insight.confidence, 3),
                "human_review_status": statuses.get(insight.theme_name, insight.human_review_status),
                "valid_quotes": valid_quotes,
                "supporting_ids": len(insight.source_feedback_ids),
                "warnings_count": len(insight.warnings),
            }
        )
    return rows


def count_evidence_warnings(aggregation: ThemeAggregationResult | None) -> int:
    """Count aggregation-level warnings plus invalid quote rejections."""
    if aggregation is None:
        return 0
    return len(aggregation.warnings) + aggregation.invalid_quotes


def insight_display_warnings(insight: ThemeInsight) -> list[str]:
    """Return UI warnings for a theme insight based on evidence quality."""
    warnings = list(insight.warnings)
    if insight.evidence_strength == "weak":
        warnings.append("Evidence strength is weak — treat findings cautiously.")
    if insight.confidence < 0.4:
        warnings.append("Average confidence is low — classification may be unreliable.")
    if insight.mention_count < 3:
        warnings.append("Fewer than three supporting records — sample may be too small.")
    review_quotes = [
        quote
        for quote in insight.evidence_quotes
        if quote.validation_status == "requires_review"
    ]
    if review_quotes:
        warnings.append(
            f"{len(review_quotes)} quote(s) require review before use as evidence."
        )
    return warnings


def format_distribution(distribution: dict[str, int]) -> str:
    """Format a count distribution as a readable comma-separated string."""
    if not distribution:
        return "—"
    parts = [f"{key}: {value}" for key, value in sorted(distribution.items())]
    return ", ".join(parts)


def apply_masking(valid_rows: pd.DataFrame) -> pd.DataFrame:
    """Run Phase 3 masking on validated feedback rows."""
    if "feedback_text" not in valid_rows.columns:
        raise KeyError("Validated rows must include 'feedback_text' for PII masking.")
    return mask_dataframe_feedback(valid_rows)


def run_analysis_pipeline(masked_df: pd.DataFrame) -> PipelineBundle:
    """Run Phase 4 analysis and Phase 5 aggregation/prioritization on masked data."""
    if "masked_text" not in masked_df.columns:
        raise KeyError(
            "Analysis requires masked_text. Run PII masking before analysis."
        )
    analysis = analyze_feedback_dataframe(masked_df)
    aggregation = aggregate_theme_insights(analysis.results, masked_df)
    insights = prioritize_theme_insights(
        aggregation.insights,
        aggregation.total_valid_feedback_records,
    )
    return PipelineBundle(
        masked_df=masked_df,
        analysis=analysis,
        aggregation=aggregation,
        insights=insights,
    )


def get_review_status(session_state: Any, theme_name: str) -> str:
    """Return the in-memory review status for a theme."""
    statuses: dict[str, str] = session_state.get(SESSION_REVIEW_STATUSES, {})
    return statuses.get(theme_name, "pending")


def set_review_status(session_state: Any, theme_name: str, status: str) -> None:
    """Set in-memory review status after validation."""
    if status not in SUPPORTED_REVIEW_STATUSES:
        raise ValueError(f"Invalid review status: {status}")
    session_state.setdefault(SESSION_REVIEW_STATUSES, {})[theme_name] = status


def get_reviewer_note(session_state: Any, theme_name: str) -> str:
    """Return the in-memory reviewer note for a theme."""
    notes: dict[str, str] = session_state.get(SESSION_REVIEWER_NOTES, {})
    return notes.get(theme_name, "")


def set_reviewer_note(session_state: Any, theme_name: str, note: str) -> None:
    """Store an in-memory reviewer note."""
    session_state.setdefault(SESSION_REVIEWER_NOTES, {})[theme_name] = note


def load_uploaded_feedback(
    upload_bytes: bytes,
    column_mapping: Mapping[str, str] | None = None,
):
    """Load and validate uploaded CSV bytes using the data loader."""
    return load_and_validate_feedback(upload_bytes, column_mapping)


def internal_field_options() -> list[str]:
    """Return internal schema fields for mapping UI."""
    return list(INTERNAL_COLUMNS)


def optional_internal_fields() -> list[str]:
    """Return optional internal fields for mapping UI."""
    return list(OPTIONAL_CSV_COLUMNS)


def priority_disclaimer() -> str:
    """Return the standard prioritization disclaimer."""
    return PRIORITY_SCORE_WARNING
