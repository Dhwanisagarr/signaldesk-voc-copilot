"""Import Data Page for SignalDesk – Ingestion, Taxonomy Selection & Quality Audit."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import MAX_UPLOAD_SIZE_BYTES, MAX_UPLOAD_SIZE_MB
from src.data_loader import (
    DataLoaderError,
    EmptyFileError,
    FileTooLargeError,
    InvalidFileTypeError,
    read_csv_input,
)
from src.taxonomy_loader import TAXONOMY_PRESETS
from src.ui_components import render_sidebar_footer
from src.ui_helpers import (
    NOT_MAPPED_LABEL,
    SESSION_AGGREGATION,
    SESSION_ANALYSIS,
    SESSION_ANALYSIS_COMPLETE,
    SESSION_COLUMN_MAPPING,
    SESSION_DQ_CONTINUED,
    SESSION_LOAD_RESULT,
    SESSION_MASKED_DF,
    SESSION_PIPELINE_ERROR,
    SESSION_TAXONOMY,
    SESSION_THEME_INSIGHTS,
    SESSION_UPLOAD_BYTES,
    SESSION_UPLOAD_NAME,
    apply_masking,
    build_mapping_from_selections,
    internal_field_options,
    load_uploaded_feedback,
    run_analysis_pipeline,
    try_infer_column_mapping,
    validate_csv_filename,
)


def main() -> None:
    st.title("1. Import customer feedback data")
    st.caption("Upload your CSV export, choose your domain taxonomy, and let SignalDesk extract prioritized product problems.")

    st.divider()

    # 1. Primary Ingestion Inputs: CSV Upload & Taxonomy Preset
    c_file, c_tax = st.columns([3, 2])

    with c_file:
        uploaded = st.file_uploader(
            "Drop your CSV export here or browse files",
            type=["csv"],
            help=f"CSV files up to {MAX_UPLOAD_SIZE_MB} MB are supported.",
        )

    with c_tax:
        curr_tax = st.session_state.get(SESSION_TAXONOMY, "fintech")
        tax_keys = list(TAXONOMY_PRESETS.keys())
        selected_tax = st.selectbox(
            "Domain Taxonomy Preset",
            options=tax_keys,
            index=tax_keys.index(curr_tax) if curr_tax in tax_keys else 0,
            format_func=lambda k: TAXONOMY_PRESETS.get(k, k),
            help="Select the domain-specific rule dictionary used to categorize feedback themes.",
        )
        st.session_state[SESSION_TAXONOMY] = selected_tax

    if uploaded is not None:
        if not validate_csv_filename(uploaded.name):
            st.error("Only CSV files are supported.")
            return
        upload_bytes = uploaded.getvalue()
        if len(upload_bytes) > MAX_UPLOAD_SIZE_BYTES:
            st.error(f"File exceeds maximum size limit of {MAX_UPLOAD_SIZE_MB} MB.")
            return

        st.session_state[SESSION_UPLOAD_BYTES] = upload_bytes
        st.session_state[SESSION_UPLOAD_NAME] = uploaded.name
        st.session_state[SESSION_LOAD_RESULT] = None
        st.session_state[SESSION_DQ_CONTINUED] = False
        st.session_state[SESSION_MASKED_DF] = None
        st.session_state[SESSION_ANALYSIS_COMPLETE] = False

    upload_bytes = st.session_state.get(SESSION_UPLOAD_BYTES)
    if not upload_bytes:
        st.info("Upload a CSV file using the box above to begin analysis.")
        render_sidebar_footer()
        return

    # Ingestion & Column Mapping
    try:
        read_result = read_csv_input(upload_bytes)
        inferred, infer_error = try_infer_column_mapping(read_result.dataframe)
        mapping_to_use = inferred

        if infer_error:
            st.warning(f"Column mapping is ambiguous: {infer_error}")
            with st.expander("Map CSV Columns", expanded=True):
                normalized_cols = list(read_result.dataframe.columns)
                options = [NOT_MAPPED_LABEL, *normalized_cols]
                selections: dict[str, str | None] = {}
                for field in internal_field_options():
                    label = f"{field} *" if field in {"feedback_id", "feedback_text"} else field
                    selections[field] = st.selectbox(label, options, key=f"map_sel_{field}")
                if st.button("Apply mapping", type="secondary"):
                    mapping_to_use = build_mapping_from_selections(selections)

        if mapping_to_use and st.session_state.get(SESSION_LOAD_RESULT) is None:
            st.session_state[SESSION_COLUMN_MAPPING] = mapping_to_use
            st.session_state[SESSION_LOAD_RESULT] = load_uploaded_feedback(
                upload_bytes, mapping_to_use
            )

    except (FileTooLargeError, EmptyFileError, InvalidFileTypeError, DataLoaderError, ValueError) as exc:
        st.error(str(exc))
        render_sidebar_footer()
        return
    except Exception:
        st.error("Unable to parse the uploaded CSV file.")
        render_sidebar_footer()
        return

    load_result = st.session_state.get(SESSION_LOAD_RESULT)
    if load_result is None:
        render_sidebar_footer()
        return

    report = load_result.report

    st.divider()

    # 2. Dataset Health Summary
    st.markdown("### Dataset Health & Privacy Audit")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Rows", report.total_rows)
    c2.metric("Valid Feedback Rows", report.valid_rows)
    c3.metric("Excluded Rows", report.invalid_rows)
    c4.metric("Active Taxonomy", TAXONOMY_PRESETS.get(selected_tax, selected_tax))

    # Data Preview Expander
    with st.expander("Data preview & validation details"):
        st.dataframe(read_result.dataframe.head(5), width="stretch")
        if report.row_issues:
            issues_df = pd.DataFrame([issue.model_dump() for issue in report.row_issues])
            st.caption(f"Validation warnings ({len(report.row_issues)}):")
            st.dataframe(issues_df, width="stretch", hide_index=True)

    if report.valid_rows == 0:
        st.error("No valid customer feedback rows found in the CSV.")
        render_sidebar_footer()
        return

    # PII Masking Prep
    if st.session_state.get(SESSION_MASKED_DF) is None:
        masked_df = apply_masking(load_result.valid_rows)
        st.session_state[SESSION_MASKED_DF] = masked_df
    else:
        masked_df = st.session_state[SESSION_MASKED_DF]

    st.divider()

    # 3. Run Analysis Action
    st.markdown("### Run Analysis")
    if st.button("Run analysis →", type="primary", width="stretch"):
        st.session_state[SESSION_PIPELINE_ERROR] = None
        progress_bar = st.progress(0)

        with st.status("Extracting product insights...", expanded=True) as status:
            st.write("✓ Verifying data quality & privacy boundaries")
            progress_bar.progress(25)

            st.write(f"✓ Applying '{TAXONOMY_PRESETS.get(selected_tax, selected_tax)}' taxonomy rules")
            progress_bar.progress(50)

            st.write("✓ Aggregating customer evidence & representative quotes")
            progress_bar.progress(75)

            st.write("✓ Prioritizing problems by urgency & impact")
            progress_bar.progress(95)

            try:
                bundle = run_analysis_pipeline(masked_df, taxonomy_preset=selected_tax)
                st.session_state[SESSION_MASKED_DF] = bundle.masked_df
                st.session_state[SESSION_ANALYSIS] = bundle.analysis
                st.session_state[SESSION_AGGREGATION] = bundle.aggregation
                st.session_state[SESSION_THEME_INSIGHTS] = bundle.insights
                st.session_state[SESSION_ANALYSIS_COMPLETE] = True

                progress_bar.progress(100)
                status.update(label="Analysis complete!", state="complete", expanded=False)
                st.success("Analysis complete! Navigating to Insight Workspace...")
                st.switch_page("pages/02_Workspace.py")
            except Exception as exc:
                st.session_state[SESSION_PIPELINE_ERROR] = str(exc)
                status.update(label="Analysis error encountered.", state="error")
                st.error(f"Analysis error: {exc}")

    render_sidebar_footer()


if __name__ == "__main__":
    main()
