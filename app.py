"""SignalDesk Streamlit dashboard – Phase 6 end-to-end user workflow."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import (
    APP_TITLE,
    EVALUATION_SET_PATH,
    MAX_UPLOAD_SIZE_MB,
    SAMPLE_FEEDBACK_PATH,
    SUPPORTED_REVIEW_STATUSES,
)
from src.data_loader import (
    DataLoaderError,
    EmptyFileError,
    FileTooLargeError,
    InvalidFileTypeError,
    read_csv_input,
)
from src.ui_helpers import (
    NOT_MAPPED_LABEL,
    SESSION_ANALYSIS,
    SESSION_ANALYSIS_COMPLETE,
    SESSION_AGGREGATION,
    SESSION_COLUMN_MAPPING,
    SESSION_DQ_CONTINUED,
    SESSION_LOAD_RESULT,
    SESSION_MASKED_DF,
    SESSION_PIPELINE_ERROR,
    SESSION_REVIEWER_NOTES,
    SESSION_REVIEW_STATUSES,
    SESSION_TEMP_WARNINGS,
    SESSION_THEME_INSIGHTS,
    SESSION_UPLOAD_BYTES,
    SESSION_UPLOAD_NAME,
    apply_masking,
    build_feedback_explorer_dataframe,
    build_mapping_from_selections,
    clear_session_data,
    count_evidence_warnings,
    count_pii_entity_types,
    filter_feedback_explorer,
    format_distribution,
    format_review_status_label,
    format_theme_label,
    get_reviewer_note,
    get_review_status,
    init_session_state,
    insight_display_warnings,
    internal_field_options,
    load_uploaded_feedback,
    pii_summary_metrics,
    priority_disclaimer,
    run_analysis_pipeline,
    set_review_status,
    set_reviewer_note,
    theme_insights_table_rows,
    try_infer_column_mapping,
    validate_csv_filename,
)

NAV_SECTIONS: tuple[str, ...] = (
    "Home",
    "Upload & mapping",
    "Data quality",
    "Privacy & masking",
    "Feedback explorer",
    "Theme insights",
    "Theme detail",
    "Review",
    "Limitations & methodology",
)


def _configure_page() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")


def _sidebar_navigation() -> str:
    st.sidebar.title("SignalDesk")
    st.sidebar.caption("Voice-of-Customer Copilot")
    section = st.sidebar.radio("Navigate", NAV_SECTIONS, label_visibility="collapsed")
    st.sidebar.divider()
    if st.sidebar.button("Clear session data", type="primary", use_container_width=True):
        clear_session_data(st.session_state)
        st.sidebar.success("Session cleared.")
        st.rerun()
    st.sidebar.caption(
        "Uploaded data and review decisions exist only in this browser session."
    )
    return section


def _render_home() -> None:
    st.title(APP_TITLE)
    st.markdown(
        """
**CSV-first, evidence-focused VoC analysis for product managers.**

