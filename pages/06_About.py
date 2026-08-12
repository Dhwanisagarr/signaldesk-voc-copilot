"""About Page for SignalDesk."""

from __future__ import annotations

import streamlit as st

from src.ui_components import render_sidebar_footer


def main() -> None:
    st.title("About SignalDesk")
    st.markdown(
        "SignalDesk is a Voice-of-Customer product that turns messy customer feedback into prioritized product problems, backed by customer evidence."
    )

    st.divider()

    # Product Overview
    st.markdown("### What SignalDesk Does")
    st.markdown(
        """
SignalDesk helps Product Managers, founders, and customer operations leaders answer three core questions:
1. **What are customers struggling with?** (Theme classification & evidence extraction)
2. **Which problems deserve my attention?** (Impact ranking based on frequency, severity, and confidence)
3. **What should I investigate next?** (Suggested investigation areas and customer evidence quotes)
"""
    )

    st.markdown("### Who It Is For")
    st.markdown(
        """
- **Product Managers & Founders** prioritizing quarterly roadmaps based on customer feedback.
- **Product Operations & Customer Support Leaders** identifying recurring friction points across channels.
"""
    )

    st.divider()

    # High-level Methodology
    st.markdown("### Methodology")
    st.markdown(
        """
- **Rule-based sentiment:** Classifies positive, neutral, and negative sentiment independently from issue severity.
- **Theme classification:** Identifies recurring domain-specific product themes.
- **Evidence-linked quotes:** Validates exact excerpts from `masked_text` to verify problem claims.
- **Transparent impact ranking:** Evaluates customer volume, complaint severity, and classification confidence.
"""
    )

    with st.expander("Technical Pipeline Details"):
        st.markdown(
            """
- **TF-IDF Batch Fallback:** Fitted once per dataset batch when keyword confidence falls below threshold.
- **Exploratory K-Means:** Groups feedback by textual similarity for exploration without altering theme or priority labels.
- **Prioritization Formula:** `Priority Score = Frequency Score × Severity Score × Confidence Score`.
- **Local Execution:** 100% offline, deterministic execution using Python standard library, Pandas, and Scikit-Learn.
"""
        )

    st.divider()

    # Privacy Policy
    with st.expander("Privacy & Security"):
        st.markdown(
            """
- **Masked Text Only:** Dashboard displays, analysis pipelines, and reports operate strictly on `masked_text`.
- **No External API Calls:** Zero external API or LLM calls. Data remains local on your machine.
- **Local SQLite Store:** Stores review decision metadata only (`theme_name`, `status`, `reviewer_note`, timestamps). Customer text is never saved to the database.
"""
        )

    # Limitations
    with st.expander("Limitations"):
        st.markdown(
            """
- **Synthetic Data Baseline:** Tested on synthetic Indian fintech customer feedback datasets.
- **Regex Masking:** Deterministic regex detection provides an initial privacy layer; manual audit is recommended for edge cases.
- **Single-User Prototype:** Review decisions and notes are saved to a local SQLite database (`outputs/reviews.db`).
"""
        )

    st.divider()

    # Contact
    st.markdown("### Contact & Feedback")
    st.markdown("Have feedback or questions? Contact the team at [support@signaldesk.local].")

    render_sidebar_footer()


if __name__ == "__main__":
    main()
