"""
NSE Portfolio Risk Scanner — Streamlit app entry point.

Thin orchestration layer: reads CSV -> computes risk -> renders UI.
Engine has ZERO Streamlit imports. UI has ZERO business logic.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import streamlit as st

from engine._log import logger

from data.prices import fetch_benchmark, fetch_prices, fetch_prices_refreshed
from engine import AnalysisReport
from engine.__init__ import RISK_PROFILES
from engine.benchmark import BENCHMARK_TICKERS, compare_to_benchmark
from engine.factors import compute_factor_exposures, estimate_macro_sensitivities
from engine.fundamentals import compute_all_zscores
from engine.garch_var import estimate_garch_var
from engine.narrative import generate_narrative
from engine.optimization import optimize_hrp, optimize_max_sharpe, optimize_min_volatility, suggest_rebalance
from engine.optimization_advanced import optimize_advanced
from engine.pelve import compute_pelve
from engine.performance import (
    compute_max_drawdown,
    compute_portfolio_returns,
)
from engine.portfolio import validate_portfolio
from engine.recommendations import generate_recommendations
from engine.regime import detect_regimes
from engine.risk import (
    compute_correlation_matrix,
    compute_risk_metrics,
    compute_stock_risk_attribution,
    denoise_correlation,
    monte_carlo_simulation,
    rolling_volatility,
)
from engine.scenario import run_default_scenarios, run_macro_scenarios
from engine.scoring import compute_institutional_scores
from engine.sector import classify_holdings, compute_sector_exposure, load_sector_map
from engine.warnings import detect_all_warnings
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
    render_advanced_section,
    render_benchmark_section,
    render_metric_row,
    render_monte_carlo_section,
    render_narrative_section,
    render_optimization_section,
    render_rebalance_section,
    render_regime_section,
    render_risk_cards,
    render_scenario_section,
    render_sector_section,
    render_stock_risk_table,
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
    initial_sidebar_state="collapsed",
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
if "force_refresh_cb" not in st.session_state:
    st.session_state.force_refresh_cb = False
if "force_refresh" not in st.session_state:
    st.session_state.force_refresh = False
if "_cache" not in st.session_state:
    st.session_state._cache = None

# ── Step 1: Upload or use existing portfolio ──
portfolio = render_upload_tab()
if portfolio is None:
    st.stop()

st.session_state.portfolio = portfolio

# Allow editing
portfolio = render_data_editor(portfolio)
render_save_button(portfolio)

# ── Shareable link ──
with st.expander("Share Portfolio", expanded=False):
    import base64
    import json

    holdings_data = [
        {"t": h.ticker.replace(".NS", ""), "n": h.name, "q": h.quantity, "p": h.avg_price}
        for h in portfolio.holdings
    ]
    encoded = base64.b64encode(json.dumps({"holdings": holdings_data}).encode()).decode()
    st.code(f"?p={encoded}", language="text")
    st.caption(
        "Append this to the app URL to share your portfolio. "
        "Example: `https://yourapp.streamlit.app/?p=...` "
        "No data is stored on any server."
    )

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
    force = st.checkbox(
        "Force refresh prices", value=False, key="force_refresh_cb"
    )
if force:
    st.session_state.force_refresh = True
else:
    st.session_state.force_refresh = False

risk_free_rate = st.session_state.get("risk_free_rate", 6.5) / 100.0

# ── Input hash — skip recomputation when portfolio hasn't changed ──
risk_profile_key = st.session_state.get("risk_profile", "moderate")
profile = RISK_PROFILES[risk_profile_key]
_input_hash = hashlib.sha256(
    json.dumps(
        {
            "holdings": [(h.ticker, h.quantity, h.avg_price, h.current_price) for h in portfolio.holdings],
            "benchmark": benchmark_choice,
            "risk_profile": risk_profile_key,
            "risk_free_rate": round(risk_free_rate, 4),
        },
        sort_keys=True,
    ).encode(),
).hexdigest()[:16]

_needs_compute = st.session_state.force_refresh or st.session_state.get("_last_input_hash") != _input_hash

if _needs_compute:
    # ── Step 3: Fetch prices ──
    with st.spinner("Fetching prices..."):
        try:
            if st.session_state.force_refresh:
                prices = fetch_prices_refreshed(portfolio.holdings, period="1y")
                st.session_state.force_refresh = False
            else:
                prices = fetch_prices(portfolio.holdings, period="1y")
        except ValueError as e:
            st.error(f"Could not fetch price data: {e}")
            st.stop()
        except Exception as e:
            logger.error("Price fetch failed: {e}", e=e)
            st.error(f"An unexpected error occurred while fetching prices: {e}")
            st.stop()

    # ── Align portfolio with available price data ──
    failed = [h.ticker for h in portfolio.holdings if h.ticker not in prices.columns]
    if failed:
        portfolio.holdings = [h for h in portfolio.holdings if h.ticker in prices.columns]
        st.warning(f"Could not fetch prices for: {', '.join(failed)}. These holdings are excluded.")

    # Remove holdings where current_price is still 0 (all-NaN history after ffill).
    # These inflate P&L because current_value = 0, making pnl = -invested_value.
    zero_price = [h.ticker for h in portfolio.holdings if h.current_price == 0.0]
    if zero_price:
        portfolio.holdings = [h for h in portfolio.holdings if h.current_price > 0.0]
        st.warning(f"No valid price data for: {', '.join(zero_price)}. These holdings are excluded.")

    if not portfolio.holdings:
        st.error("All holdings failed to fetch. No price data available for analysis.")
        st.stop()

    # Validate portfolio (now that current_price is set)
    validation_warnings = validate_portfolio(portfolio)
    for w in validation_warnings:
        st.warning(w)

    try:
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
            except Exception as e:
                logger.warning("Benchmark fetch failed: {e}", e=e)
                benchmark_prices = pd.Series(dtype=float)

        benchmark_returns = benchmark_prices.pct_change().dropna() if not benchmark_prices.empty and len(benchmark_prices) > 1 else None
        benchmark_cum = (
            (1 + benchmark_returns).cumprod() if benchmark_returns is not None else pd.Series(dtype=float)
        )

        # Compute all risk metrics
        with st.spinner("Computing risk metrics..."):
            risk = compute_risk_metrics(
                prices, weights, risk_free_rate=risk_free_rate,
                benchmark_returns=benchmark_returns, portfolio_returns=portfolio_returns
            )
            sector = compute_sector_exposure(portfolio.holdings)
            benchmark = (
                compare_to_benchmark(portfolio_returns, benchmark_returns)
                if benchmark_returns is not None
                else None
            )

        # ── New v0.6.0 features ──

        # Correlation matrix (needed for denoising)
        raw_corr = compute_correlation_matrix(prices) if not prices.empty else pd.DataFrame()

        # Portfolio Optimization (method selected by risk profile)
        opt_result = None
        if len(weights) >= 2:
            rets = prices.pct_change().dropna()
            method_map = {
                "min_volatility": lambda: optimize_min_volatility(rets, max_single_weight=profile.max_single_weight),
                "hrp": lambda: optimize_hrp(rets, max_single_weight=profile.max_single_weight),
                "max_sharpe": lambda: optimize_max_sharpe(rets, max_single_weight=profile.max_single_weight),
            }
            opt_fn = method_map.get(profile.method, method_map["hrp"])
            opt_result = opt_fn()

        # Monte Carlo simulation (stats + chart paths from single run)
        mc_data = (
            monte_carlo_simulation(portfolio_returns, return_paths=True, n_paths=200)
            if not portfolio_returns.empty
            else None
        )
        mc_result = mc_data[0] if mc_data else None
        mc_paths = mc_data[1] if mc_data else None

        # HMM Regime detection
        regime_result = detect_regimes(portfolio_returns) if not portfolio_returns.empty else None

        # Correlation denoising
        denoised_corr = (
            denoise_correlation(raw_corr, len(portfolio_returns)) if not portfolio_returns.empty else None
        )

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
        rebalance = suggest_rebalance(portfolio.holdings, profile=profile) if portfolio.holding_count >= 1 else None

        # ── v0.7.0 Intelligence modules (each guarded so one failure doesn't kill the rest) ──

        factor_report = None
        try:
            factor_report = compute_factor_exposures(prices, weights, benchmark_returns)
        except Exception as e:
            logger.warning("Factor analysis failed: {e}", e=e)

        macro_drivers = None
        try:
            macro_drivers = estimate_macro_sensitivities(portfolio_returns, prices, weights, benchmark_returns)
        except Exception as e:
            logger.warning("Macro drivers failed: {e}", e=e)

        macro_scenarios = []
        try:
            macro_scenarios = run_macro_scenarios(portfolio.holdings, stock_betas) if stock_betas else []
        except Exception as e:
            logger.warning("Macro scenarios failed: {e}", e=e)

        institutional_scores = None
        try:
            institutional_scores = compute_institutional_scores(
                risk, prices, weights, sector.sector_allocation, raw_corr
            )
        except Exception as e:
            logger.warning("Institutional scoring failed: {e}", e=e)

        early_warnings = None
        try:
            early_warnings = detect_all_warnings(prices, returns=None, corr_matrix=raw_corr)
        except Exception as e:
            logger.warning("Early warnings failed: {e}", e=e)

        recommendations = None
        try:
            recommendations = generate_recommendations(
                risk=risk,
                sector=sector,
                benchmark=benchmark,
                portfolio=portfolio,
                factor_report=factor_report,
                institutional_scores=institutional_scores,
                macro_drivers=macro_drivers,
                corr_matrix=raw_corr,
                regime_result=regime_result,
                profile=profile,
            )
        except Exception as e:
            logger.warning("Recommendations failed: {e}", e=e)

        # ── v0.7.9 Advanced modules ──

        zscore = None
        try:
            ticker_list = list(prices.columns)
            zscore = compute_all_zscores(ticker_list) if len(ticker_list) > 0 else []
        except Exception as e:
            logger.warning("Altman Z-Score failed: {e}", e=e)

        var_backtest = None
        try:
            if risk.var_95 != 0 and not portfolio_returns.empty:
                from engine.backtesting import kupiec_pof
                rets_flat = portfolio_returns.values.flatten()
                var_forecast_series = np.full(len(rets_flat), abs(risk.var_95) / 100)
                var_backtest = {"95%": kupiec_pof(
                    var_forecast_series,
                    rets_flat,
                    confidence=0.95,
                )}
        except Exception as e:
            logger.warning("VaR backtest failed: {e}", e=e)

        garch_var = None
        try:
            if not portfolio_returns.empty:
                garch_var = estimate_garch_var(portfolio_returns.values.flatten())
        except Exception as e:
            logger.warning("GARCH VaR failed: {e}", e=e)

        pelve = None
        try:
            if not portfolio_returns.empty:
                rets = portfolio_returns.values.flatten()
                pelve = compute_pelve(rets, epsilon=0.01)
        except Exception as e:
            logger.warning("PELVE failed: {e}", e=e)

        opt_advanced = None
        try:
            if not prices.empty and len(weights) >= 2:
                opt_advanced = optimize_advanced(prices, weights)
        except Exception as e:
            logger.warning("Advanced optimization failed: {e}", e=e)

    except Exception as e:
        logger.error("Analysis computation failed: {e}", e=e)
        st.error(f"An unexpected error occurred during analysis: {e}")
        st.stop()

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
        "factor_report": factor_report,
        "macro_drivers": macro_drivers,
        "macro_scenarios": macro_scenarios,
        "institutional_scores": institutional_scores,
        "early_warnings": early_warnings,
        "recommendations": recommendations,
        "zscore": zscore,
        "var_backtest": var_backtest,
        "garch_var": garch_var,
        "pelve": pelve,
        "opt_advanced": opt_advanced,
    }
    st.session_state._last_input_hash = _input_hash
    st.session_state._report_changed = True
else:
    cache = st.session_state._cache
    prices = cache.get("prices", pd.DataFrame())
    portfolio_returns = cache.get("portfolio_returns", pd.Series(dtype=float))
    portfolio_cum = cache.get("portfolio_cum", pd.Series(dtype=float))
    benchmark_returns = cache.get("benchmark_returns")
    benchmark_cum = cache.get("benchmark_cum", pd.Series(dtype=float))
    raw_corr = cache.get("raw_corr", pd.DataFrame())
    denoised_corr = cache.get("denoised_corr")
    mc_paths = cache.get("mc_paths")
    stock_betas = cache.get("stock_betas", {})
    scenarios = cache.get("scenarios", [])
    rebalance = cache.get("rebalance")
    risk = cache.get("risk")
    sector = cache.get("sector")
    benchmark = cache.get("benchmark")
    opt_result = cache.get("opt_result")
    mc_result = cache.get("mc_result")
    regime_result = cache.get("regime_result")
    factor_report = cache.get("factor_report")
    macro_drivers = cache.get("macro_drivers")
    macro_scenarios = cache.get("macro_scenarios")
    institutional_scores = cache.get("institutional_scores")
    early_warnings = cache.get("early_warnings")
    recommendations = cache.get("recommendations")
    zscore = cache.get("zscore")
    var_backtest = cache.get("var_backtest")
    garch_var = cache.get("garch_var")
    pelve = cache.get("pelve")
    opt_advanced = cache.get("opt_advanced")
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
    factor_report=factor_report,
    macro_drivers=macro_drivers,
    institutional_scores=institutional_scores,
    macro_scenarios=macro_scenarios,
    recommendations=recommendations,
    warnings=early_warnings,
    zscore=zscore,
    var_backtest=var_backtest,
    garch_var=garch_var,
    pelve=pelve,
    optimization_advanced=opt_advanced,
)

# ── Step 4: Display ──
report = st.session_state.report

# Summary metrics
render_metric_row(report.portfolio, report.risk)

# Portfolio Health Gauge
institutional = report.institutional_scores
if institutional and institutional.overall_risk_score > 0:
    health = max(0, min(100, 100 - institutional.overall_risk_score))
    if health >= 70:
        color = "#22C55E"
        label = "Good"
    elif health >= 40:
        color = "#EAB308"
        label = "Moderate"
    else:
        color = "#EF4444"
        label = "High Risk"

    st.markdown(
        f"""<div style="display:flex;align-items:center;gap:1rem;padding:0.75rem 1rem;
                          border:1px solid color-mix(in srgb, {color} 30%, transparent);
                          border-radius:0.5rem;margin-bottom:0.5rem;">
            <div style="flex:1;">
                <div style="font-size:0.75rem;color:#888;text-transform:uppercase;">Portfolio Health</div>
                <div style="font-size:1.5rem;font-weight:700;color:{color};">{health:.0f}/100</div>
                <div style="font-size:0.8rem;color:{color};">{label}</div>
            </div>
            <div style="flex:2;font-size:0.8rem;color:#aaa;line-height:1.4;">
                {institutional.score_interpretation[:200]}
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

