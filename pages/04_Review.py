"""Review Page for SignalDesk – Decision Workspace."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import SUPPORTED_REVIEW_STATUSES
from src.review_store import get_all_review_decisions
from src.ui_components import render_sidebar_footer
from src.ui_helpers import (
    SESSION_ANALYSIS_COMPLETE,
    SESSION_THEME_INSIGHTS,
    clear_review_store,
    format_review_status_label,
    format_theme_label,
    get_review_status,
    get_reviewer_note,
    map_evidence_label,
    map_impact_level,
    set_review_status,
    set_reviewer_note,
)


def main() -> None:
    st.title("Review insights")
    st.caption("Review the issues before sharing them with your team.")

    st.divider()

    insights = st.session_state.get(SESSION_THEME_INSIGHTS) or []
    if not st.session_state.get(SESSION_ANALYSIS_COMPLETE) or not insights:
        st.info("Run analysis on the **Analyze** page first to review customer issues.")
        if st.button("Go to Analyze →", type="primary"):
            st.switch_page("pages/01_Analyze.py")
        render_sidebar_footer()
        return

    # Issue Selector for Workspace
    theme_choices = {format_theme_label(i.theme_name): i.theme_name for i in insights}
    selected_label = st.selectbox("Select issue to review:", options=list(theme_choices.keys()))
    selected_theme = theme_choices[selected_label]
    insight = next(i for i in insights if i.theme_name == selected_theme)

    curr_status = get_review_status(st.session_state, selected_theme)
    curr_note = get_reviewer_note(st.session_state, selected_theme)

    impact_val = map_impact_level(insight)
    evidence_val = map_evidence_label(insight)
    cust_count = insight.mention_count

    st.divider()

    # Decision Workspace Container
    with st.container(border=True):
        st.markdown(f"### {selected_label}")
        st.caption(f"**{cust_count} customers** · **{impact_val} impact** · **{evidence_val} evidence**")

        st.markdown("#### SignalDesk finding")
        st.write(
            f"Customer complaints repeatedly describe friction and outages regarding **{selected_label.lower()}**, "
            f"representing {insight.feedback_percentage:.1f}% of analyzed responses."
        )

        st.markdown("#### Supporting customer quotes")
        valid_quotes = [q for q in insight.evidence_quotes if q.validation_status == "valid"]
        if valid_quotes:
            for q in valid_quotes[:3]:
                st.markdown(f'- *"{q.quote}"* (Source: {q.source or "—"}, Rating: {q.rating if q.rating is not None else "—"})')
        else:
            st.caption("No validated quotes available.")

        st.divider()

        st.markdown("#### Reviewer decision")
        st.write(f"Current decision: **{format_review_status_label(curr_status)}**")

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Approve insight", type="primary" if curr_status == "approved" else "secondary", width="stretch", key=f"rev_appr_{selected_theme}"):
                set_review_status(st.session_state, selected_theme, "approved")
                st.success(f"Approved '{selected_label}'.")
                st.rerun()
        with c2:
            if st.button("Needs more evidence", type="primary" if curr_status == "needs_more_evidence" else "secondary", width="stretch", key=f"rev_evid_{selected_theme}"):
                set_review_status(st.session_state, selected_theme, "needs_more_evidence")
                st.warning(f"Marked '{selected_label}' as needs more evidence.")
                st.rerun()
        with c3:
            if st.button("Reject insight", type="primary" if curr_status == "rejected" else "secondary", width="stretch", key=f"rev_rej_{selected_theme}"):
                set_review_status(st.session_state, selected_theme, "rejected")
                st.error(f"Rejected '{selected_label}'.")
                st.rerun()

        new_note = st.text_area("Reviewer notes", value=curr_note, placeholder="Add notes for your product team...", key=f"note_{selected_theme}")
        if st.button("Save notes", key=f"save_note_{selected_theme}"):
            set_reviewer_note(st.session_state, selected_theme, new_note)
            st.success("Reviewer notes saved to local SQLite store.")

    st.divider()

    # Decision Status Overview Table
    st.markdown("### All Review Decisions")
    saved_decisions = get_all_review_decisions()
    table_rows = []
    for item in insights:
        t_name = item.theme_name
        status = get_review_status(st.session_state, t_name)
        note = get_reviewer_note(st.session_state, t_name)
        updated_at = saved_decisions.get(t_name, {}).get("updated_at", "—")
        table_rows.append(
            {
                "Issue": format_theme_label(t_name),
                "Customers": item.mention_count,
                "Impact": map_impact_level(item),
                "Decision": format_review_status_label(status),
                "Reviewer Note": note if note else "—",
                "Updated At": updated_at,
            }
        )

    df_summary = pd.DataFrame(table_rows)
    st.dataframe(df_summary, width="stretch", hide_index=True)

    st.divider()

    # Database Administration Moved to Quiet Expander
    with st.expander("Database administration"):
        confirm_clear = st.checkbox("I understand this will delete all review decisions from SQLite.")
        if st.button("Clear review store", type="secondary", disabled=not confirm_clear):
            clear_review_store(st.session_state)
            st.success("Review store cleared.")
            st.rerun()

    render_sidebar_footer()


if __name__ == "__main__":
    main()
