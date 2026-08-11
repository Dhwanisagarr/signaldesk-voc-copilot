"""Export module for generating privacy-safe, masked VoC reports."""

from __future__ import annotations

from datetime import datetime, timezone
import json

import pandas as pd

from src.schemas import AnalysisPipelineResult, ThemeAggregationResult, ThemeInsight
from src.pii_detector import PII_PATTERN_SPECS


class ExportPrivacyError(Exception):
    """Raised when export validation detects unmasked PII or forbidden original text."""


FORBIDDEN_EXPORT_KEYS: set[str] = {"original_text", "feedback_text"}


def _scan_text_for_unmasked_pii(text: str) -> None:
    if not text:
        return
    for spec in PII_PATTERN_SPECS:
        if spec.entity_type in {"EMAIL", "PHONE", "UPI"}:
            matches = spec.pattern.findall(text)
            if matches:
                raise ExportPrivacyError(
                    f"Export rejected: Detected unmasked {spec.entity_type} in export text."
                )


def validate_export_privacy(data: str | dict | list | pd.DataFrame) -> None:
    """Validate that export data contains no original_text, raw feedback_text, or unmasked PII."""
    if isinstance(data, pd.DataFrame):
        for col in data.columns:
            if str(col) in FORBIDDEN_EXPORT_KEYS:
                raise ExportPrivacyError(
                    f"Export rejected: Forbidden column '{col}' present in export DataFrame."
                )
        for col in data.columns:
            if data[col].dtype == object or str(data[col].dtype) == "string":
                for val in data[col].dropna():
                    if isinstance(val, str):
                        _scan_text_for_unmasked_pii(val)
        return

    if isinstance(data, str):
        _scan_text_for_unmasked_pii(data)
        return

    if isinstance(data, dict):
        for k, v in data.items():
            if str(k) in FORBIDDEN_EXPORT_KEYS:
                raise ExportPrivacyError(
                    f"Export rejected: Forbidden key '{k}' present in export payload."
                )
            validate_export_privacy(v)
        return

    if isinstance(data, list):
        for item in data:
            validate_export_privacy(item)
        return


def export_analyzed_records_csv(
    analysis: AnalysisPipelineResult,
    masked_df: pd.DataFrame,
    review_decisions: dict[str, dict[str, str]] | dict[str, str] | None = None,
) -> str:
    """Export analyzed feedback records as a masked CSV string."""
    if not analysis.results:
        return pd.DataFrame().to_csv(index=False)

    meta = masked_df.set_index("feedback_id", drop=False) if not masked_df.empty else pd.DataFrame()
    decisions = review_decisions or {}

    rows = []
    for result in analysis.results:
        row_meta = meta.loc[result.feedback_id] if result.feedback_id in meta.index else None
        if row_meta is not None and isinstance(row_meta, pd.DataFrame):
            row_meta = row_meta.iloc[0]

        theme = result.primary_theme
        decision_info = decisions.get(theme)
        if isinstance(decision_info, dict):
            status = decision_info.get("status", "pending")
            note = decision_info.get("reviewer_note", "")
        elif isinstance(decision_info, str):
            status = decision_info
            note = ""
        else:
            status = "pending"
            note = ""

        secondary_str = (
            ", ".join(st.theme for st in result.secondary_themes)
            if result.secondary_themes
            else ""
        )
        entity_types_str = ""
        if row_meta is not None:
            et = row_meta.get("pii_entity_types")
            if isinstance(et, list):
                entity_types_str = ", ".join(et)
            elif isinstance(et, str):
                entity_types_str = et

        record = {
            "feedback_id": result.feedback_id,
            "masked_text": row_meta.get("masked_text") if row_meta is not None else "",
            "source": row_meta.get("source") if row_meta is not None else None,
            "date": row_meta.get("date") if row_meta is not None else None,
            "rating": row_meta.get("rating") if row_meta is not None else None,
            "sentiment": result.sentiment,
            "primary_theme": result.primary_theme,
            "secondary_themes": secondary_str,
            "severity": result.severity,
            "intent": result.intent,
            "product_area": result.product_area,
            "confidence": result.confidence,
            "requires_human_review": result.requires_human_review,
            "analysis_method": result.analysis_method,
            "cluster_id": result.cluster_id,
            "pii_detected": bool(row_meta.get("pii_detected", False)) if row_meta is not None else False,
            "pii_entity_types": entity_types_str,
            "review_status": status,
            "reviewer_note": note,
        }
        rows.append(record)

    df = pd.DataFrame(rows)
    validate_export_privacy(df)
    return df.to_csv(index=False)


