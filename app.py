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
from engine.optimization import optimize_hrp, suggest_rebalance
from engine.performance import (
    compute_max_drawdown,
    compute_portfolio_returns,
)
from engine.scenario import run_default_scenarios
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
    render_rebalance_section,
    render_regime_section,
    render_risk_cards,
    render_scenario_section,
    render_sector_section,
    render_stock_table,
)
from ui.export import render_export_section
from ui.icons import ALERT_TRIANGLE, BAR_CHART_3, GITHUB, HEART, icon_html
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
    force = st.checkbox("Force refresh prices", value=st.session_state.get("force_refresh", False), key="force_refresh")

# ── Input hash — skip recomputation when portfolio hasn't changed ──
_input_hash = hash((
    tuple((h.ticker, h.quantity, h.avg_price) for h in portfolio.holdings),
    benchmark_choice,
))

_needs_compute = force or st.session_state.get("_last_input_hash") != _input_hash

if _needs_compute:
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
    mc_paths = monte_carlo_paths(portfolio_returns, n_simulations=200) if not portfolio_returns.empty else None

    # HMM Regime detection
    regime_result = detect_regimes(portfolio_returns) if not portfolio_returns.empty else None

    # Correlation denoising
    denoised_corr = denoise_correlation(raw_corr, len(portfolio_returns)) if not portfolio_returns.empty else None

    # Per-holding betas (vectorized via single covariance matrix)
    stock_betas: dict[str, float] = {}
    if benchmark_returns is not None and not prices.empty:
        rets = prices.pct_change().dropna()
        extended = pd.concat([rets, benchmark_returns], axis=1, join="inner").dropna()
        if len(extended) > 5:
            cov_matrix = extended.cov()
            bm_var = cov_matrix.iloc[-1, -1]
            if bm_var > 0:
                stock_betas = (cov_matrix.iloc[:-1, -1] / bm_var).round(2).to_dict()
        if not stock_betas:
            stock_betas = {c: 1.0 for c in rets.columns}

    scenarios = run_default_scenarios(portfolio.holdings, stock_betas) if stock_betas else []
    rebalance = suggest_rebalance(portfolio.holdings) if portfolio.holding_count >= 1 else None

    # Cache everything for skip path
    st.session_state._cache = {
        "prices": prices,
        "portfolio_returns": portfolio_returns,
        "portfolio_cum": portfolio_cum,
        "benchmark_returns": benchmark_returns,
        "benchmark_cum": benchmark_cum,
        "raw_corr": raw_corr,
        "denoised_corr": denoised_corr,
        "mc_paths": mc_paths,
        "stock_betas": stock_betas,
        "scenarios": scenarios,
        "rebalance": rebalance,
        "risk": risk,
        "sector": sector,
        "benchmark": benchmark,
        "opt_result": opt_result,
        "mc_result": mc_result,
        "regime_result": regime_result,
    }
    st.session_state._last_input_hash = _input_hash
    st.session_state._report_changed = True
else:
    cache = st.session_state._cache
    prices = cache["prices"]
    portfolio_returns = cache["portfolio_returns"]
    portfolio_cum = cache["portfolio_cum"]
    benchmark_returns = cache["benchmark_returns"]
    benchmark_cum = cache["benchmark_cum"]
    raw_corr = cache["raw_corr"]
    denoised_corr = cache["denoised_corr"]
    mc_paths = cache["mc_paths"]
    stock_betas = cache["stock_betas"]
    scenarios = cache["scenarios"]
    rebalance = cache["rebalance"]
    risk = cache["risk"]
    sector = cache["sector"]
    benchmark = cache["benchmark"]
    opt_result = cache["opt_result"]
    mc_result = cache["mc_result"]
    regime_result = cache["regime_result"]
    st.session_state._report_changed = False

# Always needed for rendering
weights = portfolio.weight

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
tab_names = ["Risk Metrics", "Sector", "vs Nifty 50", "Charts", "Holdings", "Export", "Optimization", "Regime", "Scenario"]
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
    render_rebalance_section(rebalance)

