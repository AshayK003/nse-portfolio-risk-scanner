"""
Risk dashboard — metric cards, tabs, and layout.
Thin Streamlit presentation that calls engine functions.
Uses Lucide SVG icons instead of emojis.
"""

from __future__ import annotations

import streamlit as st

from engine import BenchmarkComparison, Portfolio, RiskMetrics, SectorExposure
from ui.icons import (
    ACTIVITY,
    ARROW_UP_DOWN,
    PIE_CHART,
    SEARCH,
    icon_html,
)


def render_metric_row(portfolio: Portfolio, risk: RiskMetrics) -> None:
    """Display top-level portfolio metric cards."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Total Invested",
            f"₹{portfolio.total_invested:,.0f}",
        )
    with col2:
        st.metric(
            "Current Value",
            f"₹{portfolio.total_current:,.0f}",
        )
    with col3:
        pnl = portfolio.total_pnl
        st.metric(
            "P&L",
            f"₹{pnl:+,.0f}",
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
    st.markdown(
        f'<div class="section-header">{icon_html(ACTIVITY)} Risk Metrics</div>', unsafe_allow_html=True
    )

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
    st.markdown(
        f'<div class="section-header">{icon_html(PIE_CHART)} Sector Allocation</div>', unsafe_allow_html=True
    )

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
    st.markdown(f'<div class="section-header">{icon_html(SEARCH)} vs Nifty 50</div>', unsafe_allow_html=True)

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
    st.markdown(
        f'<div class="section-header">{icon_html(ARROW_UP_DOWN)} Holdings Breakdown</div>',
        unsafe_allow_html=True,
    )

    rows = []
    for h in portfolio.holdings:
        rows.append(
            {
                "Ticker": h.ticker.replace(".NS", ""),
                "Name": h.name,
                "Qty": h.quantity,
                "Avg Price": f"₹{h.avg_price:,.2f}",
                "Current": f"₹{h.current_price:,.2f}" if h.current_price else "—",
                "Invested": f"₹{h.invested_value:,.0f}",
                "P&L": f"₹{h.pnl:+,.0f}",
                "P&L %": f"{h.pnl_pct:+.1f}%",
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)
