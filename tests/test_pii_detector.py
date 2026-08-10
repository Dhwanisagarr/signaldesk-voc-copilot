"""Tests for PII detection and masking."""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import PII_MASK_TOKENS
from src.pii_detector import (
    detect_and_mask_pii,
    detect_pii,
    mask_dataframe_feedback,
    mask_pii,
)

# Synthetic test values only — not real personal data.
SYNTHETIC_EMAIL = "user@example.com"
SYNTHETIC_PHONE = "9876543210"
SYNTHETIC_UPI = "user@upi"
SYNTHETIC_TXN = "TXN123456789"
SYNTHETIC_AADHAAR = "1234 5678 9012"
SYNTHETIC_ACCOUNT = "123456789012"
SYNTHETIC_CARD = "4111 1111 1111 1111"
SYNTHETIC_PAN = "ABCDE1234F"


def _assert_redacted(masked: str, *sensitive_values: str) -> None:
    for value in sensitive_values:
        assert value not in masked


class TestMissingInput:
    def test_none_input(self) -> None:
        result = detect_pii(None)
        assert result.detected is False
        assert result.masked_text == ""
        assert result.warning == "Input text is missing."

    def test_empty_string(self) -> None:
        result = detect_pii("")
        assert result.detected is False
        assert result.masked_text == ""
        assert result.warning == "Input text is missing."

    def test_whitespace_only(self) -> None:
        result = detect_pii("   ")
        assert result.detected is False
        assert result.masked_text == ""

    def test_pandas_na_input(self) -> None:
        result = detect_pii(pd.NA)
        assert result.detected is False
        assert result.masked_text == ""

    def test_nan_input(self) -> None:
        result = detect_pii(float("nan"))
        assert result.detected is False
        assert result.masked_text == ""


class TestNoPii:
    def test_normal_feedback_without_pii(self) -> None:
        text = "Payment failed during checkout but no contact details were shared."
        result = detect_and_mask_pii(text)
        assert result.detected is False
        assert result.masked_text == text
        assert result.entities == []


class TestEmailDetection:
    def test_email_detected_and_masked(self) -> None:
        text = f"Contact {SYNTHETIC_EMAIL} for support."
        result = detect_and_mask_pii(text)
        assert "EMAIL" in result.entity_types
        assert "UPI" not in result.entity_types
        assert PII_MASK_TOKENS["EMAIL"] in result.masked_text
        _assert_redacted(result.masked_text, SYNTHETIC_EMAIL)
        assert "Contact" in result.masked_text

    def test_email_original_preserved(self) -> None:
        text = f"Contact {SYNTHETIC_EMAIL}."
        result = detect_and_mask_pii(text)
        assert result.original_text == text
        _assert_redacted(result.masked_text, SYNTHETIC_EMAIL)


class TestPhoneDetection:
    def test_indian_phone_detected_and_masked(self) -> None:
        text = f"Contact number {SYNTHETIC_PHONE} for help."
        result = detect_and_mask_pii(text)
        assert "PHONE" in result.entity_types
        assert PII_MASK_TOKENS["PHONE"] in result.masked_text
        _assert_redacted(result.masked_text, SYNTHETIC_PHONE)

    def test_phone_with_country_code(self) -> None:
        text = "Call +91 9876543210 tomorrow."
        result = detect_and_mask_pii(text)
        assert "PHONE" in result.entity_types
        _assert_redacted(result.masked_text, "9876543210")


class TestUpiDetection:
    def test_upi_detected_and_masked(self) -> None:
        text = f"UPI ID: {SYNTHETIC_UPI}"
        result = detect_and_mask_pii(text)
        assert "UPI" in result.entity_types
        assert "EMAIL" not in result.entity_types
        assert PII_MASK_TOKENS["UPI"] in result.masked_text
        _assert_redacted(result.masked_text, SYNTHETIC_UPI)

    def test_upi_precedence_over_email(self) -> None:
        text = f"UPI ID: {SYNTHETIC_UPI}"
        result = detect_pii(text)
        assert result.entity_types == ["UPI"]
        assert all(entity.entity_type != "EMAIL" for entity in result.entities)

    def test_upi_and_email_together(self) -> None:
        text = f"Email {SYNTHETIC_EMAIL} and UPI ID {SYNTHETIC_UPI}."
        result = detect_and_mask_pii(text)
        assert "EMAIL" in result.entity_types
        assert "UPI" in result.entity_types
        _assert_redacted(result.masked_text, SYNTHETIC_EMAIL, SYNTHETIC_UPI)


class TestOtherEntityTypes:
    def test_aadhaar_with_context(self) -> None:
        text = f"Aadhaar number {SYNTHETIC_AADHAAR} was rejected."
        result = detect_and_mask_pii(text)
        assert "AADHAAR" in result.entity_types
        _assert_redacted(result.masked_text, SYNTHETIC_AADHAAR.replace(" ", ""), "56789012")

    def test_account_with_context(self) -> None:
        text = f"Bank account number {SYNTHETIC_ACCOUNT} is blocked."
        result = detect_and_mask_pii(text)
        assert "ACCOUNT" in result.entity_types
        _assert_redacted(result.masked_text, SYNTHETIC_ACCOUNT)

    def test_transaction_id_with_context(self) -> None:
        text = f"Transaction {SYNTHETIC_TXN} failed."
        result = detect_and_mask_pii(text)
        assert "TRANSACTION_ID" in result.entity_types
        _assert_redacted(result.masked_text, SYNTHETIC_TXN)

    def test_transaction_ref_format(self) -> None:
        text = "Reference REF-2026-0001 is pending."
        result = detect_and_mask_pii(text)
        assert "TRANSACTION_ID" in result.entity_types
        _assert_redacted(result.masked_text, "REF-2026-0001")

    def test_card_like_value(self) -> None:
        text = f"Card ending {SYNTHETIC_CARD} was declined."
        result = detect_and_mask_pii(text)
        assert "CARD" in result.entity_types
        assert PII_MASK_TOKENS["CARD"] in result.masked_text
        _assert_redacted(result.masked_text, "4111")

    def test_pan_with_context(self) -> None:
        text = f"PAN {SYNTHETIC_PAN} verification failed."
        result = detect_and_mask_pii(text)
        assert "PAN" in result.entity_types
        _assert_redacted(result.masked_text, SYNTHETIC_PAN)


