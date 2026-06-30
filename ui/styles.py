"""
Refined premium dark theme for the NSE Portfolio Risk Scanner.
Injected via st.markdown with unsafe_allow_html=True.
Shadcn-inspired aesthetic via pure CSS on native Streamlit elements.
"""

import streamlit as st

APP_CSS = """
<style>
/* ── Global ── */
.main .block-container {
    max-width: 1280px;
    padding-top: 1.5rem;
}

/* ── Typography scale ── */
h1, h2, h3, h4, h5, h6 {
    letter-spacing: -0.02em;
}
.stMarkdown p {
    line-height: 1.6;
}

/* ── Metric Cards (shadcn-inspired) ── */
div[data-testid="metric-container"] {
    background: linear-gradient(135deg, #181b2e 0%, #1e2238 100%);
    border: 1px solid #2a2d42;
    border-radius: 12px;
    padding: 1.2rem 1.25rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.3), 0 0 0 1px rgba(255,255,255,0.02) inset;
    transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease;
}
div[data-testid="metric-container"]:hover {
    border-color: rgba(59,130,246,0.4);
    box-shadow: 0 4px 20px rgba(59,130,246,0.08), 0 0 0 1px rgba(59,130,246,0.12) inset;
    transform: translateY(-1px);
}
div[data-testid="metric-container"] label {
    color: #7e8ba3 !important;
    font-size: 0.75rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    line-height: 1.4;
}
div[data-testid="metric-container"] div[data-testid="metric-value"] {
    color: #f1f5f9 !important;
    font-weight: 700;
    font-size: 1.6rem !important;
    letter-spacing: -0.02em;
    line-height: 1.3;
}

/* ── Custom Metric Cards ── */
.custom-metric-card {
    background: linear-gradient(135deg, #181b2e 0%, #1e2238 100%);
    border: 1px solid #2a2d42;
    border-radius: 12px;
    padding: 1.2rem 1.25rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.3);
    transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease;
}
.custom-metric-card:hover {
    border-color: rgba(59,130,246,0.4);
    box-shadow: 0 4px 20px rgba(59,130,246,0.08), 0 0 0 1px rgba(59,130,246,0.12) inset;
    transform: translateY(-1px);
}
.custom-metric-card .card-label {
    color: #7e8ba3;
    font-size: 0.75rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    line-height: 1.4;
    margin-bottom: 4px;
}
.custom-metric-card .card-value {
    color: #f1f5f9;
    font-weight: 700;
    font-size: 1.6rem;
    letter-spacing: -0.02em;
    line-height: 1.3;
}
.custom-metric-card .card-caption {
    color: #5a6680;
    font-size: 0.72rem;
    margin-top: 4px;
}
.custom-metric-card .card-delta-positive {
    color: #4ade80;
    font-size: 0.8rem;
    font-weight: 600;
}
.custom-metric-card .card-delta-negative {
    color: #f87171;
    font-size: 0.8rem;
    font-weight: 600;
}

/* ── Warning / Info / Success boxes ── */
.stAlert {
    border-radius: 10px !important;
    border: 1px solid transparent !important;
}
.stAlert[data-baseweb="notification"] {
    border: 1px solid rgba(255,255,255,0.06) !important;
}
div[data-baseweb="notification"] {
    border-radius: 10px !important;
}

/* ── Buttons ── */
.stButton button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    transition: background-color 0.15s, box-shadow 0.15s, transform 0.1s !important;
    letter-spacing: 0.01em;
}
.stButton button:hover {
    box-shadow: 0 4px 16px rgba(59,130,246,0.25);
}
.stButton button:active {
    transform: scale(0.98);
}
.stButton button:focus-visible {
    outline: 2px solid #3b82f6 !important;
    outline-offset: 2px;
    box-shadow: none !important;
}

/* ── Focus indicators (global) ── */
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
    border: 1px solid #282b40;
    font-size: 0.85rem;
}
div[data-testid="stDataFrame"] thead tr th {
    background: #181b2e !important;
    color: #7e8ba3 !important;
    font-size: 0.72rem !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600 !important;
}

/* ── Expander ── */
.streamlit-expanderHeader {
    background: #181b2e !important;
    border-radius: 10px !important;
    border: 1px solid #282b40 !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    transition: border-color 0.15s ease !important;
}
.streamlit-expanderHeader:hover {
    border-color: rgba(59,130,246,0.35) !important;
}

/* ── Tabs (shadcn-inspired line variant) ── */
button[data-baseweb="tab"] {
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    padding: 0.5rem 0.75rem !important;
    transition: color 0.15s ease !important;
    letter-spacing: 0.01em;
}
button[data-baseweb="tab"]:hover {
    color: #94a3b8 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #60a5fa !important;
}
div[data-baseweb="tab-border"] {
    background: #60a5fa !important;
    height: 2px !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #0c0f19 !important;
    border-right: 1px solid #1a1d30 !important;
}
section[data-testid="stSidebar"] .sidebar-content {
    padding-top: 1.5rem;
}
section[data-testid="stSidebar"] .stSelectbox label {
    font-size: 0.75rem !important;
    color: #7e8ba3 !important;
}

/* ── File Uploader ── */
div[data-testid="stFileUploader"] {
    border: 1.5px dashed #2a2d42;
    border-radius: 12px;
    padding: 1.5rem;
    background: #0e111f;
    transition: border-color 0.2s ease, background 0.2s ease;
}
div[data-testid="stFileUploader"]:hover {
    border-color: rgba(59,130,246,0.5);
    background: #111426;
}

/* ── Selectbox ── */
div[data-baseweb="select"] {
    border-radius: 8px !important;
}

/* ── Spinner ── */
.stSpinner > div {
    border-color: #60a5fa !important;
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
    letter-spacing: 0.01em;
}
.badge-green { background: rgba(34,197,94,0.12); color: #4ade80; }
.badge-red { background: rgba(239,68,68,0.12); color: #f87171; }
.badge-blue { background: rgba(59,130,246,0.12); color: #60a5fa; }
.badge-yellow { background: rgba(234,179,8,0.12); color: #facc15; }

/* ── Empty State ── */
.empty-state {
    text-align: center;
    padding: 3rem 2rem;
    color: #94a3b8;
}
.empty-state-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
    opacity: 0.4;
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

/* ── Section Header ── */
.section-header {
    font-size: 1.1rem;
    font-weight: 600;
    color: #e2e8f0;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

/* ── Footer ── */
.app-footer {
    text-align: center;
    color: #5a6680;
    font-size: 0.72rem;
    padding: 1.5rem 0 0.5rem;
    border-top: 1px solid #1a1d30;
    margin-top: 2rem;
}
.app-footer a {
    color: #60a5fa;
    text-decoration: none;
}
.app-footer a:hover {
    text-decoration: underline;
}

/* ── Disclaimer details ── */
details {
    border: 1px solid #282b40;
    border-radius: 10px;
    padding: 0.75rem 1rem;
    background: #0e111f;
}

/* ── Progress bar ── */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #3b82f6, #60a5fa) !important;
}

/* ── Subheader consistency ── */
.stSubheader {
    letter-spacing: -0.01em;
}

/* ── Reduced motion ── */
@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        transition-duration: 0s !important;
        animation-duration: 0s !important;
    }
    .stButton button:hover {
        transform: none !important;
    }
    div[data-testid="metric-container"]:hover,
    .custom-metric-card:hover {
        transform: none !important;
    }
}

/* ── Responsive metric cards ── */
@media (max-width: 768px) {
    div[data-testid="metric-container"] div[data-testid="metric-value"],
    .custom-metric-card .card-value {
        font-size: 1.2rem !important;
    }
    .main .block-container {
        padding-top: 1rem;
    }
}
</style>
"""


def inject_css():
    """Inject the refined dark theme CSS into the Streamlit app."""
    st.markdown(APP_CSS, unsafe_allow_html=True)