| | |
|---|---|
| **Target user** | Product managers, founders, and customer-support leaders |
| **Initial use case** | Synthetic Indian fintech feedback (payments, refunds, KYC, security) |
| **Dataset limitation** | Results describe **only the uploaded dataset** — not all customers |
| **Analysis mode** | Local, deterministic rule-based processing — no external APIs or LLMs |
"""
    )
    st.warning(
        "Portfolio prototype — outputs are illustrative and require PM judgment. "
        "Do not treat prioritization scores or suggested actions as confirmed product decisions."
    )

    col1, col2 = st.columns(2)
    with col1:
        sample_bytes = SAMPLE_FEEDBACK_PATH.read_bytes()
        st.download_button(
            "Download sample feedback CSV",
            data=sample_bytes,
            file_name=SAMPLE_FEEDBACK_PATH.name,
            mime="text/csv",
            use_container_width=True,
        )
    with col2:
        eval_bytes = EVALUATION_SET_PATH.read_bytes()
        st.download_button(
            "Download evaluation dataset (for testing)",
            data=eval_bytes,
            file_name=EVALUATION_SET_PATH.name,
            mime="text/csv",
            use_container_width=True,
        )

    st.info(
        "Workflow: upload a CSV → review mapping → check data quality → "
        "review PII masking → run analysis → explore themes and evidence → "
        "record in-session review decisions."
    )


def _render_upload_mapping() -> None:
    st.header("Upload & column mapping")
    st.caption(f"CSV only · maximum {MAX_UPLOAD_SIZE_MB} MB · data stays in memory")

    uploaded = st.file_uploader("Upload feedback CSV", type=["csv"])
    if uploaded is not None:
        if not validate_csv_filename(uploaded.name):
            st.error("Only CSV files are supported.")
            return
        st.session_state[SESSION_UPLOAD_BYTES] = uploaded.getvalue()
        st.session_state[SESSION_UPLOAD_NAME] = uploaded.name
        st.session_state[SESSION_LOAD_RESULT] = None
        st.session_state[SESSION_DQ_CONTINUED] = False
        st.session_state[SESSION_MASKED_DF] = None
        st.session_state[SESSION_ANALYSIS_COMPLETE] = False

    upload_bytes = st.session_state.get(SESSION_UPLOAD_BYTES)
    if not upload_bytes:
        st.info("Upload a CSV file to begin.")
        return

    st.success(f"File loaded in memory: **{st.session_state.get(SESSION_UPLOAD_NAME, 'upload.csv')}**")

    try:
        read_result = read_csv_input(upload_bytes)
        preview_df = read_result.dataframe.head(5)
        st.subheader("Preview (first 5 rows)")
        st.dataframe(preview_df, use_container_width=True)

        inferred, infer_error = try_infer_column_mapping(read_result.dataframe)
        if infer_error:
            st.warning(f"Automatic mapping is ambiguous: {infer_error}")
            st.subheader("Manual column mapping")
            normalized_cols = list(read_result.dataframe.columns)
            options = [NOT_MAPPED_LABEL, *normalized_cols]
            selections: dict[str, str | None] = {}
            for field in internal_field_options():
                default = NOT_MAPPED_LABEL
                if inferred:
                    for src, tgt in inferred.items():
                        if tgt == field:
                            default = src
                            break
                label = f"{field} *" if field in {"feedback_id", "feedback_text"} else field
                selections[field] = st.selectbox(label, options, index=options.index(default) if default in options else 0, key=f"map_{field}")
            if st.button("Apply mapping and validate", type="primary"):
                try:
                    mapping = build_mapping_from_selections(selections)
                    st.session_state[SESSION_COLUMN_MAPPING] = mapping
                    st.session_state[SESSION_LOAD_RESULT] = load_uploaded_feedback(
                        upload_bytes, mapping
                    )
                    st.session_state[SESSION_DQ_CONTINUED] = False
                    st.success("Mapping applied. Continue to **Data quality**.")
                except (DataLoaderError, ValueError) as exc:
                    st.error(str(exc))
        else:
            st.subheader("Inferred column mapping")
            mapping_df = pd.DataFrame(
                [{"source_column": src, "internal_field": tgt} for src, tgt in sorted(inferred.items())]
            )
            st.dataframe(mapping_df, use_container_width=True, hide_index=True)
            if st.button("Confirm mapping and validate", type="primary"):
                st.session_state[SESSION_COLUMN_MAPPING] = inferred
                st.session_state[SESSION_LOAD_RESULT] = load_uploaded_feedback(
                    upload_bytes, inferred
                )
                st.session_state[SESSION_DQ_CONTINUED] = False
                st.success("Validation complete. Continue to **Data quality**.")
    except (FileTooLargeError, EmptyFileError, InvalidFileTypeError, DataLoaderError) as exc:
        st.error(str(exc))
    except Exception:
        st.error("Unable to parse the uploaded CSV. Check the file format and encoding.")
        st.code("Error details are hidden to protect customer text.", language="text")


def _get_load_result():
    return st.session_state.get(SESSION_LOAD_RESULT)


def _render_data_quality() -> None:
    st.header("Data quality")
    load_result = _get_load_result()
    if load_result is None:
        st.info("Upload and validate a CSV in **Upload & mapping** first.")
        return

    report = load_result.report
    c1, c2, c3 = st.columns(3)
    c1.metric("Total rows", report.total_rows)
    c2.metric("Valid rows", report.valid_rows)
    c3.metric("Invalid rows", report.invalid_rows)

    st.subheader("Quality summary")
    summary = {
        "Empty feedback rows": report.empty_feedback_rows,
        "Duplicate ID rows": report.duplicate_id_rows,
        "Duplicate text rows": report.duplicate_text_rows,
        "Invalid ratings": report.invalid_rating_rows,
        "Invalid dates": report.invalid_date_rows,
        "Detected encoding": report.detected_encoding,
        "File size (bytes)": report.file_size_bytes,
    }
    st.json(summary)

    if report.missing_optional_columns:
        st.caption(f"Missing optional columns: {', '.join(report.missing_optional_columns)}")

    if report.warnings:
        for warning in report.warnings:
            st.warning(warning)
    if report.errors:
        for error in report.errors:
            st.error(error)

    if report.row_issues:
        with st.expander(f"Row-level issues ({len(report.row_issues)})"):
            issues_df = pd.DataFrame([issue.model_dump() for issue in report.row_issues])
            st.dataframe(issues_df, use_container_width=True, hide_index=True)

    blocking = bool(report.missing_required_columns) or bool(report.errors)
    if blocking:
        st.error("Cannot continue — fix required columns or parsing errors and re-upload.")
        if st.button("Start over"):
            clear_session_data(st.session_state)
            st.rerun()
        return

    if report.valid_rows == 0:
        st.error("No valid rows to process.")
        return

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Continue with valid rows", type="primary", use_container_width=True):
            st.session_state[SESSION_DQ_CONTINUED] = True
            st.session_state[SESSION_MASKED_DF] = None
            st.session_state[SESSION_ANALYSIS_COMPLETE] = False
            st.success(f"Continuing with {report.valid_rows} valid row(s). Open **Privacy & masking**.")
    with col_b:
        if st.button("Start over", use_container_width=True):
            clear_session_data(st.session_state)
            st.rerun()

    if st.session_state.get(SESSION_DQ_CONTINUED):
        st.info("Valid rows selected — proceed to Privacy & masking.")


def _ensure_masking() -> pd.DataFrame | None:
    load_result = _get_load_result()
    if load_result is None or not st.session_state.get(SESSION_DQ_CONTINUED):
        return None
    if st.session_state.get(SESSION_MASKED_DF) is not None:
        return st.session_state[SESSION_MASKED_DF]
    try:
        masked = apply_masking(load_result.valid_rows)
        st.session_state[SESSION_MASKED_DF] = masked
        return masked
    except Exception as exc:
        st.session_state[SESSION_PIPELINE_ERROR] = str(exc)
        return None


def _render_privacy_masking() -> None:
    st.header("Privacy & masking")
    if not st.session_state.get(SESSION_DQ_CONTINUED):
        st.info("Complete **Data quality** and continue with valid rows first.")
        return

    masked_df = _ensure_masking()
    if masked_df is None:
        st.error("PII masking could not be applied.")
        return

    metrics = pii_summary_metrics(masked_df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Records checked", metrics["records_checked"])
    c2.metric("Records with PII", metrics["records_with_pii"])
    c3.metric("Requiring review", metrics["records_requiring_review"])

    entity_counts = count_pii_entity_types(masked_df)
    if entity_counts:
        st.subheader("Entity-type counts")
        st.json(entity_counts)
    else:
        st.caption("No PII entity types detected.")

    st.markdown(
        """