# Generate narrative (always available — pure functions, no IO)
narrative = generate_narrative(report)

# Tabs
tab_names = [
    "Risk Metrics",
    "Sector",
    "vs Nifty 50",
    "Charts",
    "Holdings",
    "Scenarios",
    "Recommendations",
    "Export",
]
tabs = st.tabs(tab_names)

with tabs[0]:
    render_narrative_section(narrative)
    render_advanced_section(
        report.zscore, report.var_backtest, report.garch_var, report.pelve, report.optimization_advanced,
    )
    render_risk_cards(report.risk)
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            volatility_gauge(report.risk.volatility_annual), use_container_width=True, key="vol_gauge"
        )
    with col2:
        rv = rolling_volatility(portfolio_returns)
        if len(rv) > 0:
            with st.expander("Rolling 21-day Volatility", expanded=False):
                st.line_chart(rv)

    # ── Institutional Intelligence (collapsible) ──
    if institutional_scores:
        st.divider()
        with st.expander("Institutional Risk Scores & Factor Analysis", expanded=False):
            score_cols = st.columns(5)
            score_labels = [
                ("Overall Risk", institutional_scores.overall_risk_score, "#ef4444"),
                ("Conviction", institutional_scores.conviction_score, "#22c55e"),
                ("Stress", institutional_scores.portfolio_stress_score, "#f59e0b"),
                ("Hidden Corr.", institutional_scores.hidden_correlation_score, "#a855f7"),
                ("Tail Risk", institutional_scores.tail_risk_score, "#ec4899"),
            ]
            for col, (label, score, _color) in zip(score_cols, score_labels, strict=False):
                with col:
                    st.metric(label, f"{score:.0f}/100")
                    st.progress(min(score / 100, 1.0))

            if institutional_scores.score_interpretation:
                st.info(institutional_scores.score_interpretation)

            with st.expander("Risk Factor Breakdown", expanded=False):
                if institutional_scores.risk_factors:
                    for factor in sorted(institutional_scores.risk_factors, key=lambda f: f.composite, reverse=True):
                        with st.expander(
                            f"**{factor.name}** \u2014 Score: {factor.composite:.1f}/100",
                            expanded=factor.composite > 20,
                        ):
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Probability", f"{factor.probability:.0%}")
                            c2.metric("Impact", f"{factor.impact:.0%}")
                            c3.metric("Confidence", f"{factor.confidence:.0%}")
                            st.caption(factor.reasoning)

            with st.expander("Top 5 Actionable Insights", expanded=False):
                if institutional_scores.top_5_insights:
                    for i, insight in enumerate(institutional_scores.top_5_insights, 1):
                        severity_color = (
                            "#ef4444"
                            if insight.composite > 30
                            else "#f59e0b"
                            if insight.composite > 15
                            else "#22c55e"
                        )
                        st.markdown(
                            f"<div style='padding:0.75rem;margin:0.5rem 0;border-left:4px solid {severity_color};"
                            f"background:rgba(255,255,255,0.03);border-radius:0 6px 6px 0;'>"
                            f"<strong>{i}. {insight.name}</strong> (Score: {insight.composite:.1f})<br/>"
                            f"<span style='color:#9ca3af;font-size:0.85rem;'>{insight.reasoning}</span></div>",
                            unsafe_allow_html=True,
                        )

            if factor_report:
                with st.expander("Factor Risk Decomposition", expanded=False):
                    factor_cols = st.columns(2)
                    for i, factor in enumerate(factor_report.factors):
                        col_idx = i % 2
                        with factor_cols[col_idx]:
                            st.metric(
                                factor.name,
                                f"{factor.risk_contribution_pct:.1f}%",
                                help=f"Exposure: {factor.exposure:.3f}",
                            )
                            st.caption(factor.description)
                    st.caption(
                        f"Factor-explained risk: {factor_report.total_factor_risk_pct:.1f}% \u00b7 "
                        f"Idiosyncratic: {factor_report.idiosyncratic_risk_pct:.1f}% \u00b7 "
                        f"Dominant: {factor_report.dominant_factor}"
                    )

    # ── Early Warnings (collapsible) ──
    if early_warnings:
        st.divider()
        with st.expander(
            "Early Warning Signals",
            expanded=early_warnings.overall_warning_level == "critical",
        ):
            level = early_warnings.overall_warning_level
            st.caption(f"Overall level: **{level.upper()}** \u2014 {early_warnings.summary}")

            if early_warnings.signals:
                for sig in early_warnings.signals:
                    sev_colors = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#3b82f6"}
                    sev_color = sev_colors.get(sig.severity.value, "#6b7280")
                    with st.expander(
                        f"**{sig.name}** \u2014 {sig.severity.value.upper()}",
                        expanded=sig.severity.value == "critical",
                    ):
                        st.markdown(f"**{sig.description}**")
                        st.info(f"**Why:** {sig.reasoning}")
                        st.caption(f"**Suggested Action:** {sig.suggested_action}")
                        if sig.affected_holdings:
                            st.caption(f"Affected: {', '.join(sig.affected_holdings)}")
            else:
                st.success("No early-warning signals detected. Portfolio appears stable.")