class TestMultipleEntities:
    def test_multiple_entities_in_one_sentence(self) -> None:
        text = (
            f"Refund sent to {SYNTHETIC_EMAIL} after transaction {SYNTHETIC_TXN} "
            f"and phone {SYNTHETIC_PHONE}."
        )
        result = detect_and_mask_pii(text)
        assert len(result.entities) >= 3
        _assert_redacted(result.masked_text, SYNTHETIC_EMAIL, SYNTHETIC_TXN, SYNTHETIC_PHONE)

    def test_repeated_pii_values(self) -> None:
        text = f"{SYNTHETIC_EMAIL} and again {SYNTHETIC_EMAIL}"
        result = detect_and_mask_pii(text)
        assert len(result.entities) >= 2
        assert result.masked_text.count(PII_MASK_TOKENS["EMAIL"]) == 2
        _assert_redacted(result.masked_text, SYNTHETIC_EMAIL)

    def test_punctuation_around_pii(self) -> None:
        text = f"({SYNTHETIC_EMAIL}), [{SYNTHETIC_PHONE}]!"
        result = detect_and_mask_pii(text)
        _assert_redacted(result.masked_text, SYNTHETIC_EMAIL, SYNTHETIC_PHONE)
        assert "(" in result.masked_text

    def test_no_duplicate_entity_spans(self) -> None:
        text = f"Transaction {SYNTHETIC_TXN} failed."
        result = detect_pii(text)
        spans = [(entity.start, entity.end) for entity in result.entities]
        assert len(spans) == len(set(spans))

    def test_non_pii_text_unchanged(self) -> None:
        prefix = "Payment failed for "
        suffix = " during checkout."
        text = f"{prefix}{SYNTHETIC_EMAIL}{suffix}"
        result = detect_and_mask_pii(text)
        assert result.masked_text.startswith(prefix)
        assert result.masked_text.endswith(suffix)


class TestMaskPiiFunction:
    def test_mask_pii_returns_masked_string(self) -> None:
        masked = mask_pii(f"Contact {SYNTHETIC_EMAIL}")
        assert PII_MASK_TOKENS["EMAIL"] in masked
        _assert_redacted(masked, SYNTHETIC_EMAIL)


class TestDataFrameHelper:
    def test_mask_dataframe_feedback_columns(self) -> None:
        df = pd.DataFrame(
            {
                "feedback_id": ["FB-1", "FB-2"],
                "feedback_text": [
                    "No sensitive content here.",
                    f"Email {SYNTHETIC_EMAIL}",
                ],
            }
        )
        masked_df = mask_dataframe_feedback(df)
        expected_columns = {
            "feedback_id",
            "feedback_text",
            "original_text",
            "masked_text",
            "pii_detected",
            "pii_entity_types",
            "pii_review_required",
        }
        assert expected_columns.issubset(set(masked_df.columns))
        assert not bool(masked_df.loc[0, "pii_detected"])
        assert bool(masked_df.loc[1, "pii_detected"])
        _assert_redacted(masked_df.loc[1, "masked_text"], SYNTHETIC_EMAIL)

    def test_dataframe_helper_does_not_modify_input(self) -> None:
        df = pd.DataFrame({"feedback_text": ["Plain feedback."]})
        original_columns = df.columns.tolist()
        _ = mask_dataframe_feedback(df)
        assert df.columns.tolist() == original_columns
        assert "masked_text" not in df.columns

    def test_missing_text_column_raises_clear_error(self) -> None:
        df = pd.DataFrame({"feedback_id": ["FB-1"]})
        with pytest.raises(KeyError, match="feedback_text"):
            mask_dataframe_feedback(df)

    def test_dataframe_handles_missing_text_values(self) -> None:
        df = pd.DataFrame({"feedback_text": [None, pd.NA, "Valid text"]})
        masked_df = mask_dataframe_feedback(df)
        assert masked_df.loc[0, "masked_text"] == ""
        assert masked_df.loc[1, "masked_text"] == ""
        assert masked_df.loc[2, "masked_text"] == "Valid text"


class TestReviewRequired:
    def test_single_email_may_not_require_review(self) -> None:
        result = detect_pii(f"Contact {SYNTHETIC_EMAIL}")
        assert result.review_required is False

    def test_ambiguous_card_requires_review(self) -> None:
        result = detect_pii(f"Value {SYNTHETIC_CARD}")
        assert result.review_required is True

    def test_multiple_categories_require_review(self) -> None:
        result = detect_pii(f"{SYNTHETIC_EMAIL} and {SYNTHETIC_PHONE}")
        assert result.review_required is True
