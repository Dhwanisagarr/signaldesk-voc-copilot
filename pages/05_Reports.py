"""Reports Page for SignalDesk – Share Your Findings."""

from __future__ import annotations

import streamlit as st

from src.export import (
    ExportPrivacyError,
    export_analyzed_records_csv,
    export_markdown_report,
    export_theme_insights_csv,
    export_theme_insights_json,
)
from src.review_store import get_all_review_decisions
from src.ui_components import render_sidebar_footer
from src.ui_helpers import (
    SESSION_AGGREGATION,
    SESSION_ANALYSIS,
    SESSION_ANALYSIS_COMPLETE,
    SESSION_MASKED_DF,
    SESSION_THEME_INSIGHTS,
)


def main() -> None:
    st.title("Share your findings")
    st.caption("Download masked reports and dataset exports to share with your team and leadership.")

    st.divider()

    if not st.session_state.get(SESSION_ANALYSIS_COMPLETE):
        st.info("Run analysis on the **Analyze** page first to generate exportable reports.")
        if st.button("Go to Analyze →", type="primary"):
            st.switch_page("pages/01_Analyze.py")
        render_sidebar_footer()
        return

    analysis = st.session_state.get(SESSION_ANALYSIS)
    insights = st.session_state.get(SESSION_THEME_INSIGHTS)
    masked_df = st.session_state.get(SESSION_MASKED_DF)
    aggregation = st.session_state.get(SESSION_AGGREGATION)

    if not analysis or not insights or masked_df is None:
        st.warning("No analyzed results available to export.")
        render_sidebar_footer()
        return

    st.info("Exports contain masked customer information only. Raw feedback text and unmasked PII are excluded.")

    review_decisions = get_all_review_decisions()

    try:
        records_csv = export_analyzed_records_csv(analysis, masked_df, review_decisions)
        theme_csv = export_theme_insights_csv(insights, review_decisions)
        theme_json = export_theme_insights_json(insights, aggregation, review_decisions)
        markdown_doc = export_markdown_report(insights, analysis, masked_df, aggregation, review_decisions)
    except ExportPrivacyError as exc:
        st.error(f"Export rejected due to privacy validation failure: {exc}")
        render_sidebar_footer()
        return

    # Product Report Download Cards
    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.markdown("#### Executive Summary")
            st.caption("A concise report for founders and leadership.")
            st.download_button(
                "Download report",
                data=markdown_doc,
                file_name="voc_executive_report_masked.md",
                mime="text/markdown",
                width="stretch",
                key="rep_md",
            )

        with st.container(border=True):
            st.markdown("#### Customer Evidence CSV")
            st.caption("Detailed customer feedback records with masked text.")
            st.download_button(
                "Download report",
                data=records_csv,
                file_name="customer_evidence_masked.csv",
                mime="text/csv",
                width="stretch",
                key="rep_rec_csv",
            )

    with col2:
        with st.container(border=True):
            st.markdown("#### Issue Summary CSV")
            st.caption("Detailed customer issues and evidence metrics.")
            st.download_button(
                "Download report",
                data=theme_csv,
                file_name="issue_summary_masked.csv",
                mime="text/csv",
                width="stretch",
                key="rep_theme_csv",
            )

        with st.container(border=True):
            st.markdown("#### Structured JSON / API Export")
            st.caption("Structured data format for integrations.")
            st.download_button(
                "Download report",
                data=theme_json,
                file_name="theme_insights_masked.json",
                mime="application/json",
                width="stretch",
                key="rep_json",
            )

    st.divider()

    with st.expander("Privacy & Export Guarantees"):
        st.markdown(
            """
- **Pre-Export Privacy Audit:** All exports undergo automatic validation (`validate_export_privacy`).
- **Masked Data Policy:** Raw `feedback_text`, `original_text`, and unmasked PII tokens (emails, phones, UPI IDs) are strictly excluded from all exported deliverables.
- **Review Decision Sync:** Human review decisions (`approved`, `rejected`, `needs_more_evidence`) and reviewer notes are included in report exports.
"""
        )

    render_sidebar_footer()


if __name__ == "__main__":
    main()