# ── Tab 1: Sector ──
with tabs[1]:
    render_sector_section(report.sector)
    st.plotly_chart(
        sector_treemap(report.sector.sector_allocation), use_container_width=True, key="sector_treemap"
    )

# ── Tab 2: vs Nifty 50 ──
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

# ── Tab 3: Charts ──
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
        corr = raw_corr if not raw_corr.empty else (
            compute_correlation_matrix(prices) if not prices.empty else pd.DataFrame()
        )
        st.plotly_chart(
            correlation_heatmap(corr),
            use_container_width=True,
            key="corr_heatmap",
        )
    if denoised_corr is not None and not denoised_corr.empty:
        with st.expander("Denoised Correlation (Marchenko-Pastur)"):
            st.plotly_chart(correlation_heatmap(denoised_corr), use_container_width=True, key="corr_denoised")

    st.divider()
    render_monte_carlo_section(mc_result)
    if mc_paths is not None:
        st.plotly_chart(monte_carlo_chart(mc_paths, (5, 95)), use_container_width=True, key="mc_chart")

# ── Tab 4: Holdings ──
with tabs[4]:
    render_stock_table(report.portfolio)
    st.divider()
    risk_attribution = compute_stock_risk_attribution(prices, weights, stock_betas)
    if not risk_attribution.empty:
        render_stock_risk_table(risk_attribution)

