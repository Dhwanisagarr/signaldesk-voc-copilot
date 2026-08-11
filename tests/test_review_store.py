"""Unit tests for SQLite review store (src/review_store.py)."""

from __future__ import annotations

import sqlite3
import pytest
from pathlib import Path

from src.review_store import (
    ReviewStoreError,
    clear_review_decisions,
    delete_review_decision,
    get_all_review_decisions,
    get_review_decision,
    initialize_review_store,
    save_review_decision,
)


@pytest.fixture()
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_reviews.db"


class TestReviewStore:
    def test_database_initialization(self, temp_db_path: Path) -> None:
        db_file = initialize_review_store(temp_db_path)
        assert db_file.exists()

    def test_table_creation(self, temp_db_path: Path) -> None:
        initialize_review_store(temp_db_path)
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='review_decisions'")
        table = cursor.fetchone()
        conn.close()
        assert table is not None

    def test_saving_pending_review(self, temp_db_path: Path) -> None:
        result = save_review_decision(temp_db_path, "payment_failure", "pending", "Initial note")
        assert result["theme_name"] == "payment_failure"
        assert result["status"] == "pending"
        assert result["reviewer_note"] == "Initial note"

    def test_retrieving_saved_review(self, temp_db_path: Path) -> None:
        save_review_decision(temp_db_path, "refund_delay", "approved", "Valid theme")
        retrieved = get_review_decision(temp_db_path, "refund_delay")
        assert retrieved is not None
        assert retrieved["theme_name"] == "refund_delay"
        assert retrieved["status"] == "approved"
        assert retrieved["reviewer_note"] == "Valid theme"

    def test_updating_existing_review(self, temp_db_path: Path) -> None:
        first = save_review_decision(temp_db_path, "kyc_problem", "pending", "Needs review")
        second = save_review_decision(temp_db_path, "kyc_problem", "approved", "Approved by PM")
        assert second["created_at"] == first["created_at"]
        assert second["status"] == "approved"
        assert second["reviewer_note"] == "Approved by PM"

        updated = get_review_decision(temp_db_path, "kyc_problem")
        assert updated is not None
        assert updated["status"] == "approved"

    def test_retrieving_all_reviews(self, temp_db_path: Path) -> None:
        save_review_decision(temp_db_path, "payment_failure", "approved", "Note 1")
        save_review_decision(temp_db_path, "refund_delay", "rejected", "Note 2")
        all_reviews = get_all_review_decisions(temp_db_path)
        assert len(all_reviews) == 2
        assert "payment_failure" in all_reviews
        assert "refund_delay" in all_reviews
        assert all_reviews["payment_failure"]["status"] == "approved"

    def test_deleting_one_review(self, temp_db_path: Path) -> None:
        save_review_decision(temp_db_path, "fees", "approved", "Note")
        deleted = delete_review_decision(temp_db_path, "fees")
        assert deleted is True
        assert get_review_decision(temp_db_path, "fees") is None

    def test_clearing_all_reviews(self, temp_db_path: Path) -> None:
        save_review_decision(temp_db_path, "theme1", "approved", "")
        save_review_decision(temp_db_path, "theme2", "rejected", "")
        cleared_count = clear_review_decisions(temp_db_path)
        assert cleared_count == 2
        assert len(get_all_review_decisions(temp_db_path)) == 0

    def test_persistence_across_new_store_instance(self, temp_db_path: Path) -> None:
        save_review_decision(temp_db_path, "usability", "needs_more_evidence", "Note persistent")
        # Call function again independently
        retrieved = get_review_decision(temp_db_path, "usability")
        assert retrieved is not None
        assert retrieved["status"] == "needs_more_evidence"

    def test_invalid_status_rejection(self, temp_db_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid review status"):
            save_review_decision(temp_db_path, "payment_failure", "invalid_status", "Note")

    def test_empty_theme_name_rejection(self, temp_db_path: Path) -> None:
        with pytest.raises(ValueError, match="Theme name must be a non-empty string"):
            save_review_decision(temp_db_path, "", "approved", "Note")

    def test_safe_parameter_handling(self, temp_db_path: Path) -> None:
        malicious_theme = "theme'; DROP TABLE review_decisions; --"
        save_review_decision(temp_db_path, malicious_theme, "approved", "Note")
        retrieved = get_review_decision(temp_db_path, malicious_theme)
        assert retrieved is not None
        assert retrieved["theme_name"] == malicious_theme
        # Ensure table was not dropped
        assert len(get_all_review_decisions(temp_db_path)) == 1

    def test_no_original_text_column(self, temp_db_path: Path) -> None:
        initialize_review_store(temp_db_path)
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(review_decisions)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        assert "original_text" not in columns
        assert "feedback_text" not in columns

    def test_unmasked_pii_not_stored(self, temp_db_path: Path) -> None:
        save_review_decision(temp_db_path, "kyc_problem", "approved", "Reviewed metadata only")
        record = get_review_decision(temp_db_path, "kyc_problem")
        assert record is not None
        for key in record:
            assert key in {"theme_name", "status", "reviewer_note", "created_at", "updated_at"}

    def test_missing_database_path_handling(self, tmp_path: Path) -> None:
        nested_db = tmp_path / "deep" / "nested" / "dir" / "reviews.db"
        assert not nested_db.parent.exists()
        initialize_review_store(nested_db)
        assert nested_db.exists()

    def test_corrupted_database_handling(self, temp_db_path: Path) -> None:
        # Write corrupted garbage bytes to database file
        temp_db_path.parent.mkdir(parents=True, exist_ok=True)
        temp_db_path.write_bytes(b"NOT A VALID SQLITE DATABASE FILE")
        with pytest.raises(ReviewStoreError):
            get_all_review_decisions(temp_db_path)