with tabs[7]:
    render_regime_section(regime_result)
    if regime_result:
        st.plotly_chart(regime_chart(portfolio_returns, regime_result.state_sequence), use_container_width=True, key="regime_chart")

with tabs[8]:
    render_scenario_section(scenarios)

# ── Step 5: Save analysis run to history (only on fresh computation) ──
if st.session_state.get("_report_changed", False):
    try:
        from storage.db import save_analysis_run
        from storage.models import analysis_from_report

        run = analysis_from_report(report)
        save_analysis_run(run)
    except Exception:
        pass  # non-critical — silently skip on DB error

# ── Disclaimer ──
with st.expander(f"{icon_html(ALERT_TRIANGLE, size=16)} Disclaimer", expanded=False):
    st.markdown(
        "**Not financial advice.** This tool provides portfolio risk analysis, "
        "sector concentration metrics, benchmark comparison, and other quantitative "
        "indicators for educational and informational purposes only. Nothing on this "
        "platform constitutes investment advice, a recommendation, or a solicitation "
        "to buy or sell securities.\n\n"
        "**No SEBI registration.** The creator is not a SEBI-registered investment "
        "advisor. All trading and investment decisions are solely your responsibility.\n\n"
        "**Data accuracy.** Data is sourced from third-party public APIs (yfinance, "
        "nselib) and may be delayed, incomplete, or inaccurate. We do not guarantee "
        "the timeliness, accuracy, or completeness of any data displayed.\n\n"
        "**Limitations you should know:**\n"
        "- **Price data** — yfinance free tier has 15-20 min delay. Not suitable for "
        "intraday trading without real-time feeds.\n"
        "- **NSE data** — nselib is an optional dependency. Without it, all data comes "
        "from yfinance, which may have gaps for Indian equities (missing delisted "
        "tickers, delayed corporate actions).\n"
        "- **Risk metrics** — VaR, CVaR, and Monte Carlo projections are based on "
        "historical return distributions and assume normality. Tail risk is "
        "underestimated during market dislocations (2020 COVID crash, 2008 GFC).\n"
        "- **Beta** — computed against a single benchmark index using daily returns. "
        "A beta of 1.2 does not guarantee the stock moves 20% more than the market "
        "in all conditions.\n"
        "- **Monte Carlo simulation** — uses Geometric Brownian Motion, which assumes "
        "returns are normally distributed and volatility is constant. Both assumptions "
        "are violated in real markets.\n"
        "- **HMM regime detection** — optional dependency (hmmlearn). When unavailable, "
        "a rolling-quantile heuristic is used instead. Neither is a predictor of "
        "future market regimes.\n"
        "- **Scenario analysis** — estimated using stock beta × weight × market change. "
        "Beta is itself an estimate from historical data and may not hold during "
        "regime shifts.\n"
        "- **Delivery analysis** — relies on nselib bhavcopy data, which is typically "
        "available with a 1-day lag.\n\n"
        "**No liability.** Under no circumstances shall the creator be liable for any "
        "direct, indirect, incidental, special, or consequential damages arising from "
        "your use of this tool, including but not limited to financial losses from "
        "trading or investment decisions made based on the data provided.\n\n"
        "**Past performance.** Historical data and past risk metrics do not guarantee "
        "future results.\n\n"
        "**Use at your own risk.** By using this tool, you acknowledge that you "
        "understand and accept these terms. If you do not agree, do not use the tool."
    )
    st.caption("Last updated: June 2026")

# ── Footer ──
st.markdown(
    f'<div class="app-footer">'
    f'{icon_html(GITHUB)} Built by <a href="https://github.com/AshayK003">AshayK003</a> · '
    f"{icon_html(HEART)} "
    f'<a href="https://chai4.me/ashaykushwaha003">Support on Chai4Me</a>'
    f"</div>",
    unsafe_allow_html=True,
)
