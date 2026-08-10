"""Minimal Streamlit placeholder for SignalDesk Phase 1."""

import streamlit as st

from src.config import APP_TITLE

st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")

st.title(APP_TITLE)
st.subheader("Phase 1 – Project Foundation")

st.success("Phase 1 foundation is complete.")

st.markdown(
    """
SignalDesk is a CSV-first, evidence-focused product that helps product managers
analyze customer feedback and convert it into source-linked product insights.

**Current status:** This repository contains only the Phase 1 foundation.
AI analysis, CSV ingestion, PII masking, and the full dashboard have **not**
yet been implemented.

**Coming in later phases:**
- CSV upload and column mapping
- Data quality validation and duplicate detection
- PII detection and masking
- Sentiment, theme, and severity analysis
- Evidence-linked insights and transparent prioritization
- Human review workflow
- Exportable reports

**Note:** All sample data in this project is synthetic. It does not represent
real customers or real feedback.
"""
)

st.info(
    "Run tests with: `python -m pytest tests/ -v`  "
    "|  Sample data: `data/sample_feedback.csv`, `data/evaluation_set.csv`"
)