# ── Tab 5: Scenarios (merged basic + macro + regime) ──
with tabs[5]:
    render_scenario_section(scenarios)
    st.divider()
    if macro_scenarios:
        st.subheader("Macro-Driven Stress Tests")
        st.caption("Sector-aware scenarios modeling real-world macro events with causal reasoning.")
        for scenario in macro_scenarios:
            severity_color = {
                "extreme": "#ef4444",
                "severe": "#f59e0b",
                "moderate": "#3b82f6",
                "mild": "#22c55e",
            }.get(scenario.severity, "#6b7280")
            with st.expander(
                f"**{scenario.name}** — Portfolio Impact: {scenario.portfolio_impact_pct:+.1f}% · "
                f"Severity: {scenario.severity.upper()} · Probability: {scenario.probability}",
                expanded=scenario.severity in ("severe", "extreme"),
            ):
                st.markdown(f"**Description:** {scenario.description}")
                st.info(f"**Why this matters:** {scenario.reasoning}")

                if scenario.sector_impacts:
                    st.markdown("**Sector Impact Breakdown:**")
                    sector_df = pd.DataFrame(
                        [
                            {"Sector": s, "Impact": f"{imp:+.1f}%"}
                            for s, imp in sorted(scenario.sector_impacts.items(), key=lambda x: x[1])
                        ],
                    )
                    st.dataframe(sector_df, use_container_width=True, hide_index=True)

                if scenario.holding_impacts:
                    st.markdown("**Top 5 Most Affected Holdings:**")
                    top_holdings = sorted(scenario.holding_impacts, key=lambda x: x["impact_pct"])[:5]
                    for h in top_holdings:
                        st.caption(
                            f"• **{h['ticker']}** ({h.get('sector', 'N/A')}) — "
                            f"Weight: {h['weight_pct']:.1f}%, Impact: {h['impact_pct']:+.1f}%, "
                            f"Est. Loss: ₹{abs(h['impact_rs']):,.0f}"
                        )
    else:
        st.info("Macro scenarios require beta data.")

    st.divider()
    render_regime_section(regime_result)
    if regime_result:
        st.plotly_chart(
            regime_chart(portfolio_returns, regime_result.state_sequence),
            use_container_width=True,
            key="regime_chart",
        )

