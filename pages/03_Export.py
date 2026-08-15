"""Export & Share Page for SignalDesk – Share Your Findings."""

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
from src.theme import eyebrow, hero, section_title
from src.ui_components import render_sidebar_footer
from src.ui_helpers import (
    SESSION_AGGREGATION,
    SESSION_ANALYSIS,
    SESSION_ANALYSIS_COMPLETE,
    SESSION_MASKED_DF,
    SESSION_THEME_INSIGHTS,
)


def main() -> None:
    eyebrow("Export & Share")
    hero(
        "Share your findings.",
        "Turn your analysis into something you can share with your team.",
    )

    st.divider()

    if not st.session_state.get(SESSION_ANALYSIS_COMPLETE):
        st.info("Run analysis on the **Import Data** page first to generate exportable reports.")
        if st.button("Go to Import Data →", type="primary"):
            st.switch_page("pages/01_Import.py")
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

    # 1. Executive Summary Live Preview
    section_title("Executive summary preview")
    with st.container(border=True):
        st.markdown(markdown_doc)

    st.divider()

    # 2. Download Deliverables
    section_title("Download deliverables")
    st.caption(
        "All exports are automatically checked for privacy — raw text and unmasked "
        "personal data are always excluded."
    )

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.markdown("#### Executive Summary")
            st.caption("Markdown report formatted for Notion, GitHub, or slide syncs.")
            st.download_button(
                "Download Markdown Report",
                data=markdown_doc,
                file_name="voc_executive_report_masked.md",
                mime="text/markdown",
                width="stretch",
                key="rep_md",
            )

        with st.container(border=True):
            st.markdown("#### Customer Evidence")
            st.caption("Full customer feedback records with masked text.")
            st.download_button(
                "Download Evidence CSV",
                data=records_csv,
                file_name="customer_evidence_masked.csv",
                mime="text/csv",
                width="stretch",
                key="rep_rec_csv",
            )

    with col2:
        with st.container(border=True):
            st.markdown("#### Issue Summary")
            st.caption("Prioritized customer issues and evidence metrics.")
            st.download_button(
                "Download Issue Summary CSV",
                data=theme_csv,
                file_name="issue_summary_masked.csv",
                mime="text/csv",
                width="stretch",
                key="rep_theme_csv",
            )

        with st.container(border=True):
            st.markdown("#### JSON / Markdown")
            st.caption("Structured JSON dataset format for roadmap tools.")
            st.download_button(
                "Download JSON Dataset",
                data=theme_json,
                file_name="theme_insights_masked.json",
                mime="application/json",
                width="stretch",
                key="rep_json",
            )

    st.divider()

    with st.expander("Privacy & data guarantees"):
        st.markdown(
            """
- **Pre-export privacy audit:** every export is automatically validated before download.
- **Masked data policy:** raw feedback text and unmasked personal data (emails, phones, IDs) are never included.
- **Review decisions:** approved / rejected / needs-more-evidence statuses and reviewer notes are preserved in exports.
"""
        )

    render_sidebar_footer()


if __name__ == "__main__":
    main()
