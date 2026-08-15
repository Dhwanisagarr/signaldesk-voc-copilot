"""Reusable Streamlit UI components for SignalDesk."""

from __future__ import annotations

from typing import Any, Callable, Sequence
import streamlit as st

from src.config import SUPPORTED_REVIEW_STATUSES
from src.schemas import ThemeInsight
from src.theme import evidence_badge_kind, impact_badge_kind, render_badges
from src.ui_helpers import (
    clear_session_data,
    format_review_status_label,
    format_theme_label,
    get_review_status,
    get_reviewer_note,
    init_session_state,
    issue_short_explanation,
    map_evidence_label,
    map_impact_level,
    set_review_status,
    set_reviewer_note,
    sync_review_store_to_session,
)

__all__ = [
    "render_sidebar_footer",
    "render_summary_metrics",
    "render_issue_card",
    "render_filters",
    "render_review_form",
    "render_export_buttons",
]


def render_sidebar_footer() -> None:
    """Render quiet session actions and data persistence notice in the sidebar."""
    init_session_state(st.session_state)
    sync_review_store_to_session(st.session_state)

    st.sidebar.divider()
    if st.sidebar.button("Reset session data", type="secondary", width="stretch"):
        clear_session_data(st.session_state)
        st.sidebar.success("Session reset.")
        st.rerun()

    st.sidebar.caption(
        "Data stays in browser memory. Review decisions are saved automatically."
    )


def render_summary_metrics(metrics: dict[str, Any]) -> None:
    """Render metric cards grid."""
    cols = st.columns(len(metrics))
    for idx, (label, val) in enumerate(metrics.items()):
        cols[idx].metric(label, val)


def render_issue_card(
    insight: ThemeInsight,
    on_select: Callable[[str], None] | None = None,
    key_prefix: str = "card",
) -> None:
    """Render a product issue card: name, customer count, impact, evidence, explanation, CTA."""
    theme_name = insight.theme_name
    theme_label = format_theme_label(theme_name)
    impact = map_impact_level(insight)
    evidence = map_evidence_label(insight)
    customers_count = insight.mention_count

    with st.container(border=True):
        st.markdown(f"#### {theme_label}")
        st.caption(f"{customers_count} customer(s) affected")
        render_badges(
            (f"{impact} impact", impact_badge_kind(impact)),
            (f"{evidence} evidence", evidence_badge_kind(evidence)),
        )
        st.write(issue_short_explanation(insight, theme_label))

        if st.button("View issue →", key=f"{key_prefix}_{theme_name}", width="stretch"):
            st.session_state["selected_theme_detail"] = theme_name
            if on_select:
                on_select(theme_name)


def render_filters(
    theme_options: Sequence[str],
    sentiment_options: Sequence[str],
    severity_options: Sequence[str],
) -> tuple[str, str, str, str]:
    """Render top filter controls."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        selected_theme = st.selectbox("Issue / Theme", options=["All", *theme_options])
    with col2:
        selected_sentiment = st.selectbox("Sentiment", options=["All", *sentiment_options])
    with col3:
        selected_severity = st.selectbox("Impact", options=["All", *severity_options])
    with col4:
        search_term = st.text_input("Search", placeholder="Search feedback text or ID...")

    return selected_theme, selected_sentiment, selected_severity, search_term


def render_review_form(theme_name: str, key_suffix: str = "") -> None:
    """Render review decision form."""
    current_status = get_review_status(st.session_state, theme_name)
    current_note = get_reviewer_note(st.session_state, theme_name)

    form_key = f"review_form_{theme_name}_{key_suffix}" if key_suffix else f"review_form_{theme_name}"
    with st.form(key=form_key):
        st.write(f"**Issue:** {format_theme_label(theme_name)}")
        status_options = list(SUPPORTED_REVIEW_STATUSES)
        status_idx = (
            status_options.index(current_status)
            if current_status in status_options
            else 0
        )
        new_status = st.selectbox(
            "Reviewer decision",
            options=status_options,
            index=status_idx,
            format_func=format_review_status_label,
            key=f"status_sel_{theme_name}_{key_suffix}",
        )
        new_note = st.text_area(
            "Reviewer note",
            value=current_note,
            placeholder="Add context or notes for team members...",
            key=f"note_area_{theme_name}_{key_suffix}",
        )
        submitted = st.form_submit_button("Save Decision", type="primary")

        if submitted:
            set_review_status(st.session_state, theme_name, new_status)
            set_reviewer_note(st.session_state, theme_name, new_note)
            st.success(f"Saved review for '{format_theme_label(theme_name)}'.")
            st.rerun()


def render_export_buttons(
    records_csv: str | None = None,
    theme_csv: str | None = None,
    theme_json: str | None = None,
    markdown_doc: str | None = None,
) -> None:
    """Render product report download controls."""
    col1, col2 = st.columns(2)
    with col1:
        if markdown_doc is not None:
            st.download_button(
                "Executive Summary (Markdown)",
                data=markdown_doc,
                file_name="voc_executive_report_masked.md",
                mime="text/markdown",
                width="stretch",
            )
        if records_csv is not None:
            st.download_button(
                "Customer Evidence Dataset (CSV)",
                data=records_csv,
                file_name="analyzed_records_masked.csv",
                mime="text/csv",
                width="stretch",
            )
    with col2:
        if theme_csv is not None:
            st.download_button(
                "Issue Summary (CSV)",
                data=theme_csv,
                file_name="theme_insights_masked.csv",
                mime="text/csv",
                width="stretch",
            )
        if theme_json is not None:
            st.download_button(
                "Structured Data / API Export (JSON)",
                data=theme_json,
                file_name="theme_insights_masked.json",
                mime="application/json",
                width="stretch",
            )
