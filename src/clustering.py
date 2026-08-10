"""Exploratory K-Means clustering for masked feedback similarity groups."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from src.analysis_config import (
    CLUSTER_DEFAULT_K,
    CLUSTER_MAX_K,
    CLUSTER_N_INIT,
    CLUSTER_RANDOM_STATE,
    CLUSTER_REPRESENTATIVE_TERMS,
    TFIDF_MAX_FEATURES,
    TFIDF_NGRAM_RANGE,
)
from src.schemas import ClusterResult
from src.sentiment import normalize_analysis_text

CLUSTER_WARNING = "Exploratory similarity group — not a confirmed product theme."


@dataclass
class ClusteringOutput:
    """Cluster assignments and exploratory cluster metadata."""

    cluster_id_by_feedback_id: dict[str, int | None]
    clusters: list[ClusterResult]
    warnings: list[str]


def choose_cluster_count(n_records: int, requested_k: int | None = None) -> int:
    """Choose a safe cluster count for the available records."""
    if n_records <= 0:
        return 0
    if n_records == 1:
        return 1
    desired = requested_k or min(CLUSTER_DEFAULT_K, n_records)
    desired = max(1, min(desired, CLUSTER_MAX_K, n_records))
    return desired


def _build_corpus(texts: list[str | None], feedback_ids: list[str]) -> tuple[list[str], list[str]]:
    corpus: list[str] = []
    ids: list[str] = []
    for feedback_id, text in zip(feedback_ids, texts, strict=True):
        normalized = normalize_analysis_text(text)
        if normalized:
            corpus.append(normalized)
            ids.append(feedback_id)
    return corpus, ids


def get_cluster_representative_terms(
    vectorizer: TfidfVectorizer,
    matrix,
    labels: np.ndarray,
    cluster_id: int,
    top_n: int = CLUSTER_REPRESENTATIVE_TERMS,
) -> list[str]:
    """Extract top TF-IDF terms for one exploratory cluster."""
    cluster_indices = np.where(labels == cluster_id)[0]
    if cluster_indices.size == 0:
        return []
    cluster_matrix = matrix[cluster_indices].mean(axis=0)
    if hasattr(cluster_matrix, "A1"):
        scores = cluster_matrix.A1
    else:
        scores = np.asarray(cluster_matrix).ravel()
    feature_names = vectorizer.get_feature_names_out()
    top_indices = scores.argsort()[::-1][:top_n]
    return [feature_names[index] for index in top_indices if scores[index] > 0]


def cluster_feedback(
    texts: list[str | None],
    feedback_ids: list[str],
    requested_k: int | None = None,
) -> ClusteringOutput:
    """Cluster masked feedback texts into exploratory similarity groups."""
    if len(texts) != len(feedback_ids):
        raise ValueError("texts and feedback_ids must have the same length.")

    warnings: list[str] = []
    cluster_id_by_feedback_id: dict[str, int | None] = {fid: None for fid in feedback_ids}

    corpus, usable_ids = _build_corpus(texts, feedback_ids)
    if not corpus:
        warnings.append("Clustering skipped: no usable masked text.")
        return ClusteringOutput(cluster_id_by_feedback_id, [], warnings)

    if len(corpus) == 1:
        cluster_id_by_feedback_id[usable_ids[0]] = 0
        clusters = [
            ClusterResult(
                cluster_id=0,
                feedback_ids=[usable_ids[0]],
                representative_terms=[],
                cluster_size=1,
                warning=CLUSTER_WARNING,
            )
        ]
        warnings.append("Clustering skipped for single-record dataset; assigned exploratory cluster 0.")
        return ClusteringOutput(cluster_id_by_feedback_id, clusters, warnings)

    k = choose_cluster_count(len(corpus), requested_k)
    vectorizer = TfidfVectorizer(
        max_features=TFIDF_MAX_FEATURES,
        ngram_range=TFIDF_NGRAM_RANGE,
        lowercase=True,
        token_pattern=r"(?u)\b[\w\u0900-\u097F]+\b",
    )
    try:
        matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        warnings.append("Clustering skipped: empty TF-IDF vocabulary.")
        return ClusteringOutput(cluster_id_by_feedback_id, [], warnings)

    if matrix.shape[1] == 0:
        warnings.append("Clustering skipped: empty TF-IDF vocabulary.")
        return ClusteringOutput(cluster_id_by_feedback_id, [], warnings)

    effective_k = min(k, len(corpus))
    if effective_k < requested_k if requested_k else False:
        warnings.append("Requested cluster count reduced to match usable record count.")

    model = KMeans(
        n_clusters=effective_k,
        random_state=CLUSTER_RANDOM_STATE,
        n_init=CLUSTER_N_INIT,
    )
    labels = model.fit_predict(matrix)

    for feedback_id, label in zip(usable_ids, labels, strict=True):
        cluster_id_by_feedback_id[feedback_id] = int(label)

    clusters: list[ClusterResult] = []
    for cluster_id in sorted(set(int(label) for label in labels)):
        members = [usable_ids[index] for index, label in enumerate(labels) if int(label) == cluster_id]
        terms = get_cluster_representative_terms(vectorizer, matrix, labels, cluster_id)
        clusters.append(
            ClusterResult(
                cluster_id=cluster_id,
                feedback_ids=members,
                representative_terms=terms,
                cluster_size=len(members),
                warning=CLUSTER_WARNING,
            )
        )

    return ClusteringOutput(cluster_id_by_feedback_id, clusters, warnings)
