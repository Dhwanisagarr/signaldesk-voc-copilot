"""Pydantic schemas for SignalDesk data models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.config import (
    MAX_RATING,
    MIN_RATING,
    SUPPORTED_REVIEW_STATUSES,
    SUPPORTED_SENTIMENTS,
    SUPPORTED_SEVERITIES,
)

SentimentLabel = Literal["positive", "neutral", "negative", "mixed", "unknown"]
SeverityLabel = Literal["low", "medium", "high", "critical"]
AnalysisSeverityLabel = Literal["low", "medium", "high", "critical", "unknown"]
IntentLabel = Literal["complaint", "praise", "question", "request", "bug_report", "unknown"]
AnalysisMethodLabel = Literal[
    "local_rule_based",
    "keyword_rule",
    "tfidf_fallback",
    "exploratory_cluster",
    "unknown",
]
ReviewStatus = Literal["pending", "approved", "rejected", "needs_more_evidence"]
RowIssueSeverity = Literal["valid", "warning", "error"]
EvidenceStrengthLabel = Literal["weak", "moderate", "strong"]
QuoteValidationStatus = Literal[
    "valid",
    "invalid",
    "missing_source",
    "missing_feedback_id",
    "requires_review",
]


class FeedbackRecord(BaseModel):
    """A single customer feedback item from an uploaded CSV."""

    feedback_id: str = Field(..., min_length=1)
    feedback_text: str = Field(..., min_length=1)
    source: str | None = None
    date: str | None = None
    rating: float | None = None
    user_type: str | None = None
    region: str | None = None
    product_area: str | None = None
    language: str | None = None

    @field_validator("feedback_id", "feedback_text", mode="before")
    @classmethod
    def strip_and_reject_empty(cls, value: object) -> str:
        if value is None:
            raise ValueError("Field cannot be empty.")
        text = str(value).strip()
        if not text:
            raise ValueError("Field cannot be empty.")
        return text

    @field_validator("rating", mode="before")
    @classmethod
    def parse_rating(cls, value: object) -> float | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        rating = float(value)
        if rating < MIN_RATING or rating > MAX_RATING:
            raise ValueError(f"Rating must be between {MIN_RATING:g} and {MAX_RATING:g}.")
        return rating


class EvaluationRecord(BaseModel):
    """A manually labelled record used for evaluation in future phases."""

    feedback_id: str = Field(..., min_length=1)
    feedback_text: str = Field(..., min_length=1)
    expected_theme: str = Field(..., min_length=1)
    expected_sentiment: SentimentLabel
    expected_severity: SeverityLabel
    expected_product_area: str = Field(..., min_length=1)

    @field_validator(
        "feedback_id",
        "feedback_text",
        "expected_theme",
        "expected_product_area",
        mode="before",
    )
    @classmethod
    def strip_and_reject_empty(cls, value: object) -> str:
        if value is None:
            raise ValueError("Field cannot be empty.")
        text = str(value).strip()
        if not text:
            raise ValueError("Field cannot be empty.")
        return text

    @field_validator("expected_sentiment", mode="before")
    @classmethod
    def validate_sentiment(cls, value: object) -> str:
        sentiment = str(value).strip().lower()
        if sentiment not in SUPPORTED_SENTIMENTS:
            raise ValueError(
                f"Invalid sentiment '{value}'. Must be one of: {', '.join(SUPPORTED_SENTIMENTS)}."
            )
        return sentiment

    @field_validator("expected_severity", mode="before")
    @classmethod
    def validate_severity(cls, value: object) -> str:
        severity = str(value).strip().lower()
        if severity not in SUPPORTED_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{value}'. Must be one of: {', '.join(SUPPORTED_SEVERITIES)}."
            )
        return severity


class SentimentResult(BaseModel):
    """Deterministic sentiment analysis output for masked feedback text."""

    label: SentimentLabel = "unknown"
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    positive_score: float = Field(default=0.0, ge=0.0)
    negative_score: float = Field(default=0.0, ge=0.0)
    matched_positive_terms: list[str] = Field(default_factory=list)
    matched_negative_terms: list[str] = Field(default_factory=list)
    warning: str | None = None
    method: str = "local_rule_based"


class ThemeLabel(BaseModel):
    """A detected theme assignment with per-theme metadata."""

    theme: str
    subtheme: str = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_terms: list[str] = Field(default_factory=list)
    product_area: str = "unknown"
    severity: AnalysisSeverityLabel = "unknown"
    method: str = "keyword_rule"
    warning: str | None = None


class ThemeClassification(BaseModel):
    """Primary and secondary theme classification for one feedback item."""

    primary_theme: str = "unknown"
    primary_subtheme: str = "unknown"
    primary_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    secondary_themes: list[ThemeLabel] = Field(default_factory=list)
    matched_terms_by_theme: dict[str, list[str]] = Field(default_factory=dict)
    confidence_by_theme: dict[str, float] = Field(default_factory=dict)
    product_area_by_theme: dict[str, str] = Field(default_factory=dict)
    severity_by_theme: dict[str, str] = Field(default_factory=dict)
    method: str = "keyword_rule"
    warning: str | None = None
    requires_human_review: bool = False


class AnalysisResult(BaseModel):
    """Per-item local analysis output (Phase 4)."""

    feedback_id: str = Field(..., min_length=1)
    sentiment: SentimentLabel = "unknown"
    sentiment_score: float = Field(default=0.0, ge=0.0, le=1.0)
    primary_theme: str = "unknown"
    primary_subtheme: str = "unknown"
    primary_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    secondary_themes: list[ThemeLabel] = Field(default_factory=list)
    product_area: str = "unknown"
    severity: AnalysisSeverityLabel = "unknown"
    severity_score: float = Field(default=1.0, ge=1.0, le=5.0)
    intent: IntentLabel = "unknown"
    customer_problem: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_terms: list[str] = Field(default_factory=list)
    supporting_feedback_ids: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    analysis_method: AnalysisMethodLabel = "unknown"
    analysis_warnings: list[str] = Field(default_factory=list)
    cluster_id: int | None = None
    theme: str = "unknown"  # backward-compatible alias for primary_theme

    @field_validator("sentiment", mode="before")
    @classmethod
    def validate_sentiment(cls, value: object) -> str:
        sentiment = str(value).strip().lower()
        if sentiment not in SUPPORTED_SENTIMENTS:
            raise ValueError(
                f"Invalid sentiment '{value}'. Must be one of: {', '.join(SUPPORTED_SENTIMENTS)}."
            )
        return sentiment

    @field_validator("severity", mode="before")
    @classmethod
    def validate_severity(cls, value: object) -> str:
        severity = str(value).strip().lower()
        allowed = (*SUPPORTED_SEVERITIES, "unknown")
        if severity not in allowed:
            raise ValueError(f"Invalid severity '{value}'. Must be one of: {', '.join(allowed)}.")
        return severity


class ClusterResult(BaseModel):
    """Exploratory similarity group metadata — not a confirmed product theme."""

    cluster_id: int = Field(..., ge=0)
    feedback_ids: list[str] = Field(default_factory=list)
    representative_terms: list[str] = Field(default_factory=list)
    cluster_size: int = Field(default=0, ge=0)
    warning: str | None = None


class AnalysisPipelineResult(BaseModel):
    """Batch analysis output from the local analysis pipeline."""

    results: list[AnalysisResult] = Field(default_factory=list)
    clusters: list[ClusterResult] = Field(default_factory=list)
    total_records: int = Field(default=0, ge=0)
    analyzed_records: int = Field(default=0, ge=0)
    unknown_records: int = Field(default=0, ge=0)
    human_review_records: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)


class ThemeInsight(BaseModel):
    """Theme-level aggregated insight with evidence and prioritization metadata."""

    theme_name: str = Field(..., min_length=1)
    primary_count: int = Field(default=0, ge=0)
    secondary_count: int = Field(default=0, ge=0)
    mention_count: int = Field(default=0, ge=0)
    feedback_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    average_rating: float | None = None
    sentiment_distribution: dict[str, int] = Field(default_factory=dict)
    severity_distribution: dict[str, int] = Field(default_factory=dict)
    source_distribution: dict[str, int] = Field(default_factory=dict)
    segment_distribution: dict[str, int] = Field(default_factory=dict)
    date_range: dict[str, str | None] = Field(default_factory=dict)
    trend_data: dict[str, int] = Field(default_factory=dict)
    representative_quotes: list[str] = Field(default_factory=list)
    evidence_quotes: list["EvidenceQuote"] = Field(default_factory=list)
    source_feedback_ids: list[str] = Field(default_factory=list)
    possible_root_causes: list[str] = Field(default_factory=list)
    suggested_product_actions: list[str] = Field(default_factory=list)
    evidence_strength: EvidenceStrengthLabel = "weak"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    priority_score: float = Field(default=0.0, ge=0.0)
    priority_components: "PriorityComponents | None" = None
    human_review_status: ReviewStatus = "pending"
    warnings: list[str] = Field(default_factory=list)

    # Backward-compatible alias used in Phase 1 placeholder tests.
    @property
    def feedback_count(self) -> int:
        return self.mention_count

    @field_validator("human_review_status", mode="before")
    @classmethod
    def validate_review_status(cls, value: object) -> str:
        status = str(value).strip().lower()
        if status not in SUPPORTED_REVIEW_STATUSES:
            raise ValueError(
                f"Invalid review status '{value}'. "
                f"Must be one of: {', '.join(SUPPORTED_REVIEW_STATUSES)}."
            )
        return status


class EvidenceQuote(BaseModel):
    """A validated masked quote linked to a feedback record."""

    feedback_id: str = ""
    quote: str = ""
    source: str | None = None
    date: str | None = None
    rating: float | None = None
    quote_is_exact: bool = False
    validation_status: QuoteValidationStatus = "invalid"
    validation_message: str = ""


class PriorityComponents(BaseModel):
    """Transparent prototype prioritization score components."""

    priority_score: float = Field(default=0.0, ge=0.0)
    frequency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    severity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    priority_method: str = "frequency_x_severity_x_confidence"
    priority_warning: str = "Prototype prioritization score – requires PM judgment."


class ThemeAggregationResult(BaseModel):
    """Output of theme-level evidence aggregation."""

    insights: list[ThemeInsight] = Field(default_factory=list)
    total_valid_feedback_records: int = Field(default=0, ge=0)
    excluded_analysis_results: int = Field(default=0, ge=0)
    invalid_quotes: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)


class RowIssue(BaseModel):
    """A single row-level validation or quality issue."""

    row_number: int = Field(..., ge=1)
    feedback_id: str | None = None
    issue_type: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    severity: RowIssueSeverity


class DataQualityReport(BaseModel):
    """Structured summary of CSV ingestion and validation results."""

    total_rows: int = Field(..., ge=0)
    valid_rows: int = Field(..., ge=0)
    invalid_rows: int = Field(..., ge=0)
    empty_feedback_rows: int = Field(default=0, ge=0)
    duplicate_id_rows: int = Field(default=0, ge=0)
    duplicate_text_rows: int = Field(default=0, ge=0)
    missing_required_columns: list[str] = Field(default_factory=list)
    missing_optional_columns: list[str] = Field(default_factory=list)
    invalid_rating_rows: int = Field(default=0, ge=0)
    invalid_date_rows: int = Field(default=0, ge=0)
    detected_encoding: str = ""
    file_size_bytes: int = Field(default=0, ge=0)
    source_name: str = ""
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    row_issues: list[RowIssue] = Field(default_factory=list)
    detected_columns: list[str] = Field(default_factory=list)
    mapped_columns: dict[str, str] = Field(default_factory=dict)

    def to_dict(self) -> dict:
        """Return a JSON-serializable dictionary representation."""
        return self.model_dump()


class ReviewRecord(BaseModel):
    """Placeholder human review record for future phases."""

    record_id: str = Field(..., min_length=1)
    status: ReviewStatus = "pending"
    reviewer_note: str = ""
    reviewed_at: datetime | None = None

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: object) -> str:
        status = str(value).strip().lower()
        if status not in SUPPORTED_REVIEW_STATUSES:
            raise ValueError(
                f"Invalid review status '{value}'. "
                f"Must be one of: {', '.join(SUPPORTED_REVIEW_STATUSES)}."
            )
        return status


class PIIEntity(BaseModel):
    """A detected PII span within feedback text."""

    entity_type: str = Field(..., min_length=1)
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)
    original_length: int = Field(..., ge=0)
    masked_value: str = Field(..., min_length=1)

    @field_validator("end")
    @classmethod
    def end_not_before_start(cls, value: int, info) -> int:
        start = info.data.get("start", 0)
        if value < start:
            raise ValueError("end must be greater than or equal to start.")
        return value

    @field_validator("original_length")
    @classmethod
    def length_matches_span(cls, value: int, info) -> int:
        start = info.data.get("start", 0)
        end = info.data.get("end", 0)
        if end - start != value:
            raise ValueError("original_length must equal end - start.")
        return value


class PIIDetectionResult(BaseModel):
    """Result of PII detection and masking for a single text value."""

    original_text: str | None = None
    masked_text: str = ""
    detected: bool = False
    entity_types: list[str] = Field(default_factory=list)
    entities: list[PIIEntity] = Field(default_factory=list)
    warning: str | None = None
    review_required: bool = False


class ReviewDecisionRecord(BaseModel):
    """Stored human review decision for a theme."""

    theme_name: str
    status: str = "pending"
    reviewer_note: str = ""
    created_at: str = ""
    updated_at: str = ""

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in SUPPORTED_REVIEW_STATUSES:
            raise ValueError(
                f"Invalid review status: '{value}'. Allowed: {SUPPORTED_REVIEW_STATUSES}"
            )
        return value


ThemeInsight.model_rebuild()