# ── Per-stock risk data for explainability ──
risk_data = {}
if prices is not None and not prices.empty:
    ann_vol = prices.pct_change().std() * np.sqrt(252)
    ticker_vols = (ann_vol * 100).to_dict()
    risk_data["volatility"] = ticker_vols
    risk_data["avg_volatility"] = sum(ticker_vols.values()) / len(ticker_vols) if ticker_vols else 0
if raw_corr is not None and hasattr(raw_corr, "mean"):
    risk_data["avg_correlation"] = raw_corr.mean(axis=1).to_dict()
if stock_betas:
    risk_data["beta"] = stock_betas
if portfolio and portfolio.holdings:
    risk_data["sector"] = {h.ticker: h.sector for h in portfolio.holdings}
if sector:
    risk_data["sector_allocation"] = sector.sector_allocation

# ── Tab 6: Recommendations ──
with tabs[6]:
    render_optimization_section(opt_result, portfolio=report.portfolio, risk_data=risk_data, max_single_weight=profile.max_single_weight)
    render_rebalance_section(rebalance, risk_data=risk_data)
    st.divider()
    if recommendations:
        st.subheader("Portfolio Action Recommendations")
        st.caption(recommendations.summary)

        if recommendations.priority_actions:
            st.markdown("**Priority Actions:**")
            for i, rec in enumerate(recommendations.priority_actions, 1):
                action_colors = {
                    "reduce": "#ef4444",
                    "hedge": "#f59e0b",
                    "diversify": "#3b82f6",
                    "accumulate": "#22c55e",
                    "monitor": "#6b7280",
                    "rebalance": "#a855f7",
                }
                color = action_colors.get(rec.action.value, "#6b7280")
                st.markdown(
                    f"<div style='padding:0.75rem;margin:0.5rem 0;border-left:4px solid {color};"
                    f"background:rgba(255,255,255,0.03);border-radius:0 6px 6px 0;'>"
                    f"<strong>{i}. {rec.action.value.upper()} {rec.target}</strong> "
                    f"<span style='color:#9ca3af;'>({rec.urgency}, confidence: {rec.confidence:.0%})</span><br/>"
                    f"<span style='font-size:0.85rem;'>{rec.reasoning}</span><br/>"
                    f"<span style='font-size:0.8rem;color:#f59e0b;'>Trade-off: {rec.trade_off}</span></div>",
                    unsafe_allow_html=True,
                )

        if recommendations.risk_reduction_potential > 0:
            st.metric("Total Risk Reduction Potential", f"{recommendations.risk_reduction_potential:.1f}%")
            st.info(
                "Risk reduction is a directional estimate based on heuristic rules, "
                "not a backtested or simulated forecast."
            )

        st.divider()
        st.subheader("All Recommendations")
        for rec in recommendations.recommendations:
            action_colors = {
                "reduce": "#ef4444",
                "hedge": "#f59e0b",
                "diversify": "#3b82f6",
                "accumulate": "#22c55e",
                "monitor": "#6b7280",
                "rebalance": "#a855f7",
            }
            color = action_colors.get(rec.action.value, "#6b7280")
            with st.expander(
                f"**{rec.action.value.upper()}** {rec.target} — Urgency: {rec.urgency}",
                expanded=rec.urgency == "immediate",
            ):
                st.markdown(f"**Reasoning:** {rec.reasoning}")
                st.caption(f"**Trade-off:** {rec.trade_off}")
                if rec.details:
                    st.caption(f"**Suggested Action:** {rec.details}")
                st.caption(
                    f"Expected risk reduction: {rec.expected_risk_reduction:.1f}% · Confidence: {rec.confidence:.0%}"
                )
    else:
        st.info("Recommendations require full analysis.")

