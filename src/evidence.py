"""Evidence validation and theme-level aggregation for SignalDesk."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

import pandas as pd

from src.analysis_config import THEME_RULES_BY_NAME
from src.config import (
    EVIDENCE_MODERATE_MIN_MENTIONS,
    EVIDENCE_STRONG_MIN_CONFIDENCE,
    EVIDENCE_STRONG_MIN_MENTIONS,
    EVIDENCE_STRONG_MIN_SOURCES,
    EVIDENCE_WEAK_MAX_MENTIONS,
    EXCLUDED_AGGREGATION_THEMES,
    MASKED_TEXT_REQUIRED_ERROR,
    MAX_REPRESENTATIVE_QUOTES,
    PII_MASK_TOKENS,
)
from src.schemas import (
    AnalysisResult,
    EvidenceQuote,
    ThemeAggregationResult,
    ThemeInsight,
)
from src.sentiment import normalize_analysis_text

ROOT_CAUSE_TEMPLATES: dict[str, str] = {
    "payment_failure": "Payment failures or reconciliation delays may be affecting customer transactions.",
    "refund_delay": "Refund processing or status visibility may be slower than customer expectations.",
    "kyc_problem": "KYC verification or document handling may be blocking account usage.",
    "login_authentication": "Authentication or account-access flows may be failing for some users.",
    "otp_problem": "OTP delivery or verification may be unreliable during access attempts.",
    "transaction_status": "Transaction status updates or ledger visibility may be inconsistent.",
    "fees": "Fee disclosure or billing communication may be unclear to customers.",
    "customer_support": "Support responsiveness or resolution quality may need improvement.",
    "app_performance": "Application performance or stability may be degraded on some devices.",
    "usability": "Workflow clarity or navigation may be confusing for some users.",
    "security_concern": "Security alerts or account-protection signals may require investigation.",
    "feature_request": "Customers may be requesting additional product capabilities.",
}


@dataclass(frozen=True)
class _ThemeRecordRef:
    feedback_id: str
    role: str  # "primary" or "secondary"
    analysis: AnalysisResult


def _validate_feedback_dataframe(feedback_df: pd.DataFrame) -> None:
    if feedback_df.empty:
        return
    if "feedback_id" not in feedback_df.columns:
        raise KeyError("Feedback DataFrame requires a 'feedback_id' column.")
    if "masked_text" not in feedback_df.columns:
        raise KeyError(MASKED_TEXT_REQUIRED_ERROR)


def _build_feedback_lookup(feedback_df: pd.DataFrame) -> dict[str, pd.Series]:
    lookup: dict[str, pd.Series] = {}
    for _, row in feedback_df.iterrows():
        feedback_id = str(row["feedback_id"]).strip()
        if feedback_id:
            lookup[feedback_id] = row
    return lookup


def _get_masked_text(row: pd.Series) -> str | None:
    return normalize_analysis_text(row.get("masked_text"))


def _quote_supports_theme(theme_name: str, analysis: AnalysisResult) -> bool:
    if analysis.primary_theme == theme_name:
        return True
    return any(item.theme == theme_name for item in analysis.secondary_themes)


def validate_quote(
    quote: str,
    feedback_id: str | None,
    feedback_df: pd.DataFrame,
    theme_name: str | None = None,
    analysis_results: list[AnalysisResult] | None = None,
) -> EvidenceQuote:
    """Validate that a quote is an exact or contiguous excerpt from masked_text."""
    if not feedback_id or not str(feedback_id).strip():
        return EvidenceQuote(
            feedback_id=feedback_id or "",
            quote=quote,
            validation_status="missing_feedback_id",
            validation_message="Quote is missing a feedback ID.",
        )

    clean_id = str(feedback_id).strip()
    lookup = _build_feedback_lookup(feedback_df)
    if clean_id not in lookup:
        return EvidenceQuote(
            feedback_id=clean_id,
            quote=quote,
            validation_status="missing_source",
            validation_message="Feedback ID was not found in the masked feedback DataFrame.",
        )

    row = lookup[clean_id]
    masked_text = _get_masked_text(row)
    if masked_text is None:
        return EvidenceQuote(
            feedback_id=clean_id,
            quote=quote,
            validation_status="invalid",
            validation_message="Masked text is missing for the referenced feedback ID.",
        )

    quote_text = quote.strip()
    if not quote_text:
        return EvidenceQuote(
            feedback_id=clean_id,
            quote=quote,
            validation_status="invalid",
            validation_message="Quote text is empty.",
        )

    is_exact = quote_text == masked_text
    is_excerpt = quote_text in masked_text and len(quote_text) < len(masked_text)
    if not is_exact and not (is_excerpt and quote_text):
        return EvidenceQuote(
            feedback_id=clean_id,
            quote=quote_text,
            source=_optional_str(row.get("source")),
            date=_optional_str(row.get("date")),
            rating=_optional_float(row.get("rating")),
            validation_status="invalid",
            validation_message="Quote is not an exact masked_text match or contiguous excerpt.",
        )

    if theme_name and analysis_results:
        analysis_by_id = {item.feedback_id: item for item in analysis_results}
        analysis = analysis_by_id.get(clean_id)
        if analysis is None or not _quote_supports_theme(theme_name, analysis):
            return EvidenceQuote(
                feedback_id=clean_id,
                quote=quote_text,
                source=_optional_str(row.get("source")),
                date=_optional_str(row.get("date")),
                rating=_optional_float(row.get("rating")),
                validation_status="invalid",
                validation_message="Quote does not support the associated theme.",
            )

    return EvidenceQuote(
        feedback_id=clean_id,
        quote=quote_text,
        source=_optional_str(row.get("source")),
        date=_optional_str(row.get("date")),
        rating=_optional_float(row.get("rating")),
        quote_is_exact=is_exact,
        validation_status="valid",
        validation_message="Quote validated against masked_text.",
    )


def _optional_str(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect_theme_records(
    theme_name: str,
    analysis_results: list[AnalysisResult],
) -> list[_ThemeRecordRef]:
    records: list[_ThemeRecordRef] = []
    for analysis in analysis_results:
        if analysis.primary_theme == theme_name:
            records.append(_ThemeRecordRef(analysis.feedback_id, "primary", analysis))
        elif any(item.theme == theme_name for item in analysis.secondary_themes):
            records.append(_ThemeRecordRef(analysis.feedback_id, "secondary", analysis))
    return records


def select_representative_quotes(
    theme_name: str,
    analysis_results: list[AnalysisResult],
    feedback_df: pd.DataFrame,
    max_quotes: int = MAX_REPRESENTATIVE_QUOTES,
) -> list[EvidenceQuote]:
    """Select up to ``max_quotes`` validated representative masked quotes for a theme."""
    candidates: list[tuple[float, str, AnalysisResult]] = []
    lookup = _build_feedback_lookup(feedback_df)

    for analysis in analysis_results:
        if not _quote_supports_theme(theme_name, analysis):
            continue
        row = lookup.get(analysis.feedback_id)
        if row is None:
            continue
        masked_text = _get_masked_text(row)
        if masked_text is None:
            continue
        candidates.append((analysis.confidence, analysis.feedback_id, analysis))

    candidates.sort(key=lambda item: (-item[0], item[1]))

    selected: list[EvidenceQuote] = []
    seen_quotes: set[str] = set()
    seen_sources: set[str] = set()

    for _, feedback_id, analysis in candidates:
        if len(selected) >= max_quotes:
            break
        row = lookup[feedback_id]
        masked_text = _get_masked_text(row)
        if masked_text is None:
            continue

        quote_text = masked_text if len(masked_text) <= 220 else masked_text[:220].rstrip() + "..."
        if quote_text in seen_quotes:
            continue

        source = _optional_str(row.get("source")) or "unknown"
        if len(seen_sources) < max_quotes and source in seen_sources and len(selected) >= 1:
            continue

        validated = validate_quote(
            quote_text,
            feedback_id,
            feedback_df,
            theme_name=theme_name,
            analysis_results=analysis_results,
        )
        if validated.validation_status != "valid":
            continue

        selected.append(validated)
        seen_quotes.add(validated.quote)
        seen_sources.add(source)

    return selected


def _distribution(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _average_rating(feedback_ids: list[str], feedback_df: pd.DataFrame) -> float | None:
    ratings: list[float] = []
    lookup = _build_feedback_lookup(feedback_df)
    for feedback_id in feedback_ids:
        row = lookup.get(feedback_id)
        if row is None:
            continue
        rating = _optional_float(row.get("rating"))
        if rating is not None:
            ratings.append(rating)
    if not ratings:
        return None
    return round(sum(ratings) / len(ratings), 3)


def _date_metadata(
    feedback_ids: list[str],
    feedback_df: pd.DataFrame,
) -> tuple[dict[str, str | None], dict[str, int]]:
    lookup = _build_feedback_lookup(feedback_df)
    parsed_dates: list[pd.Timestamp] = []
    trend: Counter[str] = Counter()

    for feedback_id in feedback_ids:
        row = lookup.get(feedback_id)
        if row is None:
            continue
        raw_date = _optional_str(row.get("date"))
        if not raw_date:
            continue
        timestamp = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(timestamp):
            continue
        parsed_dates.append(timestamp)
        trend[str(timestamp.date())] += 1

    if not parsed_dates:
        return {"start": None, "end": None}, {}

    ordered = sorted(parsed_dates)
    return (
        {"start": str(ordered[0].date()), "end": str(ordered[-1].date())},
        dict(sorted(trend.items())),
    )


def _severity_for_theme(theme_name: str, analysis: AnalysisResult) -> str:
    if analysis.primary_theme == theme_name:
        return analysis.severity
    for item in analysis.secondary_themes:
        if item.theme == theme_name:
            return item.severity
    return "unknown"


def _confidence_for_theme(theme_name: str, analysis: AnalysisResult) -> float:
    if analysis.primary_theme == theme_name:
        return analysis.primary_confidence
    for item in analysis.secondary_themes:
        if item.theme == theme_name:
            return item.confidence
    return analysis.confidence


def _determine_evidence_strength(
    mention_count: int,
    valid_quotes: list[EvidenceQuote],
    average_confidence: float,
    source_distribution: dict[str, int],
    warnings: list[str],
) -> str:
    """Return prototype evidence strength heuristic (not statistical truth)."""
    if mention_count <= EVIDENCE_WEAK_MAX_MENTIONS:
        return "weak"
    if not valid_quotes or warnings:
        return "weak"
    if average_confidence < 0.35:
        return "weak"

    distinct_sources = len([source for source in source_distribution if source != "unknown"])
    if (
        mention_count >= EVIDENCE_STRONG_MIN_MENTIONS
        and average_confidence >= EVIDENCE_STRONG_MIN_CONFIDENCE
        and len(valid_quotes) >= 2
        and (distinct_sources >= EVIDENCE_STRONG_MIN_SOURCES or distinct_sources == 0)
    ):
        return "strong"

    if mention_count >= EVIDENCE_MODERATE_MIN_MENTIONS:
        return "moderate"

    return "weak"


def _build_possible_root_causes(theme_name: str, mention_count: int) -> list[str]:
    template = ROOT_CAUSE_TEMPLATES.get(
        theme_name,
        "Repeated masked feedback patterns suggest a recurring customer-facing issue.",
    )
    return [
        f"Observed evidence: {mention_count} feedback record(s) mention {theme_name.replace('_', ' ')}.",
        f"Possible interpretation: {template}",
        "This is a suggested interpretation and requires PM validation.",
    ]


def _build_suggested_actions(theme_name: str) -> list[str]:
    rule = THEME_RULES_BY_NAME.get(theme_name)
    if rule and rule.suggested_action_template:
        action = rule.suggested_action_template
    else:
        action = "Review supporting masked feedback and validate the next product investigation step."
    return [
        f"Suggested action: {action}",
        "This is a suggested action, not a confirmed product decision.",
    ]


def validate_theme_evidence(
    theme_insight: ThemeInsight,
    feedback_df: pd.DataFrame,
    analysis_results: list[AnalysisResult] | None = None,
) -> ThemeInsight:
    """Re-validate evidence quotes and refresh representative quote lists."""
    validated_quotes: list[EvidenceQuote] = []
    invalid_count = 0
    warnings = list(theme_insight.warnings)

    quotes_to_validate = theme_insight.evidence_quotes
    if not quotes_to_validate:
        for quote_text in theme_insight.representative_quotes:
            quotes_to_validate.append(
                EvidenceQuote(feedback_id="", quote=quote_text, validation_status="invalid")
            )

    seen: set[tuple[str, str]] = set()
    for evidence_quote in quotes_to_validate:
        result = validate_quote(
            evidence_quote.quote,
            evidence_quote.feedback_id or None,
            feedback_df,
            theme_name=theme_insight.theme_name,
            analysis_results=analysis_results,
        )
        key = (result.feedback_id, result.quote)
        if result.validation_status == "valid" and key not in seen:
            validated_quotes.append(result)
            seen.add(key)
        elif result.validation_status != "valid":
            invalid_count += 1
            warnings.append(result.validation_message)

    return theme_insight.model_copy(
        update={
            "evidence_quotes": validated_quotes,
            "representative_quotes": [item.quote for item in validated_quotes],
            "warnings": sorted(set(warnings)),
            "evidence_strength": "weak" if invalid_count and not validated_quotes else theme_insight.evidence_strength,
        }
    )


def aggregate_theme_insights(
    analysis_results: list[AnalysisResult],
    feedback_df: pd.DataFrame,
) -> ThemeAggregationResult:
    """Aggregate Phase 4 analysis results into evidence-backed theme insights."""
    _validate_feedback_dataframe(feedback_df)

    warnings: list[str] = []
    if feedback_df.empty:
        warnings.append("Empty feedback DataFrame received; no theme insights generated.")
        return ThemeAggregationResult(
            insights=[],
            total_valid_feedback_records=0,
            excluded_analysis_results=0,
            invalid_quotes=0,
            warnings=warnings,
        )

    feedback_lookup = _build_feedback_lookup(feedback_df)
    valid_ids = set(feedback_lookup.keys())
    total_valid = len(valid_ids)

    usable_results: list[AnalysisResult] = []
    excluded = 0
    for result in analysis_results:
        if result.feedback_id not in valid_ids:
            excluded += 1
            warnings.append(
                f"Analysis result for feedback_id '{result.feedback_id}' excluded: "
                "ID not found in masked feedback DataFrame."
            )
            continue
        usable_results.append(result)

    theme_refs: dict[str, list[_ThemeRecordRef]] = defaultdict(list)
    for analysis in usable_results:
        if analysis.primary_theme not in EXCLUDED_AGGREGATION_THEMES:
            theme_refs[analysis.primary_theme].append(
                _ThemeRecordRef(analysis.feedback_id, "primary", analysis)
            )
        for secondary in analysis.secondary_themes:
            if secondary.theme not in EXCLUDED_AGGREGATION_THEMES:
                theme_refs[secondary.theme].append(
                    _ThemeRecordRef(analysis.feedback_id, "secondary", analysis)
                )

    invalid_quotes = 0
    insights: list[ThemeInsight] = []

    for theme_name in sorted(theme_refs.keys()):
        refs = theme_refs[theme_name]
        primary_ids = {ref.feedback_id for ref in refs if ref.role == "primary"}
        secondary_ids = {
            ref.feedback_id
            for ref in refs
            if ref.role == "secondary" and ref.feedback_id not in primary_ids
        }
        mention_ids = sorted(primary_ids | secondary_ids)

        primary_count = len(primary_ids)
        secondary_count = len(secondary_ids)
        mention_count = len(mention_ids)
        feedback_percentage = round((mention_count / total_valid) * 100, 2) if total_valid else 0.0

        analyses_for_theme = [ref.analysis for ref in refs]
        unique_analyses = {analysis.feedback_id: analysis for analysis in analyses_for_theme}

        sentiments = [analysis.sentiment for analysis in unique_analyses.values()]
        severities = [_severity_for_theme(theme_name, analysis) for analysis in unique_analyses.values()]
        sources = [
            _optional_str(feedback_lookup[fid].get("source")) or "unknown" for fid in mention_ids
        ]
        segments = []
        if "user_type" in feedback_df.columns:
            segments = [
                _optional_str(feedback_lookup[fid].get("user_type")) or "unknown"
                for fid in mention_ids
            ]

        confidences = [_confidence_for_theme(theme_name, analysis) for analysis in unique_analyses.values()]
        average_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0

        evidence_quotes = select_representative_quotes(
            theme_name,
            list(unique_analyses.values()),
            feedback_df,
        )
        invalid_for_theme = 0
        validated_quote_texts: list[str] = []
        for quote in evidence_quotes:
            if quote.validation_status != "valid":
                invalid_for_theme += 1
            else:
                validated_quote_texts.append(quote.quote)

        invalid_quotes += invalid_for_theme
        source_distribution = _distribution(sources)
        date_range, trend_data = _date_metadata(mention_ids, feedback_df)

        theme_warnings: list[str] = []
        if mention_count <= EVIDENCE_WEAK_MAX_MENTIONS:
            theme_warnings.append(
                f"Fewer than {EVIDENCE_MODERATE_MIN_MENTIONS} supporting records; evidence strength is limited."
            )
        if not validated_quote_texts:
            theme_warnings.append("No valid masked representative quotes available.")

        evidence_strength = _determine_evidence_strength(
            mention_count=mention_count,
            valid_quotes=evidence_quotes,
            average_confidence=average_confidence,
            source_distribution=source_distribution,
            warnings=theme_warnings,
        )

        insight = ThemeInsight(
            theme_name=theme_name,
            primary_count=primary_count,
            secondary_count=secondary_count,
            mention_count=mention_count,
            feedback_percentage=feedback_percentage,
            average_rating=_average_rating(mention_ids, feedback_df),
            sentiment_distribution=_distribution(sentiments),
            severity_distribution=_distribution(severities),
            source_distribution=source_distribution,
            segment_distribution=_distribution(segments) if segments else {},
            date_range=date_range,
            trend_data=trend_data,
            representative_quotes=validated_quote_texts,
            evidence_quotes=[quote for quote in evidence_quotes if quote.validation_status == "valid"],
            source_feedback_ids=mention_ids,
            possible_root_causes=_build_possible_root_causes(theme_name, mention_count),
            suggested_product_actions=_build_suggested_actions(theme_name),
            evidence_strength=evidence_strength,  # type: ignore[arg-type]
            confidence=average_confidence,
            human_review_status="pending",
            warnings=theme_warnings,
        )
        insights.append(insight)

    insights.sort(key=lambda item: (-item.mention_count, item.theme_name))

    return ThemeAggregationResult(
        insights=insights,
        total_valid_feedback_records=total_valid,
        excluded_analysis_results=excluded,
        invalid_quotes=invalid_quotes,
        warnings=sorted(set(warnings)),
    )


def insight_contains_forbidden_pii(insight: ThemeInsight) -> bool:
    """Return True if insight text appears to contain unmasked PII markers."""
    blob = " ".join(
        insight.representative_quotes
        + [quote.quote for quote in insight.evidence_quotes]
        + insight.possible_root_causes
        + insight.suggested_product_actions
    )
    if "@" in blob and not any(token in blob for token in PII_MASK_TOKENS.values()):
        return True
    return False
