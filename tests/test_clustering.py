"""Tests for exploratory clustering."""

from __future__ import annotations

from src.clustering import choose_cluster_count, cluster_feedback
from src.theme_classifier import classify_theme
from src.sentiment import analyze_sentiment


class TestChooseClusterCount:
    def test_zero_records(self) -> None:
        assert choose_cluster_count(0) == 0

    def test_one_record(self) -> None:
        assert choose_cluster_count(1) == 1

    def test_requested_k_larger_than_records(self) -> None:
        assert choose_cluster_count(3, requested_k=8) == 3


class TestClusterFeedback:
    def test_more_records_than_clusters(self) -> None:
        texts = [
            "payment failed again",
            "refund still pending",
            "kyc rejected",
            "app crashes often",
        ]
        ids = ["A", "B", "C", "D"]
        output = cluster_feedback(texts, ids, requested_k=2)
        assert len(output.clusters) == 2
        assert all(output.cluster_id_by_feedback_id[fid] is not None for fid in ids)

    def test_fewer_records_than_requested_k(self) -> None:
        output = cluster_feedback(["payment failed", "refund pending"], ["A", "B"], requested_k=5)
        assert len(output.clusters) <= 2
        assert any("reduced" in warning.lower() or "exploratory" in warning.lower() for warning in output.warnings) or len(output.clusters) == 2

    def test_one_record(self) -> None:
        output = cluster_feedback(["payment failed"], ["A"], requested_k=3)
        assert output.cluster_id_by_feedback_id["A"] == 0
        assert output.clusters[0].cluster_size == 1
        assert output.warnings

    def test_zero_records(self) -> None:
        output = cluster_feedback([], [])
        assert output.clusters == []
        assert output.warnings

    def test_deterministic_results(self) -> None:
        texts = ["payment failed", "refund pending", "kyc rejected", "app crashes"]
        ids = ["A", "B", "C", "D"]
        first = cluster_feedback(texts, ids, requested_k=2)
        second = cluster_feedback(texts, ids, requested_k=2)
        assert first.cluster_id_by_feedback_id == second.cluster_id_by_feedback_id

    def test_clustering_does_not_modify_theme(self) -> None:
        text = "Payment failed and refund is still pending."
        before = classify_theme(text)
        cluster_feedback([text], ["FB-1"], requested_k=1)
        after = classify_theme(text)
        assert before.primary_theme == after.primary_theme

    def test_clustering_does_not_modify_sentiment(self) -> None:
        text = "Payment failed but app is fast."
        before = analyze_sentiment(text)
        cluster_feedback([text], ["FB-1"], requested_k=1)
        after = analyze_sentiment(text)
        assert before.label == after.label

    def test_cluster_warning_present(self) -> None:
        output = cluster_feedback(["payment failed", "refund pending"], ["A", "B"], requested_k=2)
        assert output.clusters
        assert all(cluster.warning for cluster in output.clusters)