**Privacy notes**
- Analysis and dashboard display use **`masked_text` only** — raw customer text is never displayed in the UI.
- This prototype does **not** guarantee complete anonymization.
- Session data is kept **in memory** for the current browser session only.
"""
    )

    with st.expander("Sample masked records (safe fields)"):
        display_cols = [
            col
            for col in ["feedback_id", "source", "date", "rating", "pii_detected", "pii_entity_types"]
            if col in masked_df.columns
        ]
        sample = masked_df[display_cols].head(10) if display_cols else masked_df.head(10)
        st.dataframe(sample, use_container_width=True, hide_index=True)

        st.caption("Masked text preview:")
        for _, row in masked_df.head(5).iterrows():
            st.text(f"{row.get('feedback_id')}: {str(row.get('masked_text', ''))[:200]}")

    st.divider()
    st.subheader("Run analysis")
    if st.button("Run local analysis", type="primary"):
        _run_analysis(masked_df)


def _run_analysis(masked_df: pd.DataFrame) -> None:
    st.session_state[SESSION_PIPELINE_ERROR] = None
    progress = st.progress(0, text="Starting…")
    steps = [
        "Loading validated records",
        "Masking PII",
        "Running local analysis",
        "Aggregating themes",
        "Calculating priority scores",
    ]
    try:
        for index, step in enumerate(steps):
            progress.progress(int((index + 1) / len(steps) * 100), text=step)
        bundle = run_analysis_pipeline(masked_df)
        st.session_state[SESSION_MASKED_DF] = bundle.masked_df
        st.session_state[SESSION_ANALYSIS] = bundle.analysis
        st.session_state[SESSION_AGGREGATION] = bundle.aggregation
        st.session_state[SESSION_THEME_INSIGHTS] = bundle.insights
        st.session_state[SESSION_ANALYSIS_COMPLETE] = True
        progress.progress(100, text="Complete")
        st.success("Analysis complete. Explore results in Feedback explorer and Theme insights.")
    except KeyError as exc:
        st.session_state[SESSION_PIPELINE_ERROR] = str(exc)
        st.error(str(exc))
    except Exception:
        st.session_state[SESSION_PIPELINE_ERROR] = "Analysis failed."
        st.error("Analysis failed. Error details are hidden to protect customer text.")


def _summary_metrics() -> None:
    load_result = _get_load_result()
    analysis = st.session_state.get(SESSION_ANALYSIS)
    aggregation = st.session_state.get(SESSION_AGGREGATION)
    insights = st.session_state.get(SESSION_THEME_INSIGHTS) or []
    masked_df = st.session_state.get(SESSION_MASKED_DF)

    if load_result is None:
        return

    st.subheader("Session summary")
    cols = st.columns(4)
    cols[0].metric("Uploaded (valid)", load_result.report.valid_rows)
    cols[1].metric("Invalid", load_result.report.invalid_rows)
    if analysis:
        cols[2].metric("Analysed", analysis.analyzed_records)
        cols[3].metric("Human review", analysis.human_review_records)
    if masked_df is not None:
        pii = pii_summary_metrics(masked_df)
        st.caption(
            f"PII detected: {pii['records_with_pii']} · "
            f"Theme insights: {len(insights)} · "
            f"Evidence warnings: {count_evidence_warnings(aggregation)}"
        )


def _render_feedback_explorer() -> None:
    st.header("Feedback explorer")
    _summary_metrics()
    analysis = st.session_state.get(SESSION_ANALYSIS)
    masked_df = st.session_state.get(SESSION_MASKED_DF)
    if not st.session_state.get(SESSION_ANALYSIS_COMPLETE) or analysis is None or masked_df is None:
        st.info("Run analysis from **Privacy & masking** first.")
        return

    explorer_df = build_feedback_explorer_dataframe(analysis, masked_df)
    display_df = explorer_df.drop(columns=["masked_text"], errors="ignore")

    st.subheader("Filters")
    f1, f2, f3 = st.columns(3)
    with f1:
        themes = sorted(display_df["primary_theme"].dropna().unique().tolist())
        sel_themes = st.multiselect("Primary theme", themes)
        sentiments = sorted(display_df["sentiment"].dropna().unique().tolist())
        sel_sentiments = st.multiselect("Sentiment", sentiments)
    with f2:
        severities = sorted(display_df["severity"].dropna().unique().tolist())
        sel_severities = st.multiselect("Severity", severities)
        intents = sorted(display_df["intent"].dropna().unique().tolist())
        sel_intents = st.multiselect("Intent", intents)
    with f3:
        sources = sorted(display_df["source"].dropna().unique().tolist()) if "source" in display_df else []
        sel_sources = st.multiselect("Source", sources)
        human_review = st.selectbox("Human review", ["All", "Yes", "No"])
        pii_filter = st.selectbox("PII detected", ["All", "Yes", "No"])
        methods = sorted(display_df["analysis_method"].dropna().unique().tolist())
        sel_methods = st.multiselect("Analysis method", methods)

    search = st.text_input("Search (feedback ID, masked text, theme, source)")

    filtered = filter_feedback_explorer(
        explorer_df,
        primary_themes=sel_themes or None,
        sentiments=sel_sentiments or None,
        severities=sel_severities or None,
        intents=sel_intents or None,
        sources=sel_sources or None,
        human_review=None if human_review == "All" else human_review,
        pii_detected=None if pii_filter == "All" else pii_filter,
        analysis_methods=sel_methods or None,
        search_query=search,
    )

    st.caption(f"Showing {len(filtered)} of {len(explorer_df)} records")
    st.dataframe(
        filtered.drop(columns=["masked_text"], errors="ignore"),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Record detail (masked text)"):
        ids = filtered["feedback_id"].tolist()
        if ids:
            selected_id = st.selectbox("Feedback ID", ids)
            row = filtered[filtered["feedback_id"] == selected_id].iloc[0]
            st.markdown(f"**Masked text:** {row['masked_text']}")
        else:
            st.caption("No records match the current filters.")


def _render_theme_insights() -> None:
    st.header("Theme insights")
    _summary_metrics()
    insights = st.session_state.get(SESSION_THEME_INSIGHTS)
    if not st.session_state.get(SESSION_ANALYSIS_COMPLETE) or not insights:
        st.info("Run analysis from **Privacy & masking** first.")
        return

    st.caption(priority_disclaimer())
    st.info(
        "A high priority score does not necessarily mean the theme is the most frequent. "
        "Priority combines frequency, severity, and confidence."
    )

    review_statuses = st.session_state.get(SESSION_REVIEW_STATUSES, {})
    rows = theme_insights_table_rows(insights, review_statuses)
    table_df = pd.DataFrame(rows)
    st.dataframe(table_df, use_container_width=True, hide_index=True)

    for insight in insights:
        with st.expander(
            f"{format_theme_label(insight.theme_name)} · "
            f"priority {insight.priority_score:.4f} · "
            f"{insight.mention_count} mentions"
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Mention count", insight.mention_count)
            c2.metric("Primary", insight.primary_count)
            c3.metric("Secondary", insight.secondary_count)
            c4.metric("Priority score", f"{insight.priority_score:.4f}")
            st.caption(priority_disclaimer())
            st.write(f"**Evidence strength:** {insight.evidence_strength}")
            st.write(f"**Confidence:** {insight.confidence:.3f}")
            st.write(
                f"**Valid quotes:** "
                f"{sum(1 for q in insight.evidence_quotes if q.validation_status == 'valid')} · "
                f"**Supporting IDs:** {len(insight.source_feedback_ids)}"
            )
            for warning in insight_display_warnings(insight):
                st.warning(warning)


def _render_theme_detail() -> None:
    st.header("Theme detail")
    insights = st.session_state.get(SESSION_THEME_INSIGHTS)
    if not st.session_state.get(SESSION_ANALYSIS_COMPLETE) or not insights:
        st.info("Run analysis from **Privacy & masking** first.")
        return

    theme_names = [insight.theme_name for insight in insights]
    selected = st.selectbox(
        "Select theme",
        theme_names,
        format_func=format_theme_label,
    )
    insight = next(item for item in insights if item.theme_name == selected)

    st.subheader(format_theme_label(insight.theme_name))
    c1, c2, c3 = st.columns(3)
    c1.metric("Primary count", insight.primary_count)
    c2.metric("Secondary count", insight.secondary_count)
    c3.metric("Mention %", f"{insight.feedback_percentage:.1f}%")

    st.markdown("**Distributions**")
    st.write(f"Sentiment: {format_distribution(insight.sentiment_distribution)}")
    st.write(f"Severity: {format_distribution(insight.severity_distribution)}")
    st.write(f"Source: {format_distribution(insight.source_distribution)}")
    if insight.segment_distribution:
        st.write(f"Segment: {format_distribution(insight.segment_distribution)}")
    if insight.average_rating is not None:
        st.write(f"Average rating: {insight.average_rating:.2f}")

    st.write(f"**Evidence strength:** {insight.evidence_strength}")
    st.write(f"**Confidence:** {insight.confidence:.3f}")

    if insight.priority_components:
        pc = insight.priority_components
        st.markdown("**Priority components**")
        st.json(
            {
                "priority_score": pc.priority_score,
                "frequency_score": pc.frequency_score,
                "severity_score": pc.severity_score,
                "confidence_score": pc.confidence_score,
                "priority_method": pc.priority_method,
                "priority_warning": pc.priority_warning,
            }
        )
        st.caption(pc.priority_warning)

    st.markdown("**Supporting feedback IDs**")
    st.code(", ".join(insight.source_feedback_ids) or "—")

    valid_quotes = [q for q in insight.evidence_quotes if q.validation_status == "valid"]
    st.markdown(f"**Validated masked quotes ({len(valid_quotes)})**")
    for quote in valid_quotes[:3]:
        st.markdown(
            f"- `{quote.feedback_id}` · {quote.validation_status} · "
            f"source: {quote.source or '—'} · date: {quote.date or '—'} · "
            f"rating: {quote.rating if quote.rating is not None else '—'}"
        )
        st.text(quote.quote)

    if insight.possible_root_causes:
        st.markdown("**Possible root causes** *(require PM validation)*")
        for item in insight.possible_root_causes:
            st.write(f"- {item}")

    if insight.suggested_product_actions:
        st.markdown("**Suggested product actions** *(not confirmed decisions)*")
        for item in insight.suggested_product_actions:
            st.write(f"- {item}")

    for warning in insight_display_warnings(insight):
        st.warning(warning)


def _render_review() -> None:
    st.header("Review")
    st.warning("Review decisions are stored only for the current browser session.")

    insights = st.session_state.get(SESSION_THEME_INSIGHTS)
    if not st.session_state.get(SESSION_ANALYSIS_COMPLETE) or not insights:
        st.info("Run analysis first to review theme insights.")
        return

    if st.button("Reset all review states"):
        st.session_state[SESSION_REVIEW_STATUSES] = {}
        st.session_state[SESSION_REVIEWER_NOTES] = {}
        st.success("Review state reset.")
        st.rerun()

    for insight in insights:
        theme = insight.theme_name
        with st.expander(format_theme_label(theme)):
            current = get_review_status(st.session_state, theme)
            st.write(f"Current status: **{format_review_status_label(current)}**")
            new_status = st.selectbox(
                "Review status",
                list(SUPPORTED_REVIEW_STATUSES),
                index=list(SUPPORTED_REVIEW_STATUSES).index(current),
                format_func=format_review_status_label,
                key=f"review_status_{theme}",
            )
            note = st.text_area(
                "Reviewer note",
                value=get_reviewer_note(st.session_state, theme),
                key=f"review_note_{theme}",
            )
            if st.button("Save review", key=f"save_review_{theme}"):
                set_review_status(st.session_state, theme, new_status)
                set_reviewer_note(st.session_state, theme, note)
                st.success("Saved in session (does not modify analysis output).")


def _render_methodology() -> None:
    st.header("Limitations & methodology")
    st.markdown(
        """
