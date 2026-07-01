"""
Risk dashboard — metric cards, tabs, and layout.
Thin Streamlit presentation that calls engine functions.
Uses Lucide SVG icons instead of emojis.
"""

from __future__ import annotations

import streamlit as st

from engine import (
    BenchmarkComparison,
    MonteCarloResult,
    OptimizationResult,
    Portfolio,
    RebalanceSuggestion,
    RegimeResult,
    RiskMetrics,
    ScenarioResult,
    SectorExposure,
)


def render_metric_row(portfolio: Portfolio, risk: RiskMetrics) -> None:
    """Display top-level portfolio metric cards."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Total Invested",
            f"Rs {portfolio.total_invested:,.0f}",
        )
    with col2:
        st.metric(
            "Current Value",
            f"Rs {portfolio.total_current:,.0f}",
        )
    with col3:
        pnl = portfolio.total_pnl
        st.metric(
            "P&L",
            f"Rs {pnl:+,.0f}",
            delta=f"{portfolio.total_pnl_pct:+.2f}%",
            delta_color="normal",
        )
    with col4:
        st.metric(
            "Holdings",
            str(portfolio.holding_count),
        )


def render_risk_cards(risk: RiskMetrics) -> None:
    """Display risk metric cards in a 4-column grid."""
    st.subheader("Risk Metrics")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Annual Volatility", f"{risk.volatility_annual:.1f}%")
        st.caption("Higher = riskier")
    with col2:
        st.metric("VaR (95%)", f"{risk.var_95:.2f}%")
        st.caption("Daily loss at 95% confidence")
    with col3:
        st.metric("CVaR (95%)", f"{risk.cvar_95:.2f}%")
        st.caption("Expected loss beyond VaR")
    with col4:
        st.metric("Max Drawdown", f"{risk.max_drawdown:.1f}%")
        st.caption(f"{risk.max_drawdown_start} to {risk.max_drawdown_end}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Sharpe Ratio", f"{risk.sharpe:.2f}")
        st.caption(">1 good, >2 great")
    with col2:
        st.metric("Sortino Ratio", f"{risk.sortino:.2f}")
        st.caption("Downside-adjusted Sharpe")
    with col3:
        st.metric("CAGR", f"{risk.cagr:.1f}%")
        st.caption("Annualized return")
    with col4:
        delta_color = "normal" if risk.beta <= 1 else "inverse"
        st.metric("Beta", f"{risk.beta:.2f}", delta_color=delta_color)
        st.caption("1.0 = market risk")


def render_sector_section(sector: SectorExposure) -> None:
    """Display sector concentration analysis."""
    st.subheader("Sector Allocation")

    if sector.concentrated_sectors:
        for sec in sector.concentrated_sectors:
            pct = sector.sector_allocation.get(sec, 0)
            st.warning(
                f"**{sec}** is {pct:.0f}% of your portfolio — high concentration risk",
            )

    col1, col2 = st.columns(2)
    with col1:
        score = sector.diversification_score
        st.metric("Diversification Score", f"{score:.0f}/100")
        st.caption("Higher = more diversified")
    with col2:
        st.metric("Herfindahl Index", f"{sector.herfindahl_index:.3f}")
        st.caption(">0.25 = concentrated")


def render_benchmark_section(benchmark: BenchmarkComparison) -> None:
    """Display benchmark comparison."""
    st.subheader("vs Nifty 50")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Portfolio Return", f"{benchmark.portfolio_return:.1f}%")
    with col2:
        st.metric("Benchmark Return", f"{benchmark.benchmark_return:.1f}%")
    with col3:
        delta_color = "normal" if benchmark.alpha >= 0 else "inverse"
        st.metric("Alpha", f"{benchmark.alpha:+.1f}%", delta_color=delta_color)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tracking Error", f"{benchmark.tracking_error:.1f}%")
    with col2:
        st.metric("Information Ratio", f"{benchmark.information_ratio:.3f}")
    with col3:
        st.metric(
            "Months Beating Benchmark",
            f"{benchmark.outperformance_months}/{benchmark.total_months}",
        )


def render_stock_table(portfolio: Portfolio) -> None:
    """Display individual holding P&L table."""
    st.subheader("Holdings Breakdown")

    rows = []
    for h in portfolio.holdings:
        rows.append(
            {
                "Ticker": h.ticker.replace(".NS", ""),
                "Name": h.name,
                "Qty": h.quantity,
                "Avg Price": f"Rs {h.avg_price:,.2f}",
                "Current": f"Rs {h.current_price:,.2f}" if h.current_price else "\u2014",
                "Invested": f"Rs {h.invested_value:,.0f}",
                "P&L": f"Rs {h.pnl:+,.0f}",
                "P&L %": f"{h.pnl_pct:+.1f}%",
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_stock_risk_table(risk_df: pd.DataFrame) -> None:
    """Display per-stock risk attribution table."""
    st.subheader("Stock Risk Attribution")
    if risk_df.empty:
        st.info("Risk attribution requires price data.")
        return

    def _highlight_risk(val: float) -> str:
        if val > 25:
            return "color: #ef4444; font-weight: 700"
        if val > 15:
            return "color: #f59e0b; font-weight: 600"
        if val < 5:
            return "color: #29c76a"
        return ""

    styled = risk_df.style.map(_highlight_risk, subset=["Risk Contrib (%)"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.caption(
        "**Risk Contrib %** \u2014 share of total portfolio risk attributed to each holding. "
        "Higher means the stock contributes more to portfolio volatility. "
        "**MRC** (Marginal Risk Contribution) \u2014 change in portfolio risk for a 1% point increase in weight."
    )


def _opt_reason(
    ticker: str, cur_w_pct: float, opt_w_pct: float, risk_data: dict | None,
) -> str:
    """One-line explanation for a weight change recommendation."""
    change = opt_w_pct - cur_w_pct
    if abs(change) < 1.0:
        return ""
    if not risk_data:
        return ""

    vol = risk_data.get("volatility", {}).get(ticker)
    avg_vol = risk_data.get("avg_volatility")
    avg_corr = risk_data.get("avg_correlation", {}).get(ticker)
    sector = risk_data.get("sector", {}).get(ticker, "")
    sec_alloc = risk_data.get("sector_allocation", {})
    beta = risk_data.get("beta", {}).get(ticker)

    if change > 0:
        if vol is not None and avg_vol and vol < avg_vol * 0.85:
            return f"Lower vol ({vol:.0f}% vs {avg_vol:.0f}% avg) → increase"
        if avg_corr is not None and avg_corr < 0.35:
            return f"Low avg corr ({avg_corr:.2f}) → diversification benefit"
        if beta is not None and beta < 0.7:
            return f"Low beta ({beta:.2f}) → reduces market sensitivity"
        if sector and sec_alloc.get(sector, 0) > 25:
            return f"Offsets {sector} concentr. ({sec_alloc[sector]:.0f}%)"
        if vol is not None and avg_vol and vol < avg_vol:
            return f"Below-avg vol ({vol:.0f}%) → higher allocation"
        if avg_corr is not None and avg_corr < 0.5:
            return f"Moderate corr ({avg_corr:.2f}) → some diversification"
        return "Underweight vs optimal allocation"
    else:
        if vol is not None and avg_vol and vol > avg_vol * 1.15:
            return f"Higher vol ({vol:.0f}% vs {avg_vol:.0f}% avg) → reduce"
        if avg_corr is not None and avg_corr > 0.65:
            return f"High avg corr ({avg_corr:.2f}) → limits diversification"
        if sector and sec_alloc.get(sector, 0) > 25:
            return f"Sector concentr. ({sec_alloc[sector]:.0f}%) → reduce"
        if beta is not None and beta > 1.3:
            return f"High beta ({beta:.2f}) → amplifies market risk"
        if vol is not None and avg_vol and vol > avg_vol:
            return f"Above-avg vol ({vol:.0f}%) → lower allocation"
        if avg_corr is not None and avg_corr > 0.5:
            return f"Moderately high corr ({avg_corr:.2f})"
        return "Overweight vs optimal allocation"


def render_optimization_section(
    opt: OptimizationResult | None,
    portfolio: Portfolio | None = None,
    risk_data: dict | None = None,
) -> None:
    """Display portfolio optimization results."""
    st.subheader("Portfolio Optimization")

    if opt is None or not opt.weights:
        st.info("Add at least 2 holdings to see optimization suggestions.")
        return

    if opt.expected_return:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Expected Return (Annual)", f"{opt.expected_return:.1f}%")
        with col2:
            st.metric("Expected Volatility", f"{opt.expected_volatility:.1f}%")
        with col3:
            st.metric("Sharpe Ratio", f"{opt.sharpe:.2f}")

    method_labels = {"hrp": "Hierarchical Risk Parity", "min_volatility": "Minimum Volatility", "max_sharpe": "Maximum Sharpe"}
    method_name = method_labels.get(opt.method, opt.method)
    st.caption(f"Method: {method_name}")

    if opt.method == "hrp":
        with st.expander("How HRP works"):
            st.markdown(
                "**Hierarchical Risk Parity** (López de Prado, 2016) builds a diversified "
                "portfolio in three steps:\n\n"
                "1. **Cluster** — assets are grouped by correlation similarity "
                "using hierarchical clustering (Ward linkage), producing a tree structure.\n"
                "2. **Quasi-diagonalize** — the tree is flattened into an ordering that "
                "keeps similar assets adjacent.\n"
                "3. **Recursive bisection** — the ordered list is repeatedly split in half, "
                "allocating inverse-variance weights within each sub-cluster. "
                "This ensures risk is spread evenly across clusters.\n\n"
                "**Why it's reliable:** No covariance matrix inversion (stable with "
                "highly correlated assets). Purely risk-based — no return forecasts needed. "
                "Covariance is estimated using **Ledoit-Wolf shrinkage**, which reduces "
                "noise by shrinking extreme correlations toward the average."
            )

    # Current vs Optimized comparison
    if portfolio and portfolio.total_current > 0:
        col1, col2 = st.columns(2)
        total_value = portfolio.total_current
        current_weights = {h.ticker: h.current_value / total_value for h in portfolio.holdings if h.ticker in opt.weights}

        with col1:
            from ui.charts import allocation_pie
            st.plotly_chart(
                allocation_pie(current_weights, "Current Allocation"),
                use_container_width=True,
                key="current_alloc",
            )

        with col2:
            from ui.charts import allocation_pie
            st.plotly_chart(
                allocation_pie(opt.weights, "Optimized Allocation"),
                use_container_width=True,
                key="opt_alloc",
            )

        comparison = []
        for ticker, opt_w in sorted(opt.weights.items(), key=lambda x: x[1], reverse=True):
            cur_w = current_weights.get(ticker, 0.0)
            cur_val = cur_w * total_value
            opt_val = opt_w * total_value
            diff = opt_val - cur_val
            reason = _opt_reason(ticker, cur_w * 100, opt_w * 100, risk_data)
            comparison.append({
                "Ticker": ticker.replace(".NS", ""),
                "Current": f"{cur_w * 100:.0f}%",
                "Optimized": f"{opt_w * 100:.0f}%",
                "Change (Rs)": f"{diff:+,.0f}",
                "Why": reason,
            })
        st.dataframe(comparison, use_container_width=True, hide_index=True)

        # Warn if optimization concentrates >25% in any single holding
        max_opt_w = max(opt.weights.values())
        if max_opt_w > 0.25:
            st.caption(
                ":warning: Risk-parity optimization is purely risk-based and may "
                "overweight low-volatility holdings. This may not be appropriate "
                "for return-seeking investors."
            )
    else:
        rows = []
        for ticker, weight in sorted(opt.weights.items(), key=lambda x: x[1], reverse=True):
            rows.append({
                "Ticker": ticker.replace(".NS", ""),
                "Suggested Weight": f"{weight * 100:.1f}%",
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)


def render_monte_carlo_section(mc: MonteCarloResult | None) -> None:
    """Display Monte Carlo simulation results."""
    st.subheader("Monte Carlo Projection")

    if mc is None:
        st.info("Not enough data for Monte Carlo simulation.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Expected Return", f"{mc.expected_return:.1f}%")
    with col2:
        st.metric("Median Return", f"{mc.median_return:.1f}%")
    with col3:
        st.metric("Probability of Profit", f"{mc.prob_profit:.0f}%")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("VaR (95%)", f"{mc.var_95:.1f}%")
    with col2:
        st.metric("CVaR (95%)", f"{mc.cvar_95:.1f}%")
    with col3:
        st.metric("95% CI Range", f"{mc.ci_lower:.1f}% to {mc.ci_upper:.1f}%")

    st.caption(f"Based on {mc.n_simulations:,} simulations over {mc.horizon_days} trading days")


def render_regime_section(regime: RegimeResult | None) -> None:
    """Display market regime detection results."""
    st.subheader("Market Regime Analysis")

    if regime is None:
        st.info("Not enough return data for regime detection (need 50+ trading days).")
        return

    # Per-regime stats
    cols = st.columns(len(regime.stats))
    for i, stat in enumerate(regime.stats):
        with cols[i]:
            color = "green" if stat["label"] in ("Bull", "Strong Bull") else ("red" if stat["label"] in ("Bear", "Crisis") else "orange")
            st.markdown(f"**<span style='color:{color}'>{stat['label']}</span>**", unsafe_allow_html=True)
            st.metric("Occurrence", f"{stat['pct']}%")
            st.metric("Mean Return", f"{stat['mean_return']:+.3f}%")
            st.metric("Annual Vol", f"{stat['annual_vol']:.1f}%")
            st.metric("Cum Return", f"{stat['cum_return']:+.1f}%")

    with st.expander("Transition Matrix"):
        st.caption("Probability of moving from row state to column state")
        trans = regime.transition_matrix
        trans_rows = []
        for i, label in enumerate(regime.labels):
            trans_rows.append({"From \\ To": label, **{regime.labels[j]: f"{trans[i][j]:.1%}" for j in range(len(regime.labels))}})
        st.dataframe(trans_rows, use_container_width=True, hide_index=True)


def render_scenario_section(scenarios: list[ScenarioResult]) -> None:
    """Display scenario / stress test results."""
    st.subheader("Scenario Analysis")
    if not scenarios:
        st.info("Scenario analysis requires benchmark data. Select a benchmark index to enable.")
        return

    st.caption("Estimated portfolio impact under different market scenarios, based on each holding's beta.")
    cols = st.columns(len(scenarios))
    for i, s in enumerate(scenarios):
        with cols[i]:
            delta_color = "normal" if s.portfolio_impact_pct >= 0 else "inverse"
            st.metric(
                s.name,
                f"{s.portfolio_impact_pct:+.1f}%",
                delta_color=delta_color,
            )

    with st.expander("Per-holding impact details"):
        for s in scenarios:
            st.markdown(f"**{s.name}**")
            rows = []
            for h in s.holding_impacts:
                rows.append({
                    "Ticker": h["ticker"],
                    "Weight": f"{h['weight_pct']:.0f}%",
                    "Beta": h["beta"],
                    "Est. Impact": f"{h['impact_pct']:+.1f}%",
                    "Impact (Rs)": f"Rs {h['impact_rs']:,.0f}",
                })
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)
            st.divider()


def render_rebalance_section(
    rebalance: RebalanceSuggestion | None,
    risk_data: dict | None = None,
) -> None:
    """Display portfolio rebalancing suggestions."""
    st.subheader("Rebalancing Suggestions")
    if rebalance is None or not rebalance.trades:
        st.info("Add holdings to see rebalancing suggestions.")
        return

    target_labels = {"equal_weight": "Equal Weight", "current_cap": "Current Cap"}
    st.caption(f"Target: {target_labels.get(rebalance.target_method, rebalance.target_method)}")
    st.metric("Total Drift", f"{rebalance.total_drift_pct:.1f}%", delta_color="inverse")

    rows = []
    for t in rebalance.trades:
        action_icon = "🟢" if t["action"] == "buy" else ("🔴" if t["action"] == "sell" else "⚪")
        reason = _opt_reason(
            f"{t['ticker']}.NS",
            t["current_w_pct"],
            t["target_w_pct"],
            risk_data,
        )
        rows.append({
            "Ticker": t["ticker"],
            "Current": f"{t['current_w_pct']:.0f}%",
            "Target": f"{t['target_w_pct']:.0f}%",
            "Drift": f"{t['drift_pct']:+.1f}%",
            "Action": f"{action_icon} {t['action'].title()}",
            "Change (Rs)": f"Rs {t['change_rs']:+,.0f}",
            "Why": reason,
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
