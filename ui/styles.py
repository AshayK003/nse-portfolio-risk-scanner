"""
Premium dark theme CSS for the NSE Portfolio Risk Scanner.
Injected via st.markdown with unsafe_allow_html=True.
Designed to complement Streamlit's native dark theme.
"""

import streamlit as st

APP_CSS = """
<style>
/* ── Global ── */
.main .block-container {
    max-width: 1200px;
    padding-top: 2rem;
}

/* ── Metric Cards ── */
div[data-testid="metric-container"] {
    background: #1a1d2e;
    border: 1px solid #2a2d3e;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    transition: border-color 0.2s, box-shadow 0.2s;
}
div[data-testid="metric-container"]:hover {
    border-color: #3b82f6;
    box-shadow: 0 0 0 1px rgba(59,130,246,0.15);
}
div[data-testid="metric-container"] label {
    color: #94a3b8 !important;
    font-size: 0.8rem !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
div[data-testid="metric-container"] div[data-testid="metric-value"] {
    color: #f1f5f9 !important;
    font-weight: 700;
    font-size: 1.5rem !important;
}

/* ── Cards & Containers ── */
.risk-card {
    background: #1a1d2e;
    border: 1px solid #2a2d3e;
    border-radius: 12px;
    padding: 1.25rem;
}

/* ── Warning / Info / Success boxes ── */
.stAlert {
    border-radius: 10px !important;
    border: none !important;
}
div[data-baseweb="notification"] {
    border-radius: 10px !important;
}

/* ── Buttons ── */
.stButton button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: background-color 0.15s, box-shadow 0.15s !important;
}
.stButton button:hover {
    box-shadow: 0 4px 12px rgba(59,130,246,0.25);
}
.stButton button:focus-visible {
    outline: 2px solid #3b82f6 !important;
    outline-offset: 2px;
    box-shadow: none !important;
}

/* ── Focus indicators (global) ─ */
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

/* ── Expander ── */
.streamlit-expanderHeader {
    background: #1a1d2e !important;
    border-radius: 10px !important;
    border: 1px solid #2a2d3e !important;
    font-weight: 500 !important;
}
.streamlit-expanderHeader:hover {
    border-color: #3b82f6 !important;
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
section[data-testid="stSidebar"] .sidebar-content {
    padding-top: 1.5rem;
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

/* ── Selectbox ── */
div[data-baseweb="select"] {
    border-radius: 8px !important;
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

/* ── Badges ── */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 500;
}
.badge-green { background: rgba(34,197,94,0.15); color: #4ade80; }
.badge-red { background: rgba(239,68,68,0.15); color: #f87171; }
.badge-blue { background: rgba(59,130,246,0.15); color: #60a5fa; }
.badge-yellow { background: rgba(234,179,8,0.15); color: #facc15; }

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

/* ── Reduced motion ── */
@media (prefers-reduced-motion: reduce) {
    .stButton button,
    div[data-testid="metric-container"],
    div[data-testid="stFileUploader"],
    .streamlit-expanderHeader {
        transition: none !important;
    }
    .stButton button:hover {
        transform: none !important;
    }
}

/* ── Responsive metric cards ── */
@media (max-width: 768px) {
    div[data-testid="metric-container"] div[data-testid="metric-value"] {
        font-size: 1.2rem !important;
    }
}
</style>
"""


def inject_css():
    """Inject the premium dark theme CSS into the Streamlit app."""
    st.markdown(APP_CSS, unsafe_allow_html=True)
