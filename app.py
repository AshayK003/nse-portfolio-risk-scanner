"""
NSE Portfolio Risk Scanner — Streamlit app entry point.

Thin orchestration layer: reads CSV -> computes risk -> renders UI.
Engine has ZERO Streamlit imports. UI has ZERO business logic.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data.prices import fetch_benchmark, fetch_prices, fetch_prices_refreshed
from engine import AnalysisReport
from engine.benchmark import BENCHMARK_TICKERS, compare_to_benchmark
from engine.optimization import optimize_hrp
from engine.performance import (
    compute_max_drawdown,
    compute_portfolio_returns,
)
from engine.portfolio import validate_portfolio
from engine.regime import detect_regimes
from engine.risk import (
    compute_correlation_matrix,
    compute_risk_metrics,
    denoise_correlation,
    monte_carlo_paths,
    monte_carlo_simulation,
    rolling_volatility,
)
from engine.sector import classify_holdings, compute_sector_exposure, load_sector_map
from ui.charts import (
    benchmark_chart,
    correlation_heatmap,
    drawdown_chart,
    monte_carlo_chart,
    regime_chart,
    sector_treemap,
    volatility_gauge,
)
from ui.dashboard import (
    render_benchmark_section,
    render_metric_row,
    render_monte_carlo_section,
    render_optimization_section,
    render_regime_section,
    render_risk_cards,
    render_sector_section,
    render_stock_table,
)
from ui.export import render_export_section
from ui.icons import BAR_CHART_3, GITHUB, HEART, icon_html
from ui.styles import inject_css
from ui.upload import render_data_editor, render_save_button, render_sidebar, render_upload_tab

# Page config
st.set_page_config(
    page_title="NSE Portfolio Risk Scanner",
    page_icon=None,
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

# ── Step 2: Benchmark selection ──
benchmark_options = {v: k for k, v in BENCHMARK_TICKERS.items()}
default_benchmark = "^NSEI"
benchmark_choice = st.selectbox(
    "Benchmark Index",
    options=list(benchmark_options.keys()),
    format_func=lambda x: benchmark_options[x],
    index=list(benchmark_options.keys()).index(default_benchmark)
    if default_benchmark in benchmark_options
    else 0,
    key="benchmark_selector",
)

# Force refresh toggle
refresh_col1, refresh_col2 = st.columns([4, 1])
with refresh_col2:
    force = st.checkbox("Force refresh prices", value=st.session_state.force_refresh)

# ── Step 3: Fetch prices ──
with st.spinner("Fetching prices..."):
    try:
        if force:
            prices = fetch_prices_refreshed(portfolio.holdings, period="1y")
            st.session_state.force_refresh = False
        else:
            prices = fetch_prices(portfolio.holdings, period="1y")
    except ValueError as e:
        st.error(f"Could not fetch price data: {e}")
        st.stop()
    except Exception:
        st.error("An unexpected error occurred while fetching prices. Please try again.")
        st.stop()

# Validate portfolio (now that current_price is set)
warnings = validate_portfolio(portfolio)
for w in warnings:
    st.warning(w)

# Classify sectors
sector_map = load_sector_map()
portfolio.holdings = classify_holdings(portfolio.holdings, sector_map)

# Compute returns
weights = portfolio.weight
portfolio_returns = compute_portfolio_returns(prices, weights)
portfolio_cum = (1 + portfolio_returns).cumprod()

with st.spinner("Fetching benchmark data..."):
    try:
        benchmark_prices = fetch_benchmark(benchmark_choice, period="1y")
    except Exception:
        benchmark_prices = pd.Series(dtype=float)

benchmark_returns = benchmark_prices.pct_change().dropna() if not benchmark_prices.empty else None
benchmark_cum = (1 + benchmark_returns).cumprod() if benchmark_returns is not None else pd.Series(dtype=float)

# Compute all risk metrics
with st.spinner("Computing risk metrics..."):
    risk = compute_risk_metrics(prices, weights, benchmark_returns=benchmark_returns)
    sector = compute_sector_exposure(portfolio.holdings)
    benchmark = (
        compare_to_benchmark(portfolio_returns, benchmark_returns) if benchmark_returns is not None else None
    )

# ── New v0.6.0 features ──

# Correlation matrix (needed for denoising)
raw_corr = compute_correlation_matrix(prices) if not prices.empty else pd.DataFrame()

# HRP Optimization
opt_result = optimize_hrp(prices.pct_change().dropna()) if len(weights) >= 2 else None

# Monte Carlo simulation
mc_result = monte_carlo_simulation(portfolio_returns) if not portfolio_returns.empty else None
mc_paths = monte_carlo_paths(portfolio_returns) if not portfolio_returns.empty else None

# HMM Regime detection
regime_result = detect_regimes(portfolio_returns) if not portfolio_returns.empty else None

# Correlation denoising
denoised_corr = denoise_correlation(raw_corr, len(portfolio_returns)) if not portfolio_returns.empty else None


# Store in session
st.session_state.report = AnalysisReport(
    portfolio=portfolio,
    risk=risk,
    sector=sector,
    benchmark=benchmark,
    optimization=opt_result,
    monte_carlo=mc_result,
    regime=regime_result,
)

# ── Step 4: Display ──
report = st.session_state.report

# Summary metrics
render_metric_row(report.portfolio, report.risk)

# Tabs
tab_names = ["Risk Metrics", "Sector", "vs Nifty 50", "Charts", "Holdings", "Export", "Optimization", "Regime"]
tabs = st.tabs(tab_names)

with tabs[0]:
    render_risk_cards(report.risk)
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(volatility_gauge(report.risk.volatility_annual), use_container_width=True, key="vol_gauge")
    with col2:
        rv = rolling_volatility(portfolio_returns)
        if len(rv) > 0:
            st.subheader("Rolling 21-day Volatility")
            st.line_chart(rv)
    st.divider()
    render_monte_carlo_section(mc_result)
    if mc_paths is not None:
        st.plotly_chart(monte_carlo_chart(mc_paths, (5, 95)), use_container_width=True, key="mc_chart")

with tabs[1]:
    render_sector_section(report.sector)
    st.plotly_chart(sector_treemap(report.sector.sector_allocation), use_container_width=True, key="sector_treemap")

with tabs[2]:
    if benchmark:
        render_benchmark_section(report.benchmark)
    else:
        st.info("Benchmark data is not available for the selected index.")
    st.plotly_chart(
        benchmark_chart(portfolio_cum, benchmark_cum),
        use_container_width=True,
        key="benchmark_chart",
    )

with tabs[3]:
    col1, col2 = st.columns(2)
    with col1:
        dd = (
            compute_max_drawdown(portfolio_cum)
            if not portfolio_returns.empty
            else {"max_drawdown": 0.0, "start": "N/A", "end": "N/A"}
        )
        running_max = portfolio_cum.cummax()
        drawdown_series = (portfolio_cum - running_max) / running_max
        st.plotly_chart(
            drawdown_chart(drawdown_series),
            use_container_width=True,
            key="drawdown_chart",
        )
    with col2:
        corr = raw_corr if not raw_corr.empty else compute_correlation_matrix(prices)
        st.plotly_chart(
            correlation_heatmap(corr),
            use_container_width=True,
            key="corr_heatmap",
        )
    if denoised_corr is not None and not denoised_corr.empty:
        with st.expander("Denoised Correlation (Marchenko-Pastur)"):
            st.plotly_chart(correlation_heatmap(denoised_corr), use_container_width=True, key="corr_denoised")

with tabs[4]:
    render_stock_table(report.portfolio)

with tabs[5]:
    render_export_section(report.portfolio, risk=report.risk, sector_data=report.sector.sector_allocation)

with tabs[6]:
    render_optimization_section(opt_result, portfolio=report.portfolio)

with tabs[7]:
    render_regime_section(regime_result)
    if regime_result:
        st.plotly_chart(regime_chart(portfolio_returns, regime_result.state_sequence), use_container_width=True, key="regime_chart")

# ── Step 5: Save analysis run to history ──
try:
    from storage.db import save_analysis_run
    from storage.models import analysis_from_report

    run = analysis_from_report(report)
    save_analysis_run(run)
except Exception:
    pass  # non-critical — silently skip on DB error

# ── Disclaimer ──
st.info(
    "**Disclaimer:** This tool provides informational analysis only and does not "
    "constitute financial advice. All data is sourced from public APIs (yfinance, NSE) "
    "and may be delayed or inaccurate. Past performance is not indicative of future "
    "results. Consult a SEBI-registered advisor before making investment decisions."
)

# ── Footer ──
st.markdown(
    f'<div class="app-footer">'
    f'{icon_html(GITHUB)} Built by <a href="https://github.com/AshayK003">AshayK003</a> · '
    f"{icon_html(HEART)} "
    f'<a href="https://chai4.me/ashaykushwaha003">Support on Chai4Me</a>'
    f"</div>",
    unsafe_allow_html=True,
)
