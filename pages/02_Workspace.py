"""Insight Workspace Page for SignalDesk – Master-Detail View, Inline Evidence Drawer & Embedded Review."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import SUPPORTED_REVIEW_STATUSES
from src.ui_components import render_sidebar_footer
from src.ui_helpers import (
    SESSION_ANALYSIS,
    SESSION_ANALYSIS_COMPLETE,
    SESSION_MASKED_DF,
    SESSION_THEME_INSIGHTS,
    build_feedback_explorer_dataframe,
    filter_feedback_explorer,
    format_distribution,
    format_review_status_label,
    format_theme_label,
    get_review_status,
    get_reviewer_note,
    map_evidence_label,
    map_impact_level,
    map_priority_urgency,
    priority_disclaimer,
    set_review_status,
    set_reviewer_note,
)


def _render_evidence_drawer(selected_theme: str, theme_label: str) -> None:
    """Render inline evidence drawer displaying all supporting customer records."""
    analysis = st.session_state.get(SESSION_ANALYSIS)
    masked_df = st.session_state.get(SESSION_MASKED_DF)
    if analysis is None or masked_df is None:
        st.warning("No customer records available.")
        return

    explorer_df = build_feedback_explorer_dataframe(analysis, masked_df)
    filtered_df = filter_feedback_explorer(
        explorer_df,
        primary_themes=[selected_theme],
    )

    st.markdown(f"### Supporting Customer Evidence for '{theme_label}'")
    st.caption(f"Showing **{len(filtered_df)}** redacted customer records linked to this issue.")

    # Search & filters within drawer
    fc1, fc2 = st.columns([3, 1])
    with fc1:
        q = st.text_input("Search quotes...", key=f"drawer_search_{selected_theme}", placeholder="Type to filter customer quotes...")
    with fc2:
        if st.button("Close drawer ✖", key=f"close_drawer_{selected_theme}"):
            st.session_state["show_evidence_drawer"] = False
            st.rerun()

    if q.strip():
        filtered_df = filter_feedback_explorer(filtered_df, search_query=q)

    st.divider()

    if filtered_df.empty:
        st.info("No customer records match your query.")
        return

    for idx, row in filtered_df.iterrows():
        feedback_id = row["feedback_id"]
        masked_text = row["masked_text"]
        sentiment_tag = str(row["sentiment"]).title()
        severity_tag = str(row["severity"]).title()
        source_val = row.get("source") or "—"
        date_val = row.get("date") or "—"
        rating_val = row.get("rating") if pd.notna(row.get("rating")) else "—"

        with st.container(border=True):
            tc1, tc2 = st.columns([4, 1])
            with tc1:
                st.markdown(f"**`{feedback_id}`** · `{source_val}` · Date: **{date_val}** · Rating: **{rating_val}★**")
                st.markdown(f'"{masked_text}"')
            with tc2:
                st.caption(f"Sentiment: **{sentiment_tag}**")
                st.caption(f"Impact: **{severity_tag}**")

            with st.expander("Analysis details"):
                st.markdown(f"- **Intent:** {str(row.get('intent', '')).title()}")
                st.markdown(f"- **Product Area:** {row.get('product_area', '—')}")
                st.markdown(f"- **Analysis Method:** `{row.get('analysis_method', '—')}`")
                st.markdown(f"- **PII Redacted:** {'Yes' if row.get('pii_detected') else 'No'}")


def main() -> None:
    st.title("2. Insight Workspace")
    st.caption("Prioritized customer problems, verified customer evidence, and roadmap decisions.")

    st.divider()

    if not st.session_state.get(SESSION_ANALYSIS_COMPLETE):
        st.info("No analysis results available yet. Import customer feedback data first.")
        if st.button("Go to Import Data →", type="primary"):
            st.switch_page("pages/01_Import.py")
        render_sidebar_footer()
        return

    insights = st.session_state.get(SESSION_THEME_INSIGHTS) or []
    if not insights:
        st.warning("No customer issues detected in the dataset.")
        render_sidebar_footer()
        return

    # Master-Detail Layout
    master_col, detail_col = st.columns([1, 2])

    # Left Column: Master List of Ranked Issues
    with master_col:
        st.markdown("### Prioritized Problems")

        selected_theme = st.session_state.get("selected_theme_detail", insights[0].theme_name)

        for idx, insight in enumerate(insights, 1):
            theme = insight.theme_name
            label = format_theme_label(theme)
            urgency = map_priority_urgency(insight)
            impact = map_impact_level(insight)
            evidence = map_evidence_label(insight)
            cust_count = insight.mention_count
            status = get_review_status(st.session_state, theme)
            is_selected = (theme == selected_theme)

            card_border = True
            with st.container(border=card_border):
                if is_selected:
                    st.markdown(f"👉 **{idx}. {label}**")
                else:
                    st.markdown(f"**{idx}. {label}**")

                st.markdown(f"`{urgency}` · **{cust_count} customers**")
                st.caption(f"Impact: **{impact}** · Evidence: **{evidence}**")
                st.caption(f"Status: `{format_review_status_label(status)}`")

                if st.button("Inspect issue →", key=f"sel_iss_{theme}", type="primary" if is_selected else "secondary", width="stretch"):
                    st.session_state["selected_theme_detail"] = theme
                    st.session_state["show_evidence_drawer"] = False
                    st.rerun()

    # Right Panel: Issue Detail View
    with detail_col:
        selected_theme = st.session_state.get("selected_theme_detail", insights[0].theme_name)
        insight = next((i for i in insights if i.theme_name == selected_theme), insights[0])

        theme_label = format_theme_label(insight.theme_name)
        urgency_val = map_priority_urgency(insight)
        impact_val = map_impact_level(insight)
        evidence_val = map_evidence_label(insight)
        cust_count = insight.mention_count
        pct_val = f"{insight.feedback_percentage:.1f}%"
        curr_status = get_review_status(st.session_state, selected_theme)

        st.markdown(f"## {theme_label}")
        st.markdown(
            f"`{urgency_val}` · **{impact_val} Impact** · **{cust_count} Affected Customers** ({pct_val} of feedback) · Evidence: **{evidence_val}**"
        )

        st.divider()

        # 1. Executive Problem Summary
        st.markdown("#### Problem narrative")
        summary = (
            f"**{theme_label}** represents a recurring product friction area affecting {cust_count} customer response(s) "
            f"({pct_val} of analyzed feedback). Evidence strength is classified as **{evidence_val}**."
        )
        st.write(summary)

        # 2. Key Metrics
        st.markdown("#### Impact metrics")
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Customers", cust_count)

        neg_reports = insight.sentiment_distribution.get("negative", 0)
        mc2.metric("Negative Tone", neg_reports)

        severe_reports = insight.severity_distribution.get("critical", 0) + insight.severity_distribution.get("high", 0)
        mc3.metric("Severe Reports", severe_reports)

        top_source = (
            max(insight.source_distribution, key=insight.source_distribution.get)
            if insight.source_distribution
            else "—"
        )
        mc4.metric("Top Source", top_source.title())

        st.caption(f"Sentiment breakdown: {format_distribution(insight.sentiment_distribution)}")

        st.divider()

        # 3. Verified Customer Evidence Quotes
        st.markdown("#### Verified customer evidence")
        valid_quotes = [q for q in insight.evidence_quotes if q.validation_status == "valid"]
        if valid_quotes:
            for q in valid_quotes[:3]:
                with st.container(border=True):
                    st.markdown(f'"{q.quote}"')
                    st.caption(
                        f"Source: **{q.source or '—'}** · Date: **{q.date or '—'}** · Rating: **{q.rating if q.rating is not None else '—'}★**"
                    )
        else:
            st.caption("No validated customer quotes available.")

        # Inline Evidence Drawer Trigger
        if st.button(f"View all {cust_count} customer records →", type="primary", key=f"btn_open_drawer_{selected_theme}"):
            st.session_state["show_evidence_drawer"] = True
            st.session_state["drawer_theme"] = selected_theme

        st.divider()

        # 4. Pattern Analysis & Investigation
        st.markdown("#### SignalDesk findings")
        st.write(
            f"Customer complaints repeatedly describe friction and outages regarding **{theme_label.lower()}**."
        )

        st.markdown("#### Suggested investigation areas")
        if insight.suggested_product_actions:
            for idx, action in enumerate(insight.suggested_product_actions, 1):
                st.write(f"{idx}. {action}")

        st.divider()

        # 5. Embedded Review Decision Panel
        st.markdown("#### Team review decision")
        st.write(f"Current Status: **{format_review_status_label(curr_status)}**")

        act_col1, act_col2, act_col3 = st.columns(3)
        with act_col1:
            if st.button("Approve for Roadmap", type="primary" if curr_status == "approved" else "secondary", width="stretch", key=f"appr_{selected_theme}"):
                set_review_status(st.session_state, selected_theme, "approved")
                st.success("Insight approved for roadmap.")
                st.rerun()
        with act_col2:
            if st.button("Needs More Evidence", type="primary" if curr_status == "needs_more_evidence" else "secondary", width="stretch", key=f"evid_{selected_theme}"):
                set_review_status(st.session_state, selected_theme, "needs_more_evidence")
                st.warning("Marked as needs more evidence.")
                st.rerun()
        with act_col3:
            if st.button("Dismiss Issue", type="primary" if curr_status == "rejected" else "secondary", width="stretch", key=f"rej_{selected_theme}"):
                set_review_status(st.session_state, selected_theme, "rejected")
                st.error("Insight dismissed.")
                st.rerun()

        curr_note = get_reviewer_note(st.session_state, selected_theme)
        new_note = st.text_area("Reviewer notes", value=curr_note, placeholder="Add notes for your sprint planning...", key=f"note_ws_{selected_theme}")
        if st.button("Save review notes", key=f"save_notes_ws_{selected_theme}"):
            set_reviewer_note(st.session_state, selected_theme, new_note)
            st.success("Review notes saved to database.")

        st.divider()

        # 6. Methodology & Raw Score Details Expander (RAW SCORES HIDE HERE ONLY)
        with st.expander("Methodology & Score Details"):
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

    # Inline Evidence Drawer Container (renders overlay when active)
    if st.session_state.get("show_evidence_drawer", False):
        st.divider()
        drawer_theme = st.session_state.get("drawer_theme", selected_theme)
        drawer_label = format_theme_label(drawer_theme)
        with st.container(border=True):
            _render_evidence_drawer(drawer_theme, drawer_label)

    render_sidebar_footer()


if __name__ == "__main__":
    main()
