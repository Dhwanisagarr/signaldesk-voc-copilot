"""Insight Workspace Page for SignalDesk – Overview, Master-Detail Investigation & Embedded Review."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.theme import (
    eyebrow,
    evidence_badge_kind,
    hero,
    impact_badge_kind,
    quote_block,
    render_badges,
    section_title,
    status_dot_html,
    urgency_badge_kind,
)
from src.ui_components import render_sidebar_footer
from src.ui_helpers import (
    SESSION_AGGREGATION,
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
    issue_short_explanation,
    map_evidence_label,
    map_impact_level,
    map_priority_urgency,
    overview_stats,
    priority_disclaimer,
    set_review_status,
    set_reviewer_note,
)


def _render_evidence_panel(selected_theme: str, cust_count: int) -> None:
    """Render the expandable evidence panel with all supporting customer records."""
    analysis = st.session_state.get(SESSION_ANALYSIS)
    masked_df = st.session_state.get(SESSION_MASKED_DF)
    if analysis is None or masked_df is None:
        st.warning("No customer records available.")
        return

    explorer_df = build_feedback_explorer_dataframe(analysis, masked_df)
    filtered_df = filter_feedback_explorer(explorer_df, primary_themes=[selected_theme])

    q = st.text_input(
        "Search quotes...",
        key=f"drawer_search_{selected_theme}",
        placeholder="Type to filter customer quotes...",
    )
    if q.strip():
        filtered_df = filter_feedback_explorer(filtered_df, search_query=q)

    st.caption(f"Showing **{len(filtered_df)}** of **{cust_count}** redacted customer record(s).")

    if filtered_df.empty:
        st.info("No customer records match your query.")
        return

    for _, row in filtered_df.iterrows():
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
                st.caption(f"`{feedback_id}` · {source_val} · {date_val} · {rating_val}★")
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
    eyebrow("Insight Workspace")

    if not st.session_state.get(SESSION_ANALYSIS_COMPLETE):
        hero(
            "No analysis yet.",
            "Import customer feedback data to see prioritized problems and evidence here.",
        )
        st.write("")
        if st.button("Go to Import Data →", type="primary"):
            st.switch_page("pages/01_Import.py")
        render_sidebar_footer()
        return

    insights = st.session_state.get(SESSION_THEME_INSIGHTS) or []
    if not insights:
        st.warning("No customer issues detected in the dataset.")
        render_sidebar_footer()
        return

    aggregation = st.session_state.get(SESSION_AGGREGATION)

    # --- Overview ---
    hero(
        "What's happening with your customers?",
        "A prioritized view of the problems customers are reporting, backed by evidence.",
    )
    stats = overview_stats(insights, aggregation)
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Customer responses", f"{stats['customer_responses']:,}")
    s2.metric("Issues identified", stats["issues_identified"])
    s3.metric("High-impact issues", stats["high_impact_issues"])
    s4.metric("Evidence-backed issues", stats["evidence_backed_issues"])

    st.divider()

    # Master-Detail Layout
    master_col, detail_col = st.columns([1, 2])

    # Left Column: What needs your attention
    with master_col:
        section_title("What needs your attention?")

        selected_theme = st.session_state.get("selected_theme_detail", insights[0].theme_name)

        for idx, insight in enumerate(insights, 1):
            theme = insight.theme_name
            label = format_theme_label(theme)
            urgency = map_priority_urgency(insight)
            impact = map_impact_level(insight)
            evidence = map_evidence_label(insight)
            cust_count = insight.mention_count
            status = get_review_status(st.session_state, theme)
            is_selected = theme == selected_theme

            with st.container(border=True):
                prefix = "👉 " if is_selected else ""
                st.markdown(f"**{prefix}{idx}. {label}**")
                st.caption(f"{cust_count} customer(s) affected")
                render_badges(
                    (urgency, urgency_badge_kind(urgency)),
                    (impact, impact_badge_kind(impact)),
                    (evidence, evidence_badge_kind(evidence)),
                )
                st.write(issue_short_explanation(insight, label))
                st.markdown(
                    status_dot_html(status, format_review_status_label(status)),
                    unsafe_allow_html=True,
                )

                if st.button(
                    "View issue →",
                    key=f"sel_iss_{theme}",
                    type="primary" if is_selected else "secondary",
                    width="stretch",
                ):
                    st.session_state["selected_theme_detail"] = theme
                    st.rerun()

    # Right Panel: Issue Investigation Workspace
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
        st.caption(f"{cust_count} affected customers · {pct_val} of feedback")
        render_badges(
            (urgency_val, urgency_badge_kind(urgency_val)),
            (f"{impact_val} impact", impact_badge_kind(impact_val)),
            (f"{evidence_val} evidence", evidence_badge_kind(evidence_val)),
        )

        st.divider()

        # 1. What's happening?
        section_title("What's happening?")
        st.write(
            f"**{theme_label}** is a recurring problem affecting {cust_count} customer "
            f"response(s) ({pct_val} of analyzed feedback)."
        )

        # 2. Why does this matter?
        section_title("Why does this matter?")
        neg_reports = insight.sentiment_distribution.get("negative", 0)
        severe_reports = insight.severity_distribution.get("critical", 0) + insight.severity_distribution.get("high", 0)
        top_source = (
            max(insight.source_distribution, key=insight.source_distribution.get)
            if insight.source_distribution
            else "—"
        )
        st.write(
            f"Evidence strength is classified as **{evidence_val.lower()}**, with "
            f"**{severe_reports}** report(s) marked high-severity or critical and "
            f"**{neg_reports}** negative-sentiment mention(s) — mostly via **{top_source.title()}**. "
            "Left unresolved, this keeps showing up in the customer experience."
        )
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Customers", cust_count)
        mc2.metric("Negative tone", neg_reports)
        mc3.metric("Severe reports", severe_reports)
        mc4.metric("Top source", top_source.title())
        st.caption(f"Sentiment breakdown: {format_distribution(insight.sentiment_distribution)}")

        st.divider()

        # 3. What are customers saying?
        section_title("What are customers saying?")
        valid_quotes = [q for q in insight.evidence_quotes if q.validation_status == "valid"]
        if valid_quotes:
            for q in valid_quotes[:3]:
                meta = f"{q.source or '—'} · {q.date or '—'} · {q.rating if q.rating is not None else '—'}★"
                quote_block(q.quote, meta)
        else:
            st.caption("No validated customer quotes available.")

        # 4. Evidence (expandable panel — MVP per spec)
        with st.expander(f"Evidence — all {cust_count} customer records"):
            _render_evidence_panel(selected_theme, cust_count)

        st.divider()

        # 5. What might be causing this? / What should I investigate next?
        section_title("What might be causing this?")
        if insight.possible_root_causes:
            for cause in insight.possible_root_causes:
                st.write(f"- {cause}")
        else:
            st.caption("No hypotheses generated for this issue yet.")

        section_title("What should I investigate next?")
        if insight.suggested_product_actions:
            for idx, action in enumerate(insight.suggested_product_actions, 1):
                st.write(f"{idx}. {action}")
        else:
            st.caption("No suggested next steps available.")

        st.divider()

        # 6. Review decision
        section_title("Review decision")
        st.markdown(
            f"Current status: {status_dot_html(curr_status, format_review_status_label(curr_status))}",
            unsafe_allow_html=True,
        )

        act_col1, act_col2, act_col3 = st.columns(3)
        with act_col1:
            if st.button("Approve", type="primary" if curr_status == "approved" else "secondary", width="stretch", key=f"appr_{selected_theme}"):
                set_review_status(st.session_state, selected_theme, "approved")
                st.success("Issue approved.")
                st.rerun()
        with act_col2:
            if st.button("Needs more evidence", type="primary" if curr_status == "needs_more_evidence" else "secondary", width="stretch", key=f"evid_{selected_theme}"):
                set_review_status(st.session_state, selected_theme, "needs_more_evidence")
                st.warning("Marked as needs more evidence.")
                st.rerun()
        with act_col3:
            if st.button("Reject", type="primary" if curr_status == "rejected" else "secondary", width="stretch", key=f"rej_{selected_theme}"):
                set_review_status(st.session_state, selected_theme, "rejected")
                st.error("Issue rejected.")
                st.rerun()

        curr_note = get_reviewer_note(st.session_state, selected_theme)
        new_note = st.text_area(
            "Reviewer notes",
            value=curr_note,
            placeholder="Add notes for your sprint planning...",
            key=f"note_ws_{selected_theme}",
        )
        if st.button("Save review notes", key=f"save_notes_ws_{selected_theme}"):
            set_reviewer_note(st.session_state, selected_theme, new_note)
            st.success("Review notes saved.")

        st.divider()

        # 7. Methodology (raw scores live ONLY here)
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

    render_sidebar_footer()


if __name__ == "__main__":
    main()
