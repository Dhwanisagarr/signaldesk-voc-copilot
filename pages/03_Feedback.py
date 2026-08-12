"""Feedback Page for SignalDesk – Individual Customer Evidence Explorer."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui_components import render_sidebar_footer
from src.ui_helpers import (
    SESSION_ANALYSIS,
    SESSION_ANALYSIS_COMPLETE,
    SESSION_MASKED_DF,
    build_feedback_explorer_dataframe,
    filter_feedback_explorer,
    format_theme_label,
)


def main() -> None:
    st.title("Customer Feedback")
    st.caption("Browse individual masked customer feedback records linked to product issues.")

    st.divider()

    if not st.session_state.get(SESSION_ANALYSIS_COMPLETE):
        st.info("Run analysis on the **Analyze** page first to browse feedback records.")
        if st.button("Go to Analyze →", type="primary"):
            st.switch_page("pages/01_Analyze.py")
        render_sidebar_footer()
        return

    analysis = st.session_state.get(SESSION_ANALYSIS)
    masked_df = st.session_state.get(SESSION_MASKED_DF)

    if analysis is None or masked_df is None:
        st.warning("No customer feedback records available.")
        render_sidebar_footer()
        return

    explorer_df = build_feedback_explorer_dataframe(analysis, masked_df)

    # 1. Top Filters
    st.markdown("### Filters")
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)

    preset_theme = st.session_state.get("filter_theme_feedback")

    with f_col1:
        themes = sorted(explorer_df["primary_theme"].dropna().unique().tolist())
        theme_labels = {t: format_theme_label(t) for t in themes}
        selected_theme = st.selectbox(
            "Issue / Theme",
            options=["All", *themes],
            index=(themes.index(preset_theme) + 1) if preset_theme in themes else 0,
            format_func=lambda x: "All" if x == "All" else theme_labels.get(x, x),
        )

    with f_col2:
        sentiments = sorted(explorer_df["sentiment"].dropna().unique().tolist())
        selected_sentiment = st.selectbox("Sentiment", options=["All", *sentiments])

    with f_col3:
        severities = sorted(explorer_df["severity"].dropna().unique().tolist())
        selected_severity = st.selectbox("Impact / Severity", options=["All", *severities])

    with f_col4:
        sources = (
            sorted(explorer_df["source"].dropna().unique().tolist())
            if "source" in explorer_df
            else []
        )
        selected_source = st.selectbox("Source", options=["All", *sources])

    search_query = st.text_input("Search (Feedback ID or text)", placeholder="Search customer quotes...")

    filtered_df = filter_feedback_explorer(
        explorer_df,
        primary_themes=[selected_theme] if selected_theme != "All" else None,
        sentiments=[selected_sentiment] if selected_sentiment != "All" else None,
        severities=[selected_severity] if selected_severity != "All" else None,
        sources=[selected_source] if selected_source != "All" else None,
        search_query=search_query,
    )

    st.caption(f"Showing **{len(filtered_df)}** of **{len(explorer_df)}** customer feedback records")

    st.divider()

    # 2. Customer Evidence Focus Cards
    if filtered_df.empty:
        st.info("No customer feedback matches the selected filters.")
        render_sidebar_footer()
        return

    for idx, row in filtered_df.iterrows():
        feedback_id = row["feedback_id"]
        masked_text = row["masked_text"]
        theme_tag = format_theme_label(row["primary_theme"])
        sentiment_tag = str(row["sentiment"]).title()
        severity_tag = str(row["severity"]).title()
        source_val = row.get("source") or "—"
        date_val = row.get("date") or "—"
        rating_val = row.get("rating") if pd.notna(row.get("rating")) else "—"

        with st.container(border=True):
            tc1, tc2 = st.columns([4, 1])
            with tc1:
                st.markdown(f"**`{feedback_id}`** · `{theme_tag}`")
                st.markdown(f'"{masked_text}"')
                st.caption(
                    f"Source: **{source_val}** · Date: **{date_val}** · Rating: **{rating_val}**"
                )
            with tc2:
                st.caption(f"Sentiment: **{sentiment_tag}**")
                st.caption(f"Impact: **{severity_tag}**")

            # Technical details hidden under per-card expander
            with st.expander("Analysis details"):
                st.markdown(f"- **Primary Theme:** {theme_tag}")
                if row.get("secondary_themes"):
                    st.markdown(f"- **Secondary Themes:** {row['secondary_themes']}")
                st.markdown(f"- **Intent:** {str(row.get('intent', '')).title()}")
                st.markdown(f"- **Product Area:** {row.get('product_area', '—')}")
                st.markdown(f"- **Analysis Method:** `{row.get('analysis_method', '—')}`")
                st.markdown(f"- **Confidence:** `{row.get('confidence', 0):.2f}`")
                st.markdown(f"- **PII Detected:** {'Yes' if row.get('pii_detected') else 'No'}")

    render_sidebar_footer()


if __name__ == "__main__":
    main()
