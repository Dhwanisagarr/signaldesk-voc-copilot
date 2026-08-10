"""Deterministic rule-based sentiment analysis for masked feedback text."""

from __future__ import annotations

import math

import pandas as pd

from src.analysis_config import (
    SENTIMENT_MIXED_MIN_TERMS,
    SENTIMENT_NEGATIVE_TERMS,
    SENTIMENT_POSITIVE_TERMS,
)
from src.schemas import SentimentResult

MISSING_TEXT_WARNING = "Input text is missing; sentiment set to unknown."


def normalize_analysis_text(text: object) -> str | None:
    """Normalize analysis input, returning None for missing/blank values."""
    if text is None:
        return None
    try:
        if pd.isna(text):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(text, float) and math.isnan(text):
        return None
    normalized = str(text).strip()
    if not normalized or normalized.lower() == "nan":
        return None
    return normalized


def _find_matched_terms(text_lower: str, terms: tuple[str, ...]) -> list[str]:
    matched: list[str] = []
    for term in terms:
        if term in text_lower and term not in matched:
            matched.append(term)
    return matched


def _score_terms(count: int) -> float:
    if count <= 0:
        return 0.0
    return min(1.0, count / 3.0)


def analyze_sentiment(text: str | None) -> SentimentResult:
    """Analyze sentiment for a single masked feedback text."""
    normalized = normalize_analysis_text(text)
    if normalized is None:
        return SentimentResult(
            label="unknown",
            score=0.0,
            warning=MISSING_TEXT_WARNING,
            method="unknown",
        )

    text_lower = normalized.lower()
    positive_terms = _find_matched_terms(text_lower, SENTIMENT_POSITIVE_TERMS)
    negative_terms = _find_matched_terms(text_lower, SENTIMENT_NEGATIVE_TERMS)

    positive_score = _score_terms(len(positive_terms))
    negative_score = _score_terms(len(negative_terms))

    has_positive = len(positive_terms) >= SENTIMENT_MIXED_MIN_TERMS
    has_negative = len(negative_terms) >= SENTIMENT_MIXED_MIN_TERMS

    if has_positive and has_negative:
        label = "mixed"
        score = min(1.0, (positive_score + negative_score) / 2)
    elif has_negative:
        label = "negative"
        score = negative_score
    elif has_positive:
        label = "positive"
        score = positive_score
    else:
        label = "neutral"
        score = 0.0

    return SentimentResult(
        label=label,  # type: ignore[arg-type]
        score=score,
        positive_score=positive_score,
        negative_score=negative_score,
        matched_positive_terms=positive_terms,
        matched_negative_terms=negative_terms,
        method="local_rule_based",
    )


def analyze_sentiment_batch(texts: list[str | None]) -> list[SentimentResult]:
    """Analyze sentiment for a batch of masked feedback texts."""
    return [analyze_sentiment(text) for text in texts]