### Design principles
- **CSV-first** ingestion with explicit column mapping and data-quality reporting
- **Local rule-based sentiment** — transparent keyword scoring, no LLM
- **Keyword and phrase theme classification** with optional batch TF-IDF fallback
- **Exploratory K-Means clustering** — metadata only; does not alter classifications or priority
- **PII masking** before analysis; downstream steps use `masked_text` only
- **Evidence-linked masked quotes** validated as exact excerpts
- **Transparent prioritization** with visible component scores
- **Unknown** and **human-review** states when confidence is low

### Limitations
- Synthetic sample data only — not representative of all customers
- Public-review selection bias may apply to some feedback sources
- No LLM or external API use in this prototype
- No statistical proof of customer demand or confirmed business impact
- Masking is regex-based and may miss or over-mask edge cases
- Root causes and suggested actions are deterministic templates requiring PM validation
- Review decisions and uploads are **session-only** — not persisted

### Deferred (Phase 7+)
- SQLite persistence, exports (CSV/JSON/PDF), evaluation dashboard, optional LLM layer
"""
    )


def main() -> None:
    _configure_page()
    init_session_state(st.session_state)
    section = _sidebar_navigation()

    renderers = {
        "Home": _render_home,
        "Upload & mapping": _render_upload_mapping,
        "Data quality": _render_data_quality,
        "Privacy & masking": _render_privacy_masking,
        "Feedback explorer": _render_feedback_explorer,
        "Theme insights": _render_theme_insights,
        "Theme detail": _render_theme_detail,
        "Review": _render_review,
        "Limitations & methodology": _render_methodology,
    }
    renderers[section]()


if __name__ == "__main__":
    main()