# ── Tab 7: Export ──
with tabs[7]:
    render_export_section(
        report.portfolio,
        risk=report.risk,
        sector_data=report.sector.sector_allocation,
        mc_result=mc_result,
        portfolio_cum=portfolio_cum,
        recommendations=recommendations,
        risk_data=risk_data,
    )

# ── Step 5: Save analysis run to history (only on fresh computation) ──
if st.session_state.get("_report_changed", False):
    try:
        from storage.db import save_analysis_run
        from storage.models import analysis_from_report

        run = analysis_from_report(report)
        save_analysis_run(run)
    except Exception as e:
        logger.error("Failed to save analysis run: {e}", e=e)

# ── Disclaimer ──
# Permanent visible warning banner (not collapsed)
st.markdown(
    f"<div style='padding:0.75rem 1rem;margin:1rem 0;background:rgba(245,158,11,0.08);"
    f"border-left:4px solid #f59e0b;border-radius:0 6px 6px 0;font-size:0.85rem;' role='alert'>"
    f"<strong>⚠️ Not financial advice.</strong> This tool provides portfolio risk analysis "
    "for educational and informational purposes only. Nothing on this platform constitutes "
    "investment advice or a solicitation to buy or sell securities. "
    "<strong>The creator is not a SEBI-registered investment advisor.</strong> "
    "All trading and investment decisions are solely your responsibility."
    f"</div>",
    unsafe_allow_html=True,
)

