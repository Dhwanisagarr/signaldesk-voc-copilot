"""Pydantic schemas for SignalDesk data models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.config import SUPPORTED_REVIEW_STATUSES, SUPPORTED_SENTIMENTS, SUPPORTED_SEVERITIES

SentimentLabel = Literal["positive", "neutral", "negative", "mixed", "unknown"]
SeverityLabel = Literal["low", "medium", "high", "critical"]
ReviewStatus = Literal["pending", "approved", "rejected", "needs_more_evidence"]
RowIssueSeverity = Literal["valid", "warning", "error"]


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
        if rating < 0 or rating > 5:
            raise ValueError("Rating must be between 0 and 5.")
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


class AnalysisResult(BaseModel):
    """Placeholder per-item analysis output for future phases."""

    feedback_id: str = Field(..., min_length=1)
    sentiment: SentimentLabel = "unknown"
    theme: str = "unknown"
    severity: SeverityLabel = "low"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    analysis_method: str = "not_implemented"

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
        if severity not in SUPPORTED_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{value}'. Must be one of: {', '.join(SUPPORTED_SEVERITIES)}."
            )
        return severity


class ThemeInsight(BaseModel):
    """Placeholder theme-level insight for future phases."""

    theme_name: str = Field(..., min_length=1)
    feedback_count: int = Field(..., ge=0)
    feedback_percentage: float = Field(..., ge=0.0, le=100.0)
    representative_quotes: list[str] = Field(default_factory=list)
    source_feedback_ids: list[str] = Field(default_factory=list)
    suggested_product_action: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    human_review_status: ReviewStatus = "pending"

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
