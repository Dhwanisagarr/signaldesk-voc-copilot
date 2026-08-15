"""Visual design system for SignalDesk — Black + Yellow + White identity.

Presentation-only module. It injects CSS that restyles native Streamlit
widgets (buttons, containers, metrics, inputs, expanders, sidebar nav, ...)
and renders small HTML building blocks (badges, hero copy, stat rows,
quote cards) from values already computed elsewhere.

This module contains NO analysis, scoring, PII, persistence, or export
logic. It only formats strings/labels that `src/ui_helpers.py` and the
backend already produced.
"""

from __future__ import annotations

import html as _html

import streamlit as st

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

BG = "#0A0A0B"
BG_ELEVATED = "#141416"
BG_ELEVATED_2 = "#1C1C1F"
BORDER = "#2A2A2D"
BORDER_SUBTLE = "#1F1F22"

YELLOW = "#F4C21A"
YELLOW_DIM = "#C9A315"
YELLOW_SOFT_BG = "rgba(244, 194, 26, 0.12)"
YELLOW_ON_YELLOW_TEXT = "#000000"

WHITE = "#FFFFFF"
WHITE_SOFT_BG = "rgba(255, 255, 255, 0.08)"
TEXT_SECONDARY = "#B4B4B9"
TEXT_TERTIARY = "#7C7C82"

GREEN = "#34D399"
GREEN_SOFT_BG = "rgba(52, 211, 153, 0.12)"
RED = "#F0576B"
RED_SOFT_BG = "rgba(240, 87, 107, 0.12)"


_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}

[data-testid="stAppViewContainer"], .main {{ background-color: {BG} !important; }}
[data-testid="stHeader"] {{ background-color: transparent !important; }}
.block-container {{ padding-top: 2.2rem !important; max-width: 1180px; }}

section[data-testid="stSidebar"] {{
    background-color: {BG} !important;
    border-right: 1px solid {BORDER_SUBTLE};
}}
section[data-testid="stSidebar"] * {{ color: {TEXT_SECONDARY}; }}
section[data-testid="stSidebar"] a {{
    color: {TEXT_SECONDARY} !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
}}
section[data-testid="stSidebar"] a:hover {{
    background-color: {BG_ELEVATED} !important;
    color: {WHITE} !important;
}}
section[data-testid="stSidebar"] a[aria-current="page"] {{
    background-color: {YELLOW_SOFT_BG} !important;
    color: {YELLOW} !important;
    font-weight: 700 !important;
}}

h1, h2, h3, h4, h5, h6 {{ color: {WHITE} !important; font-weight: 700 !important; letter-spacing: -0.01em; }}
p, li, label {{ color: {TEXT_SECONDARY}; }}
[data-testid="stCaptionContainer"], .stCaption, [data-testid="stMarkdownContainer"] small {{
    color: {TEXT_TERTIARY} !important;
}}

hr {{ border-color: {BORDER_SUBTLE} !important; margin: 1.25rem 0 !important; }}

.stButton > button {{
    border-radius: 8px !important;
    font-weight: 600 !important;
    border: 1px solid {BORDER} !important;
    background-color: {BG_ELEVATED} !important;
    color: {WHITE} !important;
    transition: all 0.15s ease;
}}
.stButton > button *, .stDownloadButton > button * {{
    color: inherit !important;
    -webkit-text-fill-color: inherit !important;
}}
.stButton > button:hover {{
    border-color: {TEXT_SECONDARY} !important;
    background-color: {BG_ELEVATED_2} !important;
}}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {{
    background-color: {YELLOW} !important;
    color: {YELLOW_ON_YELLOW_TEXT} !important;
    border: 1px solid {YELLOW} !important;
}}
.stButton > button[kind="primary"] *, .stDownloadButton > button[kind="primary"] * {{
    color: {YELLOW_ON_YELLOW_TEXT} !important;
    -webkit-text-fill-color: {YELLOW_ON_YELLOW_TEXT} !important;
}}
.stButton > button[kind="primary"]:hover {{
    background-color: {YELLOW_DIM} !important;
    border-color: {YELLOW_DIM} !important;
}}
.stDownloadButton > button {{
    border-radius: 8px !important;
    font-weight: 600 !important;
    border: 1px solid {BORDER} !important;
    background-color: {BG_ELEVATED_2} !important;
    color: {WHITE} !important;
}}

