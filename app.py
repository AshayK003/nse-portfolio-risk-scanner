"""
NSE Portfolio Risk Scanner — Streamlit app entry point.

Thin orchestration layer: reads CSV -> computes risk -> renders UI.
Engine has ZERO Streamlit imports. UI has ZERO business logic.
"""
from __future__ import annotations
import pandas as pd
import streamlit as st

from engine import Portfolio, AnalysisReport
from engine.portfolio import parse_portfolio_csv, validate_portfolio, portfolio_from_dict
from engine.risk import compute_risk_metrics, compute_correlation_matrix, rolling_volatility
from engine.sector import load_sector_map, classify_holdings, compute_sector_exposure
from engine.performance import (
    compute_portfolio_returns, compute_total_return, compute_win_rate,
    compute_holding_returns, compute_max_drawdown,
)
from engine.benchmark import compare_to_benchmark, BENCHMARK_TICKERS
from data.prices import fetch_prices, fetch_benchmark, fetch_prices_refreshed

from ui.upload import render_upload_tab, render_data_editor, render_save_button, render_sidebar
from ui.dashboard import (
    render_metric_row, render_risk_cards, render_sector_section,
    render_benchmark_section, render_stock_table,
)
from ui.charts import (
    sector_treemap, drawdown_chart, benchmark_chart,
    correlation_heatmap, volatility_gauge,
)
from ui.export import render_export_section
from ui.icons import BAR_CHART_3, GITHUB, HEART, icon_html
from ui.styles import inject_css

# Page config
st.set_page_config(
    page_title="NSE Portfolio Risk Scanner",
    page_icon=None,  # Lucide SVG used in title instead
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject premium dark theme CSS
inject_css()

# Title with Lucide icon
st.markdown(
    f"<h1 style='display: flex; align-items: center; gap: 0.5rem;'>"
    f"{icon_html(BAR_CHART_3, size=28)} NSE Portfolio Risk Scanner"
    f"</h1>",
    unsafe_allow_html=True,
)
st.caption(
    "Upload a CSV or add stocks manually to analyze risk metrics, "
    "sector concentration, and benchmark comparison."
)

# ── Sidebar ──
render_sidebar()

# ── Session state initialization ──
if "portfolio" not in st.session_state:
    st.session_state.portfolio = None
if "report" not in st.session_state:
    st.session_state.report = None
if "force_refresh" not in st.session_state:
    st.session_state.force_refresh = False
if "selected_benchmark" not in st.session_state:
    st.session_state.selected_benchmark = "^NSEI"

# ── Step 1: Upload or use existing portfolio ──
portfolio = render_upload_tab()
if portfolio is None:
    st.stop()

st.session_state.portfolio = portfolio

# Allow editing
portfolio = render_data_editor(portfolio)
render_save_button(portfolio)

# Validate
warnings = validate_portfolio(portfolio)
for w in warnings:
    st.warning(f"⚠️ {w}")

# ── Step 2: Benchmark selection ──
benchmark_options = {v: k for k, v in BENCHMARK_TICKERS.items()}
default_benchmark = "^NSEI"
benchmark_choice = st.selectbox(
    "Benchmark Index",
    options=list(benchmark_options.keys()),
    format_func=lambda x: benchmark_options[x],
    index=list(benchmark_options.keys()).index(default_benchmark) if default_benchmark in benchmark_options else 0,
    key="benchmark_selector",
)

# Force refresh toggle
refresh_col1, refresh_col2 = st.columns([4, 1])
with refresh_col2:
    force = st.checkbox("🔄 Force refresh prices", value=st.session_state.force_refresh)

# ── Step 3: Fetch prices ──
with st.spinner("Fetching prices..."):
    try:
        if force:
            prices = fetch_prices_refreshed(portfolio.holdings, period="1y")
            st.session_state.force_refresh = False
        else:
            prices = fetch_prices(portfolio.holdings, period="1y")
    except ValueError as e:
        st.error(str(e))
        st.stop()

# Classify sectors
sector_map = load_sector_map()
portfolio.holdings = classify_holdings(portfolio.holdings, sector_map)

# Compute returns
weights = portfolio.weight
portfolio_returns = compute_portfolio_returns(prices, weights)
benchmark_prices = fetch_benchmark(benchmark_choice, period="1y")
benchmark_returns = benchmark_prices.pct_change().dropna() if not benchmark_prices.empty else None

# Compute all risk metrics
risk = compute_risk_metrics(prices, weights, benchmark_returns=benchmark_returns)
sector = compute_sector_exposure(portfolio.holdings)
benchmark = compare_to_benchmark(portfolio_returns, benchmark_returns) if benchmark_returns is not None else None

# Store in session
st.session_state.report = AnalysisReport(
    portfolio=portfolio, risk=risk, sector=sector, benchmark=benchmark,
)

# ── Step 4: Display ──
report = st.session_state.report

# Summary metrics
render_metric_row(report.portfolio, report.risk)

# Tabs
tab_names = ["Risk Metrics", "Sector", "vs Nifty 50", "Charts", "Holdings", "Export"]
tabs = st.tabs(tab_names)

with tabs[0]:
    render_risk_cards(report.risk)
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(volatility_gauge(report.risk.volatility_annual), use_container_width=True)
    with col2:
        rv = rolling_volatility(portfolio_returns)
        if len(rv) > 0:
            st.subheader("Rolling 21-day Volatility")
            st.line_chart(rv)

with tabs[1]:
    render_sector_section(report.sector)
    st.plotly_chart(sector_treemap(report.sector.sector_allocation), use_container_width=True)

with tabs[2]:
    if benchmark:
        render_benchmark_section(report.benchmark)
    else:
        st.warning("Benchmark data not available")
    st.plotly_chart(benchmark_chart(
        (1 + portfolio_returns).cumprod(),
        (1 + benchmark_returns).cumprod() if benchmark_returns is not None else pd.Series(dtype=float),
    ), use_container_width=True)

with tabs[3]:
    col1, col2 = st.columns(2)
    with col1:
        dd = compute_max_drawdown((1 + portfolio_returns).cumprod()) if not portfolio_returns.empty else {"max_drawdown": 0.0, "start": "N/A", "end": "N/A"}
        st.plotly_chart(
            drawdown_chart(
                ((1 + portfolio_returns).cumprod() -
                 (1 + portfolio_returns).cumprod().cummax()) /
                (1 + portfolio_returns).cumprod().cummax()
            ),
            use_container_width=True,
        )
    with col2:
        corr = compute_correlation_matrix(prices)
        st.plotly_chart(correlation_heatmap(corr), use_container_width=True)

with tabs[4]:
    render_stock_table(report.portfolio)

with tabs[5]:
    render_export_section(report.portfolio, risk=report.risk, sector_data=report.sector.sector_allocation)

# ── Step 5: Save analysis run to history ──
try:
    from storage.db import save_analysis_run
    from storage.models import analysis_from_report
    run = analysis_from_report(report)
    save_analysis_run(run)
except Exception:
    pass  # non-critical — silently skip on DB error

# ── Footer ──
st.markdown(
    f'<div class="app-footer">'
    f'{icon_html(GITHUB)} Built by <a href="https://github.com/AshayK003">AshayK003</a> · '
    f'{icon_html(HEART)} '
    f'<a href="https://chai4.me/ashaykushwaha003">Support on Chai4Me</a>'
    f'</div>',
    unsafe_allow_html=True,
)
