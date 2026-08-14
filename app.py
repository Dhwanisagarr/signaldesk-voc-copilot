"""SignalDesk – Voice-of-Customer Copilot (Main Entrypoint)."""

from __future__ import annotations

import streamlit as st

from src.ui_helpers import (
    init_session_state,
    sync_review_store_to_session,
)


def main() -> None:
    st.set_page_config(
        page_title="SignalDesk – Voice-of-Customer Copilot",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state(st.session_state)
    sync_review_store_to_session(st.session_state)

    # EXACTLY ONE Consolidated 3-Step Navigation System via st.navigation
    pages = [
        st.Page("pages/01_Import.py", title="1. Import Data", default=True),
        st.Page("pages/02_Workspace.py", title="2. Insight Workspace"),
        st.Page("pages/03_Export.py", title="3. Export & Share"),
    ]

    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    main()