[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: {BG_ELEVATED} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 14px !important;
}}

[data-testid="stMetric"] {{
    background-color: {BG_ELEVATED} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
    padding: 0.9rem 1rem !important;
}}
[data-testid="stMetricLabel"] p {{
    color: {TEXT_TERTIARY} !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
}}
[data-testid="stMetricValue"] {{ color: {WHITE} !important; font-weight: 800 !important; }}

[data-testid="stExpander"] {{
    background-color: {BG_ELEVATED} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
}}
[data-testid="stExpander"] summary {{ color: {TEXT_SECONDARY} !important; font-weight: 600 !important; }}
[data-testid="stExpander"] summary:hover {{ color: {WHITE} !important; }}

[data-testid="stFileUploaderDropzone"] {{
    background-color: {BG_ELEVATED} !important;
    border: 1.5px dashed {BORDER} !important;
    border-radius: 12px !important;
}}
[data-testid="stFileUploaderDropzone"]:hover {{ border-color: {YELLOW} !important; }}
[data-testid="stFileUploaderDropzone"] button {{
    background-color: {BG_ELEVATED_2} !important;
    color: {WHITE} !important;
    border: 1px solid {BORDER} !important;
}}

.stTextInput input, .stTextArea textarea,
[data-testid="stSelectbox"] > div, [data-testid="stTextInputRootElement"] {{
    background-color: {BG_ELEVATED} !important;
    color: {WHITE} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color: {YELLOW} !important;
    box-shadow: 0 0 0 1px {YELLOW} !important;
}}

[data-testid="stProgress"] > div > div {{ background-color: {YELLOW} !important; }}

[data-testid="stDataFrame"] {{ border: 1px solid {BORDER} !important; border-radius: 10px !important; }}

[data-testid="stStatusWidget"] {{
    background-color: {BG_ELEVATED} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
}}

/* --- Custom SignalDesk building blocks --- */
.sd-eyebrow {{
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.72rem;
    font-weight: 700;
    color: {TEXT_TERTIARY};
    margin-bottom: 0.35rem;
}}
.sd-hero-title {{
    font-size: 2.15rem;
    font-weight: 800;
    color: {WHITE};
    letter-spacing: -0.02em;
    line-height: 1.15;
    margin-bottom: 0.5rem;
}}
.sd-hero-sub {{
    font-size: 1.03rem;
    color: {TEXT_SECONDARY};
    max-width: 660px;
    line-height: 1.55;
}}
.sd-section-title {{
    font-size: 1.05rem;
    font-weight: 700;
    color: {WHITE};
    margin: 0 0 0.6rem 0;
}}
.sd-badge {{
    display: inline-block;
    padding: 0.2rem 0.62rem;
    border-radius: 999px;
    font-size: 0.70rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    margin-right: 0.35rem;
    margin-bottom: 0.2rem;
    white-space: nowrap;
}}
.sd-quote {{
    font-size: 1.03rem;
    color: {WHITE};
    line-height: 1.55;
    font-style: italic;
    border-left: 3px solid {YELLOW};
    padding: 0.1rem 0 0.1rem 0.95rem;
    margin: 0.35rem 0;
}}
.sd-quote-meta {{
    font-size: 0.78rem;
    color: {TEXT_TERTIARY};
    margin-top: 0.3rem;
    padding-left: 0.95rem;
}}
.sd-dot {{
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%;
    margin-right: 0.4rem;
}}
</style>
"""


def inject_theme() -> None:
    """Inject the SignalDesk CSS. Safe to call at the top of every page."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Text blocks
# ---------------------------------------------------------------------------


def eyebrow(text: str) -> None:
    st.markdown(f'<div class="sd-eyebrow">{_html.escape(text)}</div>', unsafe_allow_html=True)


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="sd-hero-title">{_html.escape(title)}</div>'
        f'<div class="sd-hero-sub">{_html.escape(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def section_title(text: str) -> None:
    st.markdown(f'<div class="sd-section-title">{_html.escape(text)}</div>', unsafe_allow_html=True)


