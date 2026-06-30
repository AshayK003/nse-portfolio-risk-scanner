"""
Custom CSS for elements facade doesn't cover.
"""

import streamlit as st

APP_CSS = """
<style>
.main .block-container {
    max-width: 1200px;
    padding-top: 2rem;
}

/* ── Tabs ── */
button[data-baseweb="tab"] {
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #3b82f6 !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #0e1017 !important;
    border-right: 1px solid #1e2030 !important;
}

/* ── File Uploader ── */
div[data-testid="stFileUploader"] {
    border: 1px dashed #2a2d3e;
    border-radius: 12px;
    padding: 1.5rem;
    background: #0e1017;
    transition: border-color 0.2s;
}
div[data-testid="stFileUploader"]:hover {
    border-color: #3b82f6;
}

/* ── Data Editor & Table ── */
div[data-testid="stDataFrame"] {
    border-radius: 10px !important;
    overflow: hidden;
    border: 1px solid #2a2d3e;
}
div[data-testid="stDataFrame"] thead tr th {
    background: #1a1d2e !important;
    color: #94a3b8 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ── Icon inline styling ── */
.icon-wrap {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    vertical-align: middle;
    margin-right: 4px;
}
.icon-wrap svg {
    display: block;
}

/* ── Empty State ── */
.empty-state {
    text-align: center;
    padding: 3rem 2rem;
    color: #94a3b8;
}
.empty-state-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
    opacity: 0.5;
}
.empty-state-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: #e2e8f0;
    margin-bottom: 0.5rem;
}
.empty-state-desc {
    font-size: 0.9rem;
    line-height: 1.6;
    max-width: 480px;
    margin: 0 auto;
}

/* ── Footer ── */
.app-footer {
    text-align: center;
    color: #64748b;
    font-size: 0.75rem;
    padding: 1.5rem 0 0.5rem;
    border-top: 1px solid #1e2030;
    margin-top: 2rem;
}
.app-footer a {
    color: #60a5fa;
    text-decoration: none;
}
.app-footer a:hover {
    text-decoration: underline;
}

/* ── Focus indicators ── */
:focus-visible {
    outline: 2px solid #3b82f6;
    outline-offset: 2px;
}
input:focus-visible,
select:focus-visible,
textarea:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.4);
}

/* ── Reduced motion ── */
@media (prefers-reduced-motion: reduce) {
    div[data-testid="stFileUploader"] {
        transition: none !important;
    }
}
</style>
"""


def inject_css():
    """Inject custom CSS into the Streamlit app."""
    st.markdown(APP_CSS, unsafe_allow_html=True)
