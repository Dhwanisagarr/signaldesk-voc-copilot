"""Issues Page for SignalDesk – Core Product Screen (Customer Issues)."""

from __future__ import annotations

import streamlit as st

from src.config import SUPPORTED_REVIEW_STATUSES
from src.ui_components import render_sidebar_footer
from src.ui_helpers import (
    SESSION_ANALYSIS_COMPLETE,
    SESSION_THEME_INSIGHTS,
    format_distribution,
    format_review_status_label,
    format_theme_label,
    get_review_status,
    get_reviewer_note,
    map_evidence_label,
    map_impact_level,
    priority_disclaimer,
    set_review_status,
    set_reviewer_note,
)


def main() -> None:
    st.title("Customer issues")
    st.caption("The problems appearing most often in your customer feedback.")

    st.divider()

    if not st.session_state.get(SESSION_ANALYSIS_COMPLETE):
        st.info("No analysis results available yet. Run analysis on the **Analyze** page first.")
        if st.button("Go to Analyze →", type="primary"):
            st.switch_page("pages/01_Analyze.py")
        render_sidebar_footer()
        return

    insights = st.session_state.get(SESSION_THEME_INSIGHTS) or []
    if not insights:
        st.warning("No customer issues detected in the dataset.")
        render_sidebar_footer()
        return

    # Ranked Customer Problems List (Immediate View)
    st.markdown("### Ranked customer problems")

    for idx, insight in enumerate(insights, 1):
        theme = insight.theme_name
        label = format_theme_label(theme)
        impact = map_impact_level(insight)
        evidence = map_evidence_label(insight)
        cust_count = insight.mention_count
        status = get_review_status(st.session_state, theme)

        with st.container(border=True):
            rc1, rc2 = st.columns([3, 1])
            with rc1:
                st.markdown(f"#### {idx}. {label}")
                st.markdown(
                    f"**{impact} impact** · **{cust_count} customers** · Evidence: **{evidence}** · Status: `{format_review_status_label(status)}`"
                )
                explanation = (
                    f"Customers are repeatedly reporting friction and complaints regarding {label.lower()}."
                )
                st.write(explanation)
            with rc2:
                if st.button("View issue →", key=f"view_iss_{theme}", width="stretch"):
                    st.session_state["selected_theme_detail"] = theme

    st.divider()

    # Detailed Issue Investigation Workspace
    selected_theme = st.session_state.get("selected_theme_detail", insights[0].theme_name)
    insight = next((i for i in insights if i.theme_name == selected_theme), insights[0])

    theme_label = format_theme_label(insight.theme_name)
    impact_val = map_impact_level(insight)
    evidence_val = map_evidence_label(insight)
    cust_count = insight.mention_count
    pct_val = f"{insight.feedback_percentage:.1f}%"

    st.markdown(f"# {theme_label}")
    st.markdown(f"**{impact_val} impact** · **{cust_count} customers** · **{pct_val} of feedback**")

    st.divider()

    # 1. Executive Summary
    st.markdown("#### Executive summary")
    summary = (
        f"{theme_label} represents a significant problem affecting {cust_count} customer response(s) "
        f"({pct_val} of analyzed feedback). Evidence strength is classified as **{evidence_val}**."
    )
    st.write(summary)

    # 2. Why This Matters
    st.markdown("#### Why this matters")
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Customers Affected", cust_count)

    neg_reports = insight.sentiment_distribution.get("negative", 0)
    mc2.metric("Negative Reports", neg_reports)

    severe_reports = insight.severity_distribution.get("critical", 0) + insight.severity_distribution.get("high", 0)
    mc3.metric("Severe Reports", severe_reports)

    top_source = (
        max(insight.source_distribution, key=insight.source_distribution.get)
        if insight.source_distribution
        else "—"
    )
    mc4.metric("Most Common Source", top_source.title())

    st.caption(f"Sentiment breakdown: {format_distribution(insight.sentiment_distribution)}")

    st.divider()

    # 3. What Customers Are Saying
    st.markdown("#### What customers are saying")
    valid_quotes = [q for q in insight.evidence_quotes if q.validation_status == "valid"]
    if valid_quotes:
        for q in valid_quotes[:5]:
            with st.container(border=True):
                st.markdown(f'"{q.quote}"')
                st.caption(
                    f"Source: {q.source or '—'} · Date: {q.date or '—'} · Rating: {q.rating if q.rating is not None else '—'}"
                )
    else:
        st.caption("No validated customer quotes available.")

    if st.button("View all related feedback →", key=f"btn_feed_{selected_theme}"):
        st.session_state["filter_theme_feedback"] = selected_theme
        st.switch_page("pages/03_Feedback.py")

    st.divider()

    # 4. What SignalDesk Found & Evidence
    st.markdown("#### What SignalDesk found")
    st.write(
        f"A recurring pattern of customer complaints was identified matching the keyword and phrase triggers for **{theme_label.lower()}**."
    )

    st.markdown("#### Evidence")
    st.write(
        f"Evidence strength is rated **{evidence_val}** based on supporting record volume ({cust_count} responses across {len(insight.source_feedback_ids)} feedback IDs) and classification confidence ({insight.confidence:.2f})."
    )

    # 5. How SignalDesk Calculated This (Technical Expandable)
    with st.expander("How SignalDesk calculated this"):
        pc = insight.priority_components
        if pc:
            st.markdown(
                f"""
- **Frequency score:** `{pc.frequency_score:.4f}`
- **Severity score:** `{pc.severity_score:.4f}`
- **Confidence score:** `{pc.confidence_score:.4f}`
- **Priority formula:** `Priority Score = Frequency Score × Severity Score × Confidence Score`
- **Calculated priority score:** `{pc.priority_score:.4f}`
"""
            )
            st.caption(priority_disclaimer())
        else:
            st.caption("Technical score components not attached.")

    st.divider()

    # 6. Suggested Investigation Areas
    st.markdown("#### Suggested investigation areas")
    st.caption("*(Hypotheses for team investigation — not confirmed product decisions)*")
    if insight.suggested_product_actions:
        for idx, action in enumerate(insight.suggested_product_actions, 1):
            st.write(f"{idx}. {action}")
    else:
        st.write("1. Investigate root cause with customer operations.")
        st.write("2. Audit transaction logs for affected feedback IDs.")
        st.write("3. Review support communication templates.")

    st.divider()

    # 7. Review Actions directly on Issue Detail
    st.markdown("#### Review decision")
    curr_status = get_review_status(st.session_state, selected_theme)
    curr_note = get_reviewer_note(st.session_state, selected_theme)

    st.write(f"Current decision: **{format_review_status_label(curr_status)}**")

    act_col1, act_col2, act_col3 = st.columns(3)
    with act_col1:
        if st.button("Approve insight", type="primary" if curr_status == "approved" else "secondary", width="stretch", key=f"appr_{selected_theme}"):
            set_review_status(st.session_state, selected_theme, "approved")
            st.success("Insight approved.")
            st.rerun()
    with act_col2:
        if st.button("Needs more evidence", type="primary" if curr_status == "needs_more_evidence" else "secondary", width="stretch", key=f"evid_{selected_theme}"):
            set_review_status(st.session_state, selected_theme, "needs_more_evidence")
            st.warning("Marked as needs more evidence.")
            st.rerun()
    with act_col3:
        if st.button("Reject insight", type="primary" if curr_status == "rejected" else "secondary", width="stretch", key=f"rej_{selected_theme}"):
            set_review_status(st.session_state, selected_theme, "rejected")
            st.error("Insight rejected.")
            st.rerun()

    new_note = st.text_area("Reviewer notes", value=curr_note, key=f"note_issue_{selected_theme}")
    if st.button("Save notes", key=f"save_notes_{selected_theme}"):
        set_reviewer_note(st.session_state, selected_theme, new_note)
        st.success("Notes saved.")

    render_sidebar_footer()


if __name__ == "__main__":
    main()