# Collapsible detailed limitations
st.markdown(
    f"<details style='font-size:0.85rem;color:#6b7280;'>"
    f"<summary style='cursor:pointer;font-weight:600;color:#f59e0b;display:flex;align-items:center;gap:0.4rem;'>"
    f"{icon_html(ALERT_TRIANGLE, size=14)} Detailed limitations"
    f"</summary>"
    f"<p><strong>Data accuracy.</strong> Data is sourced from third-party public APIs (yfinance, "
    "nselib) and may be delayed, incomplete, or inaccurate. We do not guarantee "
    "the timeliness, accuracy, or completeness of any data displayed.</p>"
    f"<p><strong>Limitations you should know:</strong></p>"
    f"<ul>"
    f"<li><strong>Price data</strong> \u2014 yfinance free tier has 15-20 min delay. Not suitable for "
    "intraday trading without real-time feeds.</li>"
    f"<li><strong>NSE data</strong> \u2014 nselib is an optional dependency. Without it, all data comes "
    "from yfinance, which may have gaps for Indian equities (missing delisted "
    "tickers, delayed corporate actions).</li>"
    f"<li><strong>Risk metrics</strong> \u2014 VaR, CVaR, and Monte Carlo projections are based on "
    "historical return distributions and assume normality. Tail risk is "
    "underestimated during market dislocations (2020 COVID crash, 2008 GFC).</li>"
    f"<li><strong>Beta</strong> \u2014 computed against a single benchmark index using daily returns. "
    "A beta of 1.2 does not guarantee the stock moves 20% more than the market "
    "in all conditions.</li>"
    f"<li><strong>Monte Carlo simulation</strong> \u2014 uses Geometric Brownian Motion, which assumes "
    "returns are normally distributed and volatility is constant. Both assumptions "
    "are violated in real markets.</li>"
    f"<li><strong>HMM regime detection</strong> \u2014 optional dependency (hmmlearn). When unavailable, "
    "a rolling-quantile heuristic is used instead. Neither is a predictor of "
    "future market regimes.</li>"
    f"<li><strong>Scenario analysis</strong> \u2014 estimated using stock beta \u00d7 weight \u00d7 market change. "
    "Beta is itself an estimate from historical data and may not hold during "
    "regime shifts.</li>"
    f"<li><strong>Delivery analysis</strong> \u2014 relies on nselib bhavcopy data, which is typically "
    "available with a 1-day lag.</li>"
    f"</ul>"
    f"<p><strong>No liability.</strong> Under no circumstances shall the creator be liable for any "
    "direct, indirect, incidental, special, or consequential damages arising from "
    "your use of this tool, including but not limited to financial losses from "
    "trading or investment decisions made based on the data provided.</p>"
    f"<p><strong>Past performance.</strong> Historical data and past risk metrics do not guarantee "
    "future results.</p>"
    f"<p><strong>Use at your own risk.</strong> By using this tool, you acknowledge that you "
    "understand and accept these terms. If you do not agree, do not use the tool.</p>"
    f"<p style='font-size:0.75rem;color:#9ca3af;'>Last updated: June 2026</p>"
    f"</details>",
    unsafe_allow_html=True,
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