def quote_block(quote: str, meta: str | None = None) -> None:
    """Render a customer quote as visually prominent evidence."""
    html = f'<div class="sd-quote">\u201c{_html.escape(quote)}\u201d</div>'
    if meta:
        html += f'<div class="sd-quote-meta">{_html.escape(meta)}</div>'
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Badges — small pure mappings from already-computed labels to a visual kind.
# No thresholds or scoring here; the label (e.g. "High", "Strong", "P0
# Critical") is produced by src/ui_helpers.py from the real backend data.
# ---------------------------------------------------------------------------

_BADGE_STYLES: dict[str, tuple[str, str, str]] = {
    # kind: (background, text color, border color)
    "impact-high": (YELLOW_SOFT_BG, YELLOW, YELLOW_DIM),
    "impact-medium": (BG_ELEVATED_2, TEXT_SECONDARY, BORDER),
    "impact-low": (BG_ELEVATED_2, TEXT_TERTIARY, BORDER_SUBTLE),
    "evidence-strong": (WHITE_SOFT_BG, WHITE, "rgba(255,255,255,0.35)"),
    "evidence-moderate": (BG_ELEVATED_2, TEXT_SECONDARY, BORDER),
    "evidence-weak": (BG_ELEVATED_2, TEXT_TERTIARY, BORDER_SUBTLE),
    "urgency-p0": (YELLOW, YELLOW_ON_YELLOW_TEXT, YELLOW),
    "urgency-p1": (YELLOW_SOFT_BG, YELLOW, YELLOW_DIM),
    "urgency-p2": (BG_ELEVATED_2, TEXT_SECONDARY, BORDER),
    "urgency-p3": (BG_ELEVATED_2, TEXT_TERTIARY, BORDER_SUBTLE),
    "status-approved": (GREEN_SOFT_BG, GREEN, GREEN),
    "status-rejected": (RED_SOFT_BG, RED, RED),
    "status-needs_more_evidence": (YELLOW_SOFT_BG, YELLOW, YELLOW_DIM),
    "status-pending": (BG_ELEVATED_2, TEXT_TERTIARY, BORDER),
    "neutral": (BG_ELEVATED_2, TEXT_SECONDARY, BORDER),
}


def _badge_html(text: str, kind: str) -> str:
    bg, fg, border = _BADGE_STYLES.get(kind, _BADGE_STYLES["neutral"])
    safe_text = _html.escape(str(text))
    return (
        f'<span class="sd-badge" style="background-color:{bg};color:{fg};'
        f'border:1px solid {border};">{safe_text}</span>'
    )


def render_badges(*specs: tuple[str, str]) -> None:
    """Render one or more (text, kind) badges inline in a single block."""
    st.markdown("".join(_badge_html(text, kind) for text, kind in specs), unsafe_allow_html=True)


def impact_badge_kind(level: str) -> str:
    return {"High": "impact-high", "Medium": "impact-medium", "Low": "impact-low"}.get(level, "neutral")


def evidence_badge_kind(label: str) -> str:
    return {
        "Strong": "evidence-strong",
        "Moderate": "evidence-moderate",
        "Weak": "evidence-weak",
    }.get(label, "neutral")


def urgency_badge_kind(label: str) -> str:
    if label.startswith("P0"):
        return "urgency-p0"
    if label.startswith("P1"):
        return "urgency-p1"
    if label.startswith("P2"):
        return "urgency-p2"
    return "urgency-p3"


def status_badge_kind(status_code: str) -> str:
    return f"status-{status_code}" if f"status-{status_code}" in _BADGE_STYLES else "status-pending"


def status_dot_color(status_code: str) -> str:
    return {
        "approved": GREEN,
        "rejected": RED,
        "needs_more_evidence": YELLOW,
        "pending": TEXT_TERTIARY,
    }.get(status_code, TEXT_TERTIARY)


def status_dot_html(status_code: str, label: str) -> str:
    color = status_dot_color(status_code)
    return f'<span class="sd-dot" style="background-color:{color};"></span>{_html.escape(label)}'