def export_theme_insights_csv(
    insights: list[ThemeInsight],
    review_decisions: dict[str, dict[str, str]] | dict[str, str] | None = None,
) -> str:
    """Export priority-sorted theme insights as a CSV string."""
    if not insights:
        return pd.DataFrame().to_csv(index=False)

    decisions = review_decisions or {}
    rows = []
    for insight in insights:
        theme = insight.theme_name
        decision_info = decisions.get(theme)
        if isinstance(decision_info, dict):
            status = decision_info.get("status", insight.human_review_status)
            note = decision_info.get("reviewer_note", "")
        elif isinstance(decision_info, str):
            status = decision_info
            note = ""
        else:
            status = insight.human_review_status
            note = ""

        valid_quotes = sum(1 for q in insight.evidence_quotes if q.validation_status == "valid")
        pc = insight.priority_components

        row = {
            "theme_name": insight.theme_name,
            "priority_score": round(insight.priority_score, 4),
            "mention_count": insight.mention_count,
            "primary_count": insight.primary_count,
            "secondary_count": insight.secondary_count,
            "feedback_percentage": round(insight.feedback_percentage, 1),
            "average_rating": round(insight.average_rating, 2) if insight.average_rating is not None else None,
            "evidence_strength": insight.evidence_strength,
            "confidence": round(insight.confidence, 3),
            "review_status": status,
            "reviewer_note": note,
            "valid_quotes_count": valid_quotes,
            "supporting_ids_count": len(insight.source_feedback_ids),
            "frequency_score": pc.frequency_score if pc else None,
            "severity_score": pc.severity_score if pc else None,
            "confidence_score": pc.confidence_score if pc else None,
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    validate_export_privacy(df)
    return df.to_csv(index=False)


def export_theme_insights_json(
    insights: list[ThemeInsight],
    aggregation: ThemeAggregationResult | None = None,
    review_decisions: dict[str, dict[str, str]] | dict[str, str] | None = None,
) -> str:
    """Export theme insights as a formatted JSON string."""
    decisions = review_decisions or {}
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    insight_list = []
    for insight in insights:
        theme = insight.theme_name
        decision_info = decisions.get(theme)
        if isinstance(decision_info, dict):
            status = decision_info.get("status", insight.human_review_status)
            note = decision_info.get("reviewer_note", "")
        elif isinstance(decision_info, str):
            status = decision_info
            note = ""
        else:
            status = insight.human_review_status
            note = ""

        quotes = [
            {
                "feedback_id": q.feedback_id,
                "quote": q.quote,
                "validation_status": q.validation_status,
                "source": q.source,
                "date": q.date,
                "rating": q.rating,
            }
            for q in insight.evidence_quotes
            if q.validation_status == "valid"
        ]

        pc = insight.priority_components
        pc_dict = (
            {
                "priority_score": pc.priority_score,
                "frequency_score": pc.frequency_score,
                "severity_score": pc.severity_score,
                "confidence_score": pc.confidence_score,
                "priority_method": pc.priority_method,
            }
            if pc
            else None
        )

        insight_dict = {
            "theme_name": insight.theme_name,
            "priority_score": insight.priority_score,
            "mention_count": insight.mention_count,
            "primary_count": insight.primary_count,
            "secondary_count": insight.secondary_count,
            "feedback_percentage": insight.feedback_percentage,
            "average_rating": insight.average_rating,
            "evidence_strength": insight.evidence_strength,
            "confidence": insight.confidence,
            "review_status": status,
            "reviewer_note": note,
            "priority_components": pc_dict,
            "source_feedback_ids": insight.source_feedback_ids,
            "evidence_quotes": quotes,
            "sentiment_distribution": insight.sentiment_distribution,
            "severity_distribution": insight.severity_distribution,
            "source_distribution": insight.source_distribution,
            "segment_distribution": insight.segment_distribution,
            "possible_root_causes": insight.possible_root_causes,
            "suggested_product_actions": insight.suggested_product_actions,
        }
        insight_list.append(insight_dict)

    payload = {
        "meta": {
            "exported_at": now_str,
            "total_themes": len(insights),
            "disclaimer": "Results describe patterns in the uploaded dataset only. Suggested actions are prototype outputs and require product-manager validation.",
        },
        "insights": insight_list,
    }

    validate_export_privacy(payload)
    return json.dumps(payload, indent=2)


def export_markdown_report(
    insights: list[ThemeInsight],
    analysis: AnalysisPipelineResult | None = None,
    masked_df: pd.DataFrame | None = None,
    aggregation: ThemeAggregationResult | None = None,
    review_decisions: dict[str, dict[str, str]] | dict[str, str] | None = None,
) -> str:
    """Export an executive Markdown report containing all 19 required sections."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    decisions = review_decisions or {}

    total_uploaded = len(masked_df) if masked_df is not None else 0
    total_analyzed = analysis.analyzed_records if analysis else 0

    lines = []
    lines.append("# SignalDesk – Voice-of-Customer Executive Report")
    lines.append("")
    lines.append(f"**Report generated:** {now_str}")
    lines.append("")
    lines.append("## Dataset Summary")
    lines.append(f"- **Total feedback records (uploaded):** {total_uploaded}")
    lines.append(f"- **Valid records analyzed:** {total_analyzed}")
    lines.append(f"- **Total theme insights:** {len(insights)}")
    lines.append("")

    lines.append("## Theme Insights Overview")
    lines.append("| Theme | Priority | Mentions | Primary | Secondary | % Feedback | Evidence Strength | Status |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for item in insights:
        t_name = item.theme_name
        d_info = decisions.get(t_name)
        if isinstance(d_info, dict):
            st = d_info.get("status", item.human_review_status)
        elif isinstance(d_info, str):
            st = d_info
        else:
            st = item.human_review_status

        lines.append(
            f"| {item.theme_name} | {item.priority_score:.4f} | {item.mention_count} | "
            f"{item.primary_count} | {item.secondary_count} | {item.feedback_percentage:.1f}% | "
            f"{item.evidence_strength} | {st} |"
        )
    lines.append("")

    lines.append("## Detailed Theme Breakdown")
    for item in insights:
        t_name = item.theme_name
        d_info = decisions.get(t_name)
        if isinstance(d_info, dict):
            st = d_info.get("status", item.human_review_status)
            note = d_info.get("reviewer_note", "")
        elif isinstance(d_info, str):
            st = d_info
            note = ""
        else:
            st = item.human_review_status
            note = ""

        lines.append(f"### {item.theme_name.replace('_', ' ').title()}")
        lines.append(f"- **Priority Score:** {item.priority_score:.4f}")
        if item.priority_components:
            pc = item.priority_components
            lines.append(
                f"  - Components: Frequency={pc.frequency_score:.4f}, Severity={pc.severity_score:.4f}, Confidence={pc.confidence_score:.4f}"
            )
        lines.append(f"- **Mention Count:** {item.mention_count} (Primary: {item.primary_count}, Secondary: {item.secondary_count})")
        lines.append(f"- **Feedback Percentage:** {item.feedback_percentage:.1f}%")
        lines.append(f"- **Evidence Strength:** {item.evidence_strength} (Confidence: {item.confidence:.3f})")
        lines.append(f"- **Review Status:** {st}")
        if note:
            lines.append(f"- **Reviewer Note:** {note}")

        lines.append(f"- **Supporting Feedback IDs:** {', '.join(item.source_feedback_ids) if item.source_feedback_ids else 'None'}")

        valid_quotes = [q for q in item.evidence_quotes if q.validation_status == "valid"]
        if valid_quotes:
            lines.append("- **Validated Masked Quotes:**")
            for q in valid_quotes:
                lines.append(f"  - `{q.feedback_id}`: \"{q.quote}\"")

        if item.possible_root_causes:
            lines.append("- **Possible Root Causes (PM Validation Required):**")
            for rc in item.possible_root_causes:
                lines.append(f"  - {rc}")

        if item.suggested_product_actions:
            lines.append("- **Suggested Product Actions (Suggestions Only):**")
            for sa in item.suggested_product_actions:
                lines.append(f"  - {sa}")
        lines.append("")

    lines.append("## Methodology & Limitations")
    lines.append("- All analysis uses local rule-based models and TF-IDF batch processing.")
    lines.append("- Uploaded data and review decisions describe only the current dataset.")
    lines.append("- Heuristic priority scores combine frequency, severity, and confidence.")
    lines.append("")

    lines.append("## Privacy Statement")
    lines.append("Exports contain masked text only. Raw customer feedback text and unmasked PII are never included in export outputs.")
    lines.append("")

    lines.append("> Results describe patterns in the uploaded dataset only. Suggested actions are prototype outputs and require product-manager validation.")
    lines.append("")

    content = "\n".join(lines)
    validate_export_privacy(content)
    return content
