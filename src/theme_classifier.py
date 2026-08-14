"""Keyword and TF-IDF theme classification for masked feedback text."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import re
from src.analysis_config import (
    INTENT_BUG_TERMS,
    INTENT_NEGATION_PHRASES,
    INTENT_PRAISE_TERMS,
    INTENT_QUESTION_TERMS,
    INTENT_REQUEST_TERMS,
    SEVERITY_CRITICAL_PHRASES,
    SEVERITY_HIGH_PHRASES,
    SEVERITY_LOW_PHRASES,
    SEVERITY_MEDIUM_PHRASES,
    SEVERITY_SCORES,
    THEME_KEYWORD_WEIGHT,
    THEME_PHRASE_WEIGHT,
    THEME_PRIMARY_MIN_CONFIDENCE,
    THEME_RULES,
    THEME_RULES_BY_NAME,
    THEME_SECONDARY_MIN_CONFIDENCE,
    THEME_STOPWORDS,
    TFIDF_FALLBACK_MAX_CONFIDENCE,
    TFIDF_FALLBACK_MIN_SIMILARITY,
    TFIDF_MAX_FEATURES,
    TFIDF_NGRAM_RANGE,
)
from src.schemas import ThemeClassification, ThemeLabel
from src.sentiment import normalize_analysis_text

MISSING_TEXT_WARNING = "Input text is missing; theme set to unknown."


@dataclass
class _ThemeScore:
    theme: str
    score: float
    confidence: float
    matched_terms: list[str]
    subtheme: str
    product_area: str
    severity: str
    intent: str
    method: str = "keyword_rule"
    warning: str | None = None


def _match_terms(text_lower: str, terms: tuple[str, ...]) -> list[str]:
    matched: list[str] = []
    for term in terms:
        if term in THEME_STOPWORDS:
            continue
        if term in text_lower and term not in matched:
            matched.append(term)
    return matched


def _resolve_subtheme(rule, text_lower: str) -> str:
    for subtheme, keywords in rule.subthemes.items():
        if any(keyword in text_lower for keyword in keywords):
            return subtheme
    return "general"


def _score_theme(text_lower: str, rule) -> _ThemeScore:
    phrase_matches = _match_terms(text_lower, rule.phrases)
    keyword_matches = _match_terms(text_lower, rule.keywords)
    raw_score = (
        len(phrase_matches) * THEME_PHRASE_WEIGHT + len(keyword_matches) * THEME_KEYWORD_WEIGHT
    )
    max_terms = max(1, len(rule.phrases) + len(rule.keywords))
    confidence = min(1.0, raw_score / max(2.0, max_terms * 0.5))
    matched_terms = phrase_matches + [term for term in keyword_matches if term not in phrase_matches]
    severity = determine_severity(text_lower, rule.default_severity)
    return _ThemeScore(
        theme=rule.theme,
        score=raw_score,
        confidence=confidence if matched_terms else 0.0,
        matched_terms=matched_terms,
        subtheme=_resolve_subtheme(rule, text_lower),
        product_area=rule.product_area,
        severity=severity,
        intent=rule.default_intent,
    )


def determine_severity(text_lower: str, default_severity: str) -> str:
    """Determine severity independently from sentiment."""
    if any(phrase in text_lower for phrase in SEVERITY_CRITICAL_PHRASES):
        return "critical"
    if any(phrase in text_lower for phrase in SEVERITY_HIGH_PHRASES):
        return "high"
    if any(phrase in text_lower for phrase in SEVERITY_MEDIUM_PHRASES):
        return "medium"
    if any(phrase in text_lower for phrase in SEVERITY_LOW_PHRASES):
        return "low"
    return default_severity


def _matches_word_or_phrase(term: str, text: str) -> bool:
    """Return True if term matches as a complete word/phrase in text."""
    if not term:
        return False
    if not any(c.isalnum() for c in term):
        return term in text
    pattern = r"(?<![a-zA-Z0-9_])" + re.escape(term) + r"(?![a-zA-Z0-9_])"
    return bool(re.search(pattern, text))


def determine_intent(text_lower: str, default_intent: str) -> str:
    """Determine intent using centralized keyword rules, word-boundary matching, and negation precedence."""
    has_negation = any(phrase in text_lower for phrase in INTENT_NEGATION_PHRASES)

    # Explicit negative phrases take precedence over positive keywords
    if not has_negation:
        if any(_matches_word_or_phrase(term, text_lower) for term in INTENT_PRAISE_TERMS):
            return "praise"

    if any(_matches_word_or_phrase(term, text_lower) for term in INTENT_REQUEST_TERMS):
        return "request"
    if any(_matches_word_or_phrase(term, text_lower) for term in INTENT_QUESTION_TERMS):
        return "question"
    if any(_matches_word_or_phrase(term, text_lower) for term in INTENT_BUG_TERMS):
        return "bug_report"

    if default_intent in {"complaint", "praise", "request", "bug_report", "question"}:
        if has_negation and default_intent == "praise":
            return "complaint"
        return default_intent

    return "complaint" if (has_negation or any(term in text_lower for term in ("failed", "delay", "unable", "not"))) else "unknown"


def severity_to_score(severity: str) -> float:
    return float(SEVERITY_SCORES.get(severity, 1))


def _scores_to_classification(scores: list[_ThemeScore], method: str, warning: str | None = None) -> ThemeClassification:
    ranked = sorted(
        scores,
        key=lambda item: (item.confidence, severity_to_score(item.severity), item.score),
        reverse=True,
    )
    ranked = [item for item in ranked if item.confidence > 0]

    if not ranked:
        return ThemeClassification(
            primary_theme="unknown",
            primary_subtheme="unknown",
            primary_confidence=0.0,
            method=method,
            warning=warning or "No reliable theme evidence found.",
            requires_human_review=True,
        )

    primary = ranked[0]
    secondary = [
        ThemeLabel(
            theme=item.theme,
            subtheme=item.subtheme,
            confidence=item.confidence,
            matched_terms=item.matched_terms,
            product_area=item.product_area,
            severity=item.severity,  # type: ignore[arg-type]
            method=item.method,
            warning=item.warning,
        )
        for item in ranked[1:]
        if item.confidence >= THEME_SECONDARY_MIN_CONFIDENCE
    ]

    requires_review = (
        primary.confidence < THEME_PRIMARY_MIN_CONFIDENCE
        or primary.theme == "unknown"
        or any(item.warning for item in ranked)
    )

    matched_terms_by_theme = {item.theme: item.matched_terms for item in ranked}
    confidence_by_theme = {item.theme: item.confidence for item in ranked}
    product_area_by_theme = {item.theme: item.product_area for item in ranked}
    severity_by_theme = {item.theme: item.severity for item in ranked}

    return ThemeClassification(
        primary_theme=primary.theme,
        primary_subtheme=primary.subtheme,
        primary_confidence=primary.confidence,
        secondary_themes=secondary,
        matched_terms_by_theme=matched_terms_by_theme,
        confidence_by_theme=confidence_by_theme,
        product_area_by_theme=product_area_by_theme,
        severity_by_theme=severity_by_theme,
        method=method,
        warning=warning,
        requires_human_review=requires_review,
    )


def classify_theme(
    text: str | None,
    rules: tuple[ThemeRuleConfig, ...] | None = None,
) -> ThemeClassification:
    """Classify themes for one masked text using keyword rules only."""
    normalized = normalize_analysis_text(text)
    if normalized is None:
        return ThemeClassification(
            primary_theme="unknown",
            primary_confidence=0.0,
            method="unknown",
            warning=MISSING_TEXT_WARNING,
            requires_human_review=True,
        )

    rules_to_use = rules if rules is not None else THEME_RULES
    text_lower = normalized.lower()
    scores = [_score_theme(text_lower, rule) for rule in rules_to_use]
    return _scores_to_classification(scores, method="keyword_rule")


def fit_theme_vectorizer(texts: list[str | None]) -> tuple[TfidfVectorizer | None, list[str]]:
    """Fit one TF-IDF vectorizer on the current batch of masked texts."""
    corpus = [text for text in (normalize_analysis_text(value) for value in texts) if text]
    if not corpus:
        return None, []

    vectorizer = TfidfVectorizer(
        max_features=TFIDF_MAX_FEATURES,
        ngram_range=TFIDF_NGRAM_RANGE,
        lowercase=True,
        token_pattern=r"(?u)\b[\w\u0900-\u097F]+\b",
    )
    try:
        vectorizer.fit(corpus)
    except ValueError:
        return None, corpus
    return vectorizer, corpus


def _theme_reference_documents(rules: tuple[ThemeRuleConfig, ...] | None = None) -> dict[str, str]:
    rules_to_use = rules if rules is not None else THEME_RULES
    documents: dict[str, str] = {}
    for rule in rules_to_use:
        documents[rule.theme] = " ".join(rule.phrases + rule.keywords)
    return documents


def infer_tfidf_fallback(
    text: str | None,
    vectorizer: TfidfVectorizer | None,
    rules: tuple[ThemeRuleConfig, ...] | None = None,
) -> ThemeClassification:
    """Infer a theme using dataset-level TF-IDF similarity."""
    normalized = normalize_analysis_text(text)
    if normalized is None or vectorizer is None:
        return ThemeClassification(
            primary_theme="unknown",
            primary_confidence=0.0,
            method="unknown",
            warning="TF-IDF fallback unavailable.",
            requires_human_review=True,
        )

    rules_to_use = rules if rules is not None else THEME_RULES
    rules_by_name = {rule.theme: rule for rule in rules_to_use}
    references = _theme_reference_documents(rules_to_use)
    try:
        reference_matrix = vectorizer.transform(list(references.values()))
        text_matrix = vectorizer.transform([normalized])
    except ValueError:
        return ThemeClassification(
            primary_theme="unknown",
            primary_confidence=0.0,
            method="unknown",
            warning="TF-IDF vocabulary empty for fallback.",
            requires_human_review=True,
        )

    similarities = cosine_similarity(text_matrix, reference_matrix).flatten()
    if similarities.size == 0:
        return ThemeClassification(
            primary_theme="unknown",
            primary_confidence=0.0,
            method="unknown",
            warning="No TF-IDF similarity scores available.",
            requires_human_review=True,
        )

    best_index = int(np.argmax(similarities))
    best_theme = list(references.keys())[best_index]
    best_similarity = float(similarities[best_index])
    if best_similarity < TFIDF_FALLBACK_MIN_SIMILARITY:
        return ThemeClassification(
            primary_theme="unknown",
            primary_confidence=0.0,
            method="unknown",
            warning="TF-IDF similarity below fallback threshold.",
            requires_human_review=True,
        )

    rule = rules_by_name.get(best_theme, THEME_RULES_BY_NAME.get(best_theme))
    if rule is None:
        return ThemeClassification(
            primary_theme="unknown",
            primary_confidence=0.0,
            method="unknown",
            warning="TF-IDF fallback rule mapping missing.",
            requires_human_review=True,
        )

    text_lower = normalized.lower()
    confidence = min(TFIDF_FALLBACK_MAX_CONFIDENCE, best_similarity)
    severity = determine_severity(text_lower, rule.default_severity)
    return ThemeClassification(
        primary_theme=best_theme,
        primary_subtheme=_resolve_subtheme(rule, text_lower),
        primary_confidence=confidence,
        matched_terms_by_theme={best_theme: ["tfidf_similarity"]},
        confidence_by_theme={best_theme: confidence},
        product_area_by_theme={best_theme: rule.product_area},
        severity_by_theme={best_theme: severity},
        method="tfidf_fallback",
        warning="Theme assigned via exploratory TF-IDF fallback.",
        requires_human_review=True,
    )


def classify_themes_batch(
    texts: list[str | None],
    rules: tuple[ThemeRuleConfig, ...] | None = None,
) -> list[ThemeClassification]:
    """Classify themes for a batch with keyword rules and TF-IDF fallback."""
    keyword_results = [classify_theme(text, rules=rules) for text in texts]
    vectorizer, _ = fit_theme_vectorizer(texts)

    final_results: list[ThemeClassification] = []
    for index, keyword_result in enumerate(keyword_results):
        needs_fallback = (
            keyword_result.primary_theme == "unknown"
            or keyword_result.primary_confidence < THEME_PRIMARY_MIN_CONFIDENCE
        )
        if needs_fallback:
            fallback = infer_tfidf_fallback(texts[index], vectorizer, rules=rules)
            if fallback.primary_theme != "unknown":
                # Preserve secondary themes from keyword pass when present.
                fallback.secondary_themes = keyword_result.secondary_themes
                final_results.append(fallback)
                continue
        final_results.append(keyword_result)
    return final_results
