"""Local analysis pipeline for masked customer feedback."""

from __future__ import annotations

import pandas as pd

from src.analysis_config import LOW_CONFIDENCE_REVIEW_THRESHOLD, THEME_RULES_BY_NAME
from src.clustering import cluster_feedback
from src.schemas import AnalysisPipelineResult, AnalysisResult, ThemeLabel
from src.sentiment import analyze_sentiment_batch, normalize_analysis_text
from src.theme_classifier import classify_themes_batch, determine_intent, severity_to_score

MASKED_TEXT_REQUIRED_ERROR = (
    "Analysis requires a 'masked_text' column. "
    "Run Phase 3 PII masking before analysis. "
    "Raw 'feedback_text' or 'original_text' must not be analysed directly."
)


def _validate_input_dataframe(df: pd.DataFrame, text_column: str) -> None:
    if "feedback_id" not in df.columns:
        raise KeyError("Analysis requires a 'feedback_id' column.")
    if text_column not in df.columns:
        if text_column == "masked_text" and "feedback_text" in df.columns:
            raise KeyError(MASKED_TEXT_REQUIRED_ERROR)
        raise KeyError(f"Analysis requires a '{text_column}' column.")


def _build_customer_problem(theme_label: ThemeLabel, masked_text: str | None) -> str:
    if not theme_label.matched_terms:
        return ""
    terms = ", ".join(theme_label.matched_terms[:3])
    return f"Detected {theme_label.theme.replace('_', ' ')} related to: {terms}"


def _combine_confidence(theme_confidence: float, sentiment_score: float) -> float:
    return round(min(1.0, max(0.0, (theme_confidence * 0.75) + (sentiment_score * 0.25))), 3)


def _unknown_result(feedback_id: str, warnings: list[str]) -> AnalysisResult:
    return AnalysisResult(
        feedback_id=feedback_id,
        sentiment="unknown",
        sentiment_score=0.0,
        primary_theme="unknown",
        primary_subtheme="unknown",
        primary_confidence=0.0,
        product_area="unknown",
        severity="unknown",
        severity_score=1.0,
        intent="unknown",
        confidence=0.0,
        requires_human_review=True,
        analysis_method="unknown",
        analysis_warnings=warnings,
        supporting_feedback_ids=[feedback_id],
        theme="unknown",
    )


from src.taxonomy_loader import load_taxonomy_preset


def analyze_feedback_dataframe(
    df: pd.DataFrame,
    text_column: str = "masked_text",
    taxonomy_preset: str = "fintech",
) -> AnalysisPipelineResult:
    """Analyze a DataFrame of masked feedback using local deterministic rules."""
    _validate_input_dataframe(df, text_column)

    pipeline_warnings: list[str] = []
    if df.empty:
        pipeline_warnings.append("Empty DataFrame received; no records analysed.")
        return AnalysisPipelineResult(
            results=[],
            clusters=[],
            total_records=0,
            analyzed_records=0,
            unknown_records=0,
            human_review_records=0,
            warnings=pipeline_warnings,
        )

    working = df.copy()
    feedback_ids = working["feedback_id"].astype(str).tolist()
    masked_texts = working[text_column].tolist()

    rules = load_taxonomy_preset(taxonomy_preset)
    rules_by_name = {rule.theme: rule for rule in rules}

    sentiment_results = analyze_sentiment_batch(masked_texts)
    theme_results = classify_themes_batch(masked_texts, rules=rules)
    clustering_output = cluster_feedback(masked_texts, feedback_ids)
    pipeline_warnings.extend(clustering_output.warnings)

    if working["feedback_id"].duplicated().any():
        pipeline_warnings.append("Duplicate feedback_id values detected; results retained for all rows.")

    results: list[AnalysisResult] = []
    for index, feedback_id in enumerate(feedback_ids):
        row_warnings: list[str] = []
        masked_text = normalize_analysis_text(masked_texts[index])
        sentiment = sentiment_results[index]
        themes = theme_results[index]
        cluster_id = clustering_output.cluster_id_by_feedback_id.get(feedback_id)

        pii_review = bool(working.iloc[index].get("pii_review_required", False))
        if pd.isna(working.iloc[index].get("pii_review_required", False)):
            pii_review = False

        if masked_text is None:
            unknown = _unknown_result(feedback_id, ["Masked text is missing."])
            if pii_review:
                unknown.requires_human_review = True
                unknown.analysis_warnings.append("PII review flagged on source row.")
            results.append(unknown)
            continue

        if themes.primary_theme == "unknown":
            row_warnings.append("No reliable theme identified.")

        primary_rule = rules_by_name.get(themes.primary_theme, THEME_RULES_BY_NAME.get(themes.primary_theme))
        primary_theme_label = ThemeLabel(
            theme=themes.primary_theme,
            subtheme=themes.primary_subtheme,
            confidence=themes.primary_confidence,
            matched_terms=themes.matched_terms_by_theme.get(themes.primary_theme, []),
            product_area=themes.product_area_by_theme.get(themes.primary_theme, "unknown"),
            severity=themes.severity_by_theme.get(themes.primary_theme, "unknown"),  # type: ignore[arg-type]
            method=themes.method,
            warning=themes.warning,
        )

        intent = (
            determine_intent(masked_text.lower(), primary_rule.default_intent)
            if primary_rule
            else "unknown"
        )
        severity = themes.severity_by_theme.get(themes.primary_theme, "unknown")
        severity_score = severity_to_score(severity)
        confidence = _combine_confidence(themes.primary_confidence, sentiment.score)
        customer_problem = _build_customer_problem(primary_theme_label, masked_text)

        requires_review = (
            themes.requires_human_review
            or pii_review
            or themes.primary_theme == "unknown"
            or confidence < LOW_CONFIDENCE_REVIEW_THRESHOLD
            or sentiment.label == "unknown"
        )
        if themes.warning:
            row_warnings.append(themes.warning)
        if pii_review:
            row_warnings.append("PII review flagged on source row.")

        analysis_method = themes.method if themes.method in {
            "local_rule_based",
            "keyword_rule",
            "tfidf_fallback",
            "exploratory_cluster",
            "unknown",
        } else "keyword_rule"

        result = AnalysisResult(
            feedback_id=feedback_id,
            sentiment=sentiment.label,
            sentiment_score=sentiment.score,
            primary_theme=themes.primary_theme,
            primary_subtheme=themes.primary_subtheme,
            primary_confidence=themes.primary_confidence,
            secondary_themes=themes.secondary_themes,
            product_area=themes.product_area_by_theme.get(themes.primary_theme, "unknown"),
            severity=severity,  # type: ignore[arg-type]
            severity_score=severity_score,
            intent=intent,  # type: ignore[arg-type]
            customer_problem=customer_problem,
            confidence=confidence,
            matched_terms=primary_theme_label.matched_terms,
            supporting_feedback_ids=[feedback_id],
            requires_human_review=requires_review,
            analysis_method=analysis_method,  # type: ignore[arg-type]
            analysis_warnings=row_warnings,
            cluster_id=cluster_id,
            theme=themes.primary_theme,
        )
        results.append(result)

    analyzed_records = sum(1 for result in results if result.primary_theme != "unknown")
    unknown_records = sum(1 for result in results if result.primary_theme == "unknown")
    human_review_records = sum(1 for result in results if result.requires_human_review)

    return AnalysisPipelineResult(
        results=results,
        clusters=clustering_output.clusters,
        total_records=len(results),
        analyzed_records=analyzed_records,
        unknown_records=unknown_records,
        human_review_records=human_review_records,
        warnings=pipeline_warnings,
    )
