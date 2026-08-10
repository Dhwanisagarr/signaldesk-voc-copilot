"""Tests for theme classification."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from src.theme_classifier import (
    classify_theme,
    classify_themes_batch,
    determine_intent,
    determine_severity,
    fit_theme_vectorizer,
    infer_tfidf_fallback,
)


class TestThemeClassification:
    def test_payment_failure(self) -> None:
        result = classify_theme("Payment failed and money was deducted.")
        assert result.primary_theme == "payment_failure"

    def test_refund_delay(self) -> None:
        result = classify_theme("Refund still pending after two weeks.")
        assert result.primary_theme == "refund_delay"

    def test_kyc_issue(self) -> None:
        result = classify_theme("KYC verification rejected after document upload.")
        assert result.primary_theme == "kyc_problem"

    def test_login_issue(self) -> None:
        result = classify_theme("Unable to login to my account since morning.")
        assert result.primary_theme == "login_authentication"

    def test_otp_issue(self) -> None:
        result = classify_theme("OTP not received for verification code step.")
        assert result.primary_theme == "otp_problem"

    def test_fees(self) -> None:
        result = classify_theme("Unexpected service fee charged without prior notification.")
        assert result.primary_theme == "fees"

    def test_customer_support(self) -> None:
        result = classify_theme("Customer support kept me on hold and disconnected the call.")
        assert result.primary_theme == "customer_support"

    def test_app_performance(self) -> None:
        result = classify_theme("App crashes whenever I open transaction history.")
        assert result.primary_theme == "app_performance"

    def test_usability(self) -> None:
        result = classify_theme("Refund tracking labels are unclear and hard to understand.")
        assert result.primary_theme == "usability"

    def test_security_concern(self) -> None:
        result = classify_theme("Received alert for unauthorized transaction activity.")
        assert result.primary_theme == "security_concern"

    def test_feature_request(self) -> None:
        result = classify_theme("Please add dark mode and export to CSV.")
        assert result.primary_theme == "feature_request"

    def test_unknown_text(self) -> None:
        result = classify_theme("Okay.")
        assert result.primary_theme == "unknown"
        assert result.requires_human_review is True

    def test_multiple_themes(self) -> None:
        text = "The app is fast, but my refund is still pending."
        result = classify_theme(text)
        assert result.primary_theme == "refund_delay"
        assert any(item.theme == "app_performance" for item in result.secondary_themes)

    def test_payment_and_support_secondary(self) -> None:
        text = "My payment failed and the money was deducted. Customer support has not replied."
        result = classify_theme(text)
        assert result.primary_theme == "payment_failure"
        assert any(item.theme == "customer_support" for item in result.secondary_themes)

    def test_matched_terms_returned(self) -> None:
        result = classify_theme("Refund still pending after payment failed.")
        assert result.matched_terms_by_theme

    def test_product_area_returned(self) -> None:
        result = classify_theme("Refund still pending.")
        assert result.product_area_by_theme.get("refund_delay") == "refunds"

    def test_severity_per_theme(self) -> None:
        text = "The app is fast, but my refund is still pending."
        result = classify_theme(text)
        assert result.severity_by_theme["refund_delay"] in {"high", "medium", "critical"}
        performance = next(item for item in result.secondary_themes if item.theme == "app_performance")
        assert performance.severity == "medium"

    def test_masked_text_only_via_function_contract(self) -> None:
        result = classify_theme("Payment failed for [EMAIL_REDACTED].")
        assert result.primary_theme == "payment_failure"

    def test_generic_problem_alone_not_theme(self) -> None:
        result = classify_theme("There is a problem.")
        assert result.primary_theme == "unknown"


class TestTfidfFallback:
    def test_fit_vectorizer_on_small_dataset(self) -> None:
        texts = ["payment failed", "refund pending", "kyc rejected"]
        vectorizer, corpus = fit_theme_vectorizer(texts)
        assert vectorizer is not None
        assert len(corpus) == 3

    def test_one_record_dataset(self) -> None:
        vectorizer, corpus = fit_theme_vectorizer(["payment failed once"])
        assert vectorizer is not None
        assert len(corpus) == 1

    def test_empty_dataset(self) -> None:
        vectorizer, corpus = fit_theme_vectorizer([])
        assert vectorizer is None
        assert corpus == []

    def test_blank_text_dataset(self) -> None:
        vectorizer, corpus = fit_theme_vectorizer(["", None, "   "])
        assert vectorizer is None
        assert corpus == []

    def test_repeated_identical_text(self) -> None:
        vectorizer, corpus = fit_theme_vectorizer(["refund pending", "refund pending"])
        assert vectorizer is not None
        assert len(corpus) == 2

    def test_single_text_classifier_does_not_use_tfidf(self) -> None:
        with patch("src.theme_classifier.infer_tfidf_fallback") as mocked:
            classify_theme("Payment failed.")
            mocked.assert_not_called()

    def test_batch_uses_one_vectorizer(self) -> None:
        with patch("src.theme_classifier.fit_theme_vectorizer") as mocked_fit:
            mocked_fit.return_value = (None, [])
            classify_themes_batch(["unknown phrase xyz", "another unrelated phrase"])
            mocked_fit.assert_called_once()

    def test_tfidf_fallback_method(self) -> None:
        texts = ["refund pending for many days"] * 3 + ["payment failed badly"] * 3
        vectorizer, _ = fit_theme_vectorizer(texts)
        fallback = infer_tfidf_fallback("refund pending for many days", vectorizer)
        assert fallback.method in {"tfidf_fallback", "unknown"}


class TestIntentAndSeverity:
    def test_intent_rules(self) -> None:
        assert determine_intent("please add dark mode", "complaint") == "request"
        assert determine_intent("thank you for resolving this", "complaint") == "praise"

    def test_severity_independent_from_sentiment(self) -> None:
        text = "Convenient app overall, but unauthorized transaction alert appeared."
        assert determine_severity(text.lower(), "low") == "critical"
