"""Tests for deterministic sentiment analysis."""

from __future__ import annotations

import pandas as pd

from src.sentiment import analyze_sentiment, analyze_sentiment_batch, normalize_analysis_text
from src.theme_classifier import determine_severity


class TestNormalizeAnalysisText:
    def test_none_and_na_are_missing(self) -> None:
        assert normalize_analysis_text(None) is None
        assert normalize_analysis_text(pd.NA) is None
        assert normalize_analysis_text(float("nan")) is None


class TestSentimentAnalysis:
    def test_positive_feedback(self) -> None:
        result = analyze_sentiment("Smooth and helpful onboarding experience.")
        assert result.label == "positive"
        assert result.matched_positive_terms

    def test_negative_feedback(self) -> None:
        result = analyze_sentiment("Payment failed and refund is still pending.")
        assert result.label == "negative"
        assert result.matched_negative_terms

    def test_neutral_feedback(self) -> None:
        result = analyze_sentiment("I checked the transaction history page.")
        assert result.label == "neutral"

    def test_mixed_sentiment(self) -> None:
        result = analyze_sentiment("The app is fast, but my refund is still pending.")
        assert result.label == "mixed"
        assert result.matched_positive_terms
        assert result.matched_negative_terms

    def test_empty_and_none(self) -> None:
        assert analyze_sentiment("").label == "unknown"
        assert analyze_sentiment(None).label == "unknown"

    def test_hinglish_terms(self) -> None:
        result = analyze_sentiment("App bahut achha hai par refund mein der ho rahi hai.")
        assert "अच्छा" in result.matched_positive_terms or result.label in {"mixed", "positive"}

    def test_sentiment_separate_from_severity(self) -> None:
        text = "Overall experience is convenient, but unauthorized transaction alert appeared."
        sentiment = analyze_sentiment(text)
        severity = determine_severity(text.lower(), "medium")
        assert sentiment.label in {"mixed", "positive", "neutral"}
        assert severity == "critical"

    def test_positive_text_with_security_concern(self) -> None:
        text = "Love the rewards program but unauthorized transaction alert appeared."
        sentiment = analyze_sentiment(text)
        severity = determine_severity(text.lower(), "low")
        assert sentiment.label == "positive"
        assert severity == "critical"

    def test_batch_analysis(self) -> None:
        results = analyze_sentiment_batch(["Great app", None, "Payment failed"])
        assert len(results) == 3
        assert results[1].label == "unknown"
