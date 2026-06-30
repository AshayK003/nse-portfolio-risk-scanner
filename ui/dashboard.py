"""
Risk dashboard — metric cards, tabs, and layout.
Thin Streamlit presentation that calls engine functions.
Uses Lucide SVG icons instead of emojis.
"""

from __future__ import annotations

import facade
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
        facade.Metric(label="Total Invested", value=f"Rs {portfolio.total_invested:,.0f}")
    with col2:
        facade.Metric(label="Current Value", value=f"Rs {portfolio.total_current:,.0f}")
    with col3:
        facade.Metric(
            label="P&L",
            value=f"Rs {portfolio.total_pnl:+,.0f}",
            delta=f"{portfolio.total_pnl_pct:+.2f}%",
        )
    with col4:
        facade.Metric(label="Holdings", value=str(portfolio.holding_count))


def render_risk_cards(risk: RiskMetrics) -> None:
    """Display risk metric cards in a 4-column grid."""
    st.subheader("Risk Metrics")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        facade.Metric(label="Annual Volatility", value=f"{risk.volatility_annual:.1f}%")
        st.caption("Higher = riskier")
    with col2:
        facade.Metric(label="VaR (95%)", value=f"{risk.var_95:.2f}%")
        st.caption("Daily loss at 95% confidence")
    with col3:
        facade.Metric(label="CVaR (95%)", value=f"{risk.cvar_95:.2f}%")
        st.caption("Expected loss beyond VaR")
    with col4:
        facade.Metric(label="Max Drawdown", value=f"{risk.max_drawdown:.1f}%")
        st.caption(f"{risk.max_drawdown_start} to {risk.max_drawdown_end}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        facade.Metric(label="Sharpe Ratio", value=f"{risk.sharpe:.2f}")
        st.caption(">1 good, >2 great")
    with col2:
        facade.Metric(label="Sortino Ratio", value=f"{risk.sortino:.2f}")
        st.caption("Downside-adjusted Sharpe")
    with col3:
        facade.Metric(label="CAGR", value=f"{risk.cagr:.1f}%")
        st.caption("Annualized return")
    with col4:
        facade.Metric(label="Beta", value=f"{risk.beta:.2f}")
        st.caption("1.0 = market risk")


def render_sector_section(sector: SectorExposure) -> None:
    """Display sector concentration analysis."""
    st.subheader("Sector Allocation")

    if sector.concentrated_sectors:
        for sec in sector.concentrated_sectors:
            pct = sector.sector_allocation.get(sec, 0)
            facade.Alert(f"**{sec}** is {pct:.0f}% of your portfolio — high concentration risk", variant="warning")

    col1, col2 = st.columns(2)
    with col1:
        facade.Metric(label="Diversification Score", value=f"{sector.diversification_score:.0f}/100")
        st.caption("Higher = more diversified")
    with col2:
        facade.Metric(label="Herfindahl Index", value=f"{sector.herfindahl_index:.3f}")
        st.caption(">0.25 = concentrated")


def render_benchmark_section(benchmark: BenchmarkComparison) -> None:
    """Display benchmark comparison."""
    st.subheader("vs Nifty 50")

    col1, col2, col3 = st.columns(3)
    with col1:
        facade.Metric(label="Portfolio Return", value=f"{benchmark.portfolio_return:.1f}%")
    with col2:
        facade.Metric(label="Benchmark Return", value=f"{benchmark.benchmark_return:.1f}%")
    with col3:
        facade.Metric(label="Alpha", value=f"{benchmark.alpha:+.1f}%")

    col1, col2, col3 = st.columns(3)
    with col1:
        facade.Metric(label="Tracking Error", value=f"{benchmark.tracking_error:.1f}%")
    with col2:
        facade.Metric(label="Information Ratio", value=f"{benchmark.information_ratio:.3f}")
    with col3:
        facade.Metric(
            label="Months Beating Benchmark",
            value=f"{benchmark.outperformance_months}/{benchmark.total_months}",
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
                "Current": f"Rs {h.current_price:,.2f}" if h.current_price else "—",
                "Invested": f"Rs {h.invested_value:,.0f}",
                "P&L": f"Rs {h.pnl:+,.0f}",
                "P&L %": f"{h.pnl_pct:+.1f}%",
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_optimization_section(opt: OptimizationResult | None, portfolio: Portfolio | None = None) -> None:
    """Display portfolio optimization results."""
    st.subheader("Portfolio Optimization")

    if opt is None or not opt.weights:
        facade.Alert("Add at least 2 holdings to see optimization suggestions.", variant="info")
        return

    if opt.expected_return:
        col1, col2, col3 = st.columns(3)
        with col1:
            facade.Metric(label="Expected Return (Annual)", value=f"{opt.expected_return:.1f}%")
        with col2:
            facade.Metric(label="Expected Volatility", value=f"{opt.expected_volatility:.1f}%")
        with col3:
            facade.Metric(label="Sharpe Ratio", value=f"{opt.sharpe:.2f}")

    method_labels = {"hrp": "Hierarchical Risk Parity", "min_volatility": "Minimum Volatility", "max_sharpe": "Maximum Sharpe"}
    method_name = method_labels.get(opt.method, opt.method)
    st.caption(f"Method: {method_name}")

    if opt.method == "hrp":
        with facade.Accordion("How HRP works"):
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
            comparison.append({
                "Ticker": ticker.replace(".NS", ""),
                "Current Weight": f"{cur_w * 100:.1f}%",
                "Optimized Weight": f"{opt_w * 100:.1f}%",
                "Current Value (Rs)": f"{cur_val:,.0f}",
                "Optimized Value (Rs)": f"{opt_val:,.0f}",
                "Change (Rs)": f"{diff:+,.0f}",
            })
        st.dataframe(comparison, use_container_width=True, hide_index=True)
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
        facade.Alert("Not enough data for Monte Carlo simulation.", variant="info")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        facade.Metric(label="Expected Return", value=f"{mc.expected_return:.1f}%")
    with col2:
        facade.Metric(label="Median Return", value=f"{mc.median_return:.1f}%")
    with col3:
        facade.Metric(label="Probability of Profit", value=f"{mc.prob_profit:.0f}%")

    col1, col2, col3 = st.columns(3)
    with col1:
        facade.Metric(label="VaR (95%)", value=f"{mc.var_95:.1f}%")
    with col2:
        facade.Metric(label="CVaR (95%)", value=f"{mc.cvar_95:.1f}%")
    with col3:
        facade.Metric(label="95% CI Range", value=f"{mc.ci_lower:.1f}% to {mc.ci_upper:.1f}%")

    st.caption(f"Based on {mc.n_simulations:,} simulations over {mc.horizon_days} trading days")


def render_regime_section(regime: RegimeResult | None) -> None:
    """Display market regime detection results."""
    st.subheader("Market Regime Analysis")

    if regime is None:
        facade.Alert("Not enough return data for regime detection (need 50+ trading days).", variant="info")
        return

    # Per-regime stats
    cols = st.columns(len(regime.stats))
    for i, stat in enumerate(regime.stats):
        with cols[i]:
            color = "green" if stat["label"] in ("Bull", "Strong Bull") else ("red" if stat["label"] in ("Bear", "Crisis") else "orange")
            st.markdown(f"**<span style='color:{color}'>{stat['label']}</span>**", unsafe_allow_html=True)
            facade.Metric(label="Occurrence", value=f"{stat['pct']}%")
            facade.Metric(label="Mean Return", value=f"{stat['mean_return']:+.3f}%")
            facade.Metric(label="Annual Vol", value=f"{stat['annual_vol']:.1f}%")
            facade.Metric(label="Cum Return", value=f"{stat['cum_return']:+.1f}%")

    with facade.Accordion("Transition Matrix"):
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
        facade.Alert("Scenario analysis requires benchmark data. Select a benchmark index to enable.", variant="info")
        return

    st.caption("Estimated portfolio impact under different market scenarios, based on each holding's beta.")
    cols = st.columns(len(scenarios))
    for i, s in enumerate(scenarios):
        with cols[i]:
            facade.Metric(label=s.name, value=f"{s.portfolio_impact_pct:+.1f}%")

    with facade.Accordion("Per-holding impact details"):
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
            facade.Separator()


def render_rebalance_section(rebalance: RebalanceSuggestion | None) -> None:
    """Display portfolio rebalancing suggestions."""
    st.subheader("Rebalancing Suggestions")
    if rebalance is None or not rebalance.trades:
        facade.Alert("Add holdings to see rebalancing suggestions.", variant="info")
        return

    target_labels = {"equal_weight": "Equal Weight", "current_cap": "Current Cap"}
    st.caption(f"Target: {target_labels.get(rebalance.target_method, rebalance.target_method)}")
    facade.Metric(label="Total Drift", value=f"{rebalance.total_drift_pct:.1f}%")

    rows = []
    for t in rebalance.trades:
        action_icon = "🟢" if t["action"] == "buy" else ("🔴" if t["action"] == "sell" else "⚪")
        rows.append({
            "Ticker": t["ticker"],
            "Current": f"{t['current_w_pct']:.0f}%",
            "Target": f"{t['target_w_pct']:.0f}%",
            "Drift": f"{t['drift_pct']:+.1f}%",
            "Action": f"{action_icon} {t['action'].title()}",
            "Change (Rs)": f"Rs {t['change_rs']:+,.0f}",
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
