"""SignalDesk – Voice-of-Customer Copilot (Overview & Navigation Entrypoint)."""

from __future__ import annotations

from datetime import datetime, timezone
import streamlit as st

from src.config import SAMPLE_FEEDBACK_PATH
from src.ui_components import render_issue_card, render_sidebar_footer
from src.ui_helpers import (
    SESSION_ANALYSIS,
    SESSION_ANALYSIS_COMPLETE,
    SESSION_LOAD_RESULT,
    SESSION_THEME_INSIGHTS,
    init_session_state,
    map_evidence_label,
    map_impact_level,
    sync_review_store_to_session,
)


def _render_overview() -> None:
    st.title("Good morning, Product Manager 👋")
    st.subheader("Here’s what your customers are telling you.")
    st.caption(
        "SignalDesk turns messy customer feedback into prioritized product problems, backed by customer evidence."
    )

    st.divider()

    # Latest Analysis Summary KPIs
    st.markdown("### Latest analysis summary")
    has_analysis = st.session_state.get(SESSION_ANALYSIS_COMPLETE, False)
    insights = st.session_state.get(SESSION_THEME_INSIGHTS) or []
    load_result = st.session_state.get(SESSION_LOAD_RESULT)
    analysis = st.session_state.get(SESSION_ANALYSIS)

    c1, c2, c3, c4, c5 = st.columns(5)

    if has_analysis and load_result and analysis:
        total_resp = load_result.report.total_rows
        num_issues = len(insights)
        high_impact = sum(1 for i in insights if map_impact_level(i) == "High")
        evidence_backed = sum(1 for i in insights if map_evidence_label(i) in {"Strong", "Moderate"})
        neg_count = sum(1 for r in analysis.results if r.sentiment == "negative")
        neg_percentage = round((neg_count / len(analysis.results) * 100)) if analysis.results else 0

        c1.metric("Last Analyzed", datetime.now(timezone.utc).strftime("%b %d, %H:%M UTC"))
        c2.metric("Total Responses", total_resp)
        c3.metric("Customer Issues", num_issues)
        c4.metric("High Impact Issues", high_impact)
        c5.metric("Evidence-Backed", evidence_backed)
        st.caption(f"Negative feedback trend: **{neg_percentage}%** of analyzed responses describe negative sentiment.")
    else:
        c1.metric("Last Analyzed", "Not run yet")
        c2.metric("Total Responses", "—")
        c3.metric("Customer Issues", "—")
        c4.metric("High Impact Issues", "—")
        c5.metric("Evidence-Backed", "—")
        st.info("Upload a CSV file on the **Analyze** page to generate live insights.")
        if st.button("Start analysis →", type="primary", key="home_start_btn"):
            st.switch_page("pages/01_Analyze.py")

    st.divider()

    # "What needs your attention?" Top Customer Issues
    st.markdown("### What needs your attention?")

    if has_analysis and insights:
        top_issues = insights[:3]
        cols = st.columns(3)
        for col, insight in zip(cols, top_issues):
            with col:
                render_issue_card(
                    insight,
                    on_select=lambda name: st.switch_page("pages/02_Issues.py"),
                    key_prefix="home",
                )
    else:
        sample_cards = [
            {
                "name": "Refund Delays",
                "customers": 8,
                "impact": "High",
                "evidence": "Weak",
                "summary": "Customers are repeatedly reporting delayed refunds after cancellation.",
            },
            {
                "name": "Payment Failures",
                "customers": 6,
                "impact": "High",
                "evidence": "Weak",
                "summary": "UPI and card gateway timeout errors occurring during checkout.",
            },
            {
                "name": "Security Concerns",
                "customers": 4,
                "impact": "Medium",
                "evidence": "Strong",
                "summary": "SMS OTP delivery delays and account access verification alerts.",
            },
        ]
        cols = st.columns(3)
        for col, item in zip(cols, sample_cards):
            with col:
                with st.container(border=True):
                    st.markdown(f"#### {item['name']}")
                    ic1, ic2 = st.columns(2)
                    ic1.markdown(f"**Customers:** {item['customers']}")
                    ic2.markdown(f"**Impact:** `{item['impact']}`")
                    st.caption(f"Evidence strength: **{item['evidence']}**")
                    st.write(item["summary"])
                    if st.button("Analyze data to unlock →", key=f"teaser_{item['name']}", width="stretch"):
                        st.switch_page("pages/01_Analyze.py")

    st.divider()

    # Quick Actions
    col_dl, col_go = st.columns(2)
    with col_dl:
        sample_bytes = (
            SAMPLE_FEEDBACK_PATH.read_bytes()
            if SAMPLE_FEEDBACK_PATH.exists()
            else b"feedback_id,feedback_text\nFB-001,Sample feedback"
        )
        st.download_button(
            label="Download sample CSV dataset",
            data=sample_bytes,
            file_name="sample_feedback.csv",
            mime="text/csv",
            width="stretch",
        )
    with col_go:
        if st.button("Upload CSV to Analyze →", type="primary", width="stretch", key="home_upload_go"):
            st.switch_page("pages/01_Analyze.py")

    render_sidebar_footer()


def main() -> None:
    st.set_page_config(
        page_title="SignalDesk – Voice-of-Customer Copilot",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state(st.session_state)
    sync_review_store_to_session(st.session_state)

    # 1. EXACTLY ONE Navigation System via st.navigation
    pages = [
        st.Page(_render_overview, title="Overview", default=True),
        st.Page("pages/01_Analyze.py", title="Analyze"),
        st.Page("pages/02_Issues.py", title="Issues"),
        st.Page("pages/03_Feedback.py", title="Feedback"),
        st.Page("pages/04_Review.py", title="Review"),
        st.Page("pages/05_Reports.py", title="Reports"),
        st.Page("pages/06_About.py", title="About"),
    ]

    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    main()
