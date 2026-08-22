"""
Tab rendering for NSE Portfolio Risk Scanner.

Pure UI layer — uses Streamlit, no business logic, no computation.
Consumes ComputeContext + AnalysisReport produced by engine.compute.
"""

from __future__ import annotations

import html

import numpy as np
import pandas as pd
import streamlit as st

from engine import AnalysisReport
from engine.__init__ import RISK_PROFILES
from engine.compute import ComputeContext
from engine.risk import (
    compute_correlation_matrix,
    compute_stock_risk_attribution,
    rolling_volatility,
)
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
    render_composition_metrics,
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
from ui.fundamentals import render_fundamentals_section
from ui.icons import ALERT_TRIANGLE, GITHUB, HEART, icon_html
from ui.news import render_news_section


def render_health_gauge(report: AnalysisReport) -> None:
    """Portfolio Health gauge block."""
    institutional = report.institutional_scores
    if not institutional or institutional.overall_risk_score <= 0:
        return

    health = max(0, min(100, 100 - institutional.overall_risk_score))
    if health >= 70:
        color, label = "#22C55E", "Good"
    elif health >= 40:
        color, label = "#EAB308", "Moderate"
    else:
        color, label = "#EF4444", "High Risk"

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
                {html.escape(institutional.score_interpretation[:200])}
            </div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_institutional_intelligence(institutional_scores, factor_report, early_warnings) -> None:
    """Institutional risk scores + factor analysis + early warnings."""
    if not institutional_scores:
        return

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
                for factor in sorted(
                    institutional_scores.risk_factors,
                    key=lambda f: f.composite,
                    reverse=True,
                ):
                    with st.expander(
                        f"**{factor.name}** — Score: {factor.composite:.1f}/100",
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
                        f"<strong>{i}. {html.escape(insight.name)}</strong> (Score: {insight.composite:.1f})<br/>"
                        f"<span style='color:#9ca3af;font-size:0.85rem;'>{html.escape(insight.reasoning)}</span></div>",
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
                    f"Factor-explained risk: {factor_report.total_factor_risk_pct:.1f}% · "
                    f"Idiosyncratic: {factor_report.idiosyncratic_risk_pct:.1f}% · "
                    f"Dominant: {factor_report.dominant_factor}"
                )

    if early_warnings:
        st.divider()
        with st.expander(
            "Early Warning Signals",
            expanded=early_warnings.overall_warning_level == "critical",
        ):
            st.caption(
                f"Overall level: **{early_warnings.overall_warning_level.upper()}** — {early_warnings.summary}"
            )
            if early_warnings.signals:
                for sig in early_warnings.signals:
                    with st.expander(
                        f"**{sig.name}** — {sig.severity.value.upper()}",
                        expanded=sig.severity.value == "critical",
                    ):
                        st.markdown(f"**{sig.description}**")
                        st.info(f"**Why:** {sig.reasoning}")
                        st.caption(f"**Suggested Action:** {sig.suggested_action}")
                        if sig.affected_holdings:
                            st.caption(f"Affected: {', '.join(sig.affected_holdings)}")
            else:
                st.success("No early-warning signals detected. Portfolio appears stable.")


def render_recommendations_tab(opt_result, rebalance, recommendations, risk_data, profile, report) -> None:
    """Tab 8: Recommendations - uses new RecommendationCard format."""

    render_optimization_section(
        opt_result,
        portfolio=report.portfolio,
        risk_data=risk_data,
        max_single_weight=profile.max_single_weight,
    )
    render_rebalance_section(rebalance, risk_data=risk_data)
    st.divider()

    # Handle both old RecommendationReport (with recommendations list) and new RecommendationCard format
    if recommendations:
        # Check if it's the new RecommendationCard format (has 'cards' attribute)
        if hasattr(recommendations, "cards"):
            cards = recommendations.cards
            priority_cards = (
                recommendations.priority_actions if hasattr(recommendations, "priority_actions") else []
            )
            summary = recommendations.summary if hasattr(recommendations, "summary") else ""
        else:
            # Old format - convert for compatibility
            cards = getattr(recommendations, "recommendations", [])
            priority_cards = getattr(recommendations, "priority_actions", [])
            summary = getattr(recommendations, "summary", "")

        st.subheader("Portfolio Action Recommendations")
        if summary:
            st.caption(summary)

        if priority_cards:
            st.markdown("**Priority Actions:**")
            for i, card in enumerate(priority_cards, 1):
                action_colors = {
                    "buy": "#22c55e",
                    "sell": "#ef4444",
                    "trim": "#f59e0b",
                    "hold": "#6b7280",
                    "block": "#a855f7",
                }
                color = action_colors.get(card.action.value, "#6b7280")
                st.markdown(
                    f"<div style='padding:0.75rem;margin:0.5rem 0;border-left:4px solid {color};"
                    f"background:rgba(255,255,255,0.03);border-radius:0 6px 6px 0;'>"
                    f"<strong>{i}. {card.action.value.upper()} {html.escape(', '.join(card.tickers)) if card.tickers else 'PORTFOLIO'}</strong> "
                    f"<span style='color:#9ca3af;'>{card.urgency.value}, confidence: {card.confidence:.0%}</span><br/>"
                    f"<span style='font-size:0.85rem;'>{html.escape(card.reason)}</span><br/>"
                    f"<span style='font-size:0.8rem;color:#f59e0b;'>Trade-off: {html.escape('; '.join(card.alternatives[:2])) if card.alternatives else 'See alternatives'}</span></div>",
                    unsafe_allow_html=True,
                )

        # Show total risk reduction
        total_risk_reduction = sum(c.net_risk_reduction_bps for c in cards) / 100
        if total_risk_reduction > 0:
            st.metric(
                "Total Risk Reduction Potential",
                f"{total_risk_reduction:.1f}%",
            )
            st.info(
                "Risk reduction is a directional estimate based on heuristic rules, "
                "not a backtested or simulated forecast."
            )

        st.divider()
        st.subheader("All Recommendations")

        for card in cards:
            action_colors = {
                "buy": "#22c55e",
                "sell": "#ef4444",
                "trim": "#f59e0b",
                "hold": "#6b7280",
                "block": "#a855f7",
            }
            color = action_colors.get(card.action.value, "#6b7280")

            with st.expander(
                f"**{card.action.value.upper()}** {', '.join(card.tickers) if card.tickers else 'PORTFOLIO'} — Urgency: {card.urgency.value}",
                expanded=card.urgency.value == "immediate",
            ):
                st.markdown(f"**Reasoning:** {card.reason}")

                # Show rule verdicts
                if card.rule_verdicts:
                    st.caption("**Triggered Rules:**")
                    for verdict in card.rule_verdicts:
                        st.caption(f"• {verdict.rule_name}: {verdict.reason}")

                # Tax and impact breakdown
                if card.tax_breakdown:
                    total_tax = sum(card.tax_breakdown.values())
                    st.caption(f"**Estimated Tax Cost:** ₹{total_tax:,.0f}")

                if card.impact_breakdown:
                    total_impact = sum(card.impact_breakdown.values())
                    st.caption(f"**Estimated Impact Cost:** ₹{total_impact:,.0f}")

                st.caption(f"**Net Risk Reduction:** {card.net_risk_reduction_bps} bps")

                if card.alternatives:
                    st.caption(f"**Alternatives:** {'; '.join(card.alternatives[:3])}")

                st.caption(f"**Confidence:** {card.confidence:.0%}")

                # Guardrails
                if card.guardrails:
                    with st.expander("⚠️ Guardrails (Don't execute if...)", expanded=False):
                        for g in card.guardrails:
                            st.caption(f"• {g}")
    else:
        st.info("Recommendations require full analysis.")


def render_all_tabs(ctx: ComputeContext, report: AnalysisReport) -> None:
    """
    Render all 10 tabs using pre-computed context.

    Args:
        ctx: ComputeContext from engine.compute.compute_all
        report: AnalysisReport for rendering
    """
    render_metric_row(report.portfolio, report.risk)
    render_health_gauge(report)

    narrative = ctx.narrative

    # Per-stock risk data for explainability
    risk_data: dict = {}
    prices = ctx.prices
    portfolio_returns = ctx.portfolio_returns
    if prices is not None and not prices.empty:
        ann_vol = prices.pct_change().std() * np.sqrt(252)
        ticker_vols = (ann_vol * 100).to_dict()
        risk_data["volatility"] = ticker_vols
        risk_data["avg_volatility"] = sum(ticker_vols.values()) / len(ticker_vols) if ticker_vols else 0
    if ctx.raw_corr is not None and hasattr(ctx.raw_corr, "mean"):
        risk_data["avg_correlation"] = ctx.raw_corr.mean(axis=1).to_dict()
    if ctx.stock_betas:
        risk_data["beta"] = ctx.stock_betas
    if ctx.portfolio and ctx.portfolio.holdings:
        risk_data["sector"] = {h.ticker: h.sector for h in ctx.portfolio.holdings}
    if ctx.sector:
        risk_data["sector_allocation"] = ctx.sector.sector_allocation

    profile = RISK_PROFILES[ctx.risk_profile_key]

    tab_names = [
        "Risk Metrics",
        "Sector",
        "vs Nifty 50",
        "Charts",
        "Holdings",
        "Fundamentals",
        "News",
        "Scenarios",
        "Recommendations",
        "Export",
    ]
    tabs = st.tabs(tab_names)

    # ── Tab 0: Risk Metrics ──
    with tabs[0]:
        render_narrative_section(narrative)
        render_advanced_section(
            report.zscore,
            report.var_backtest,
            report.garch_var,
            report.pelve,
            report.optimization_advanced,
        )
        render_risk_cards(report.risk)
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(
                volatility_gauge(report.risk.volatility_annual),
                width="stretch",
                key="vol_gauge",
            )
        with col2:
            rv = rolling_volatility(portfolio_returns)
            if len(rv) > 0:
                with st.expander("Rolling 21-day Volatility", expanded=False):
                    st.line_chart(rv)

        st.divider()
        render_composition_metrics(report.portfolio)
        render_institutional_intelligence(report.institutional_scores, report.factor_report, report.warnings)

    # ── Tab 1: Sector ──
    with tabs[1]:
        render_sector_section(report.sector)
        st.plotly_chart(
            sector_treemap(report.sector.sector_allocation),
            width="stretch",
            key="sector_treemap",
        )

    # ── Tab 2: vs Nifty 50 ──
    with tabs[2]:
        if ctx.benchmark:
            render_benchmark_section(report.benchmark)
        else:
            st.info("Benchmark data is not available for the selected index.")
        # Only overlay the benchmark line when we actually have benchmark data,
        # otherwise the chart silently plots an empty (misleading) series.
        if ctx.benchmark_cum is not None and not ctx.benchmark_cum.empty:
            st.plotly_chart(
                benchmark_chart(ctx.portfolio_cum, ctx.benchmark_cum),
                width="stretch",
                key="benchmark_chart",
            )

    # ── Tab 3: Charts ──
    with tabs[3]:
        col1, col2 = st.columns(2)
        with col1:
            running_max = ctx.portfolio_cum.cummax()
            drawdown_series = (ctx.portfolio_cum - running_max) / running_max
            st.plotly_chart(
                drawdown_chart(drawdown_series),
                width="stretch",
                key="drawdown_chart",
            )
        with col2:
            corr = (
                ctx.raw_corr
                if not ctx.raw_corr.empty
                else (compute_correlation_matrix(prices) if not prices.empty else pd.DataFrame())
            )
            st.plotly_chart(
                correlation_heatmap(corr),
                width="stretch",
                key="corr_heatmap",
            )
        if ctx.denoised_corr is not None and not ctx.denoised_corr.empty:
            with st.expander("Denoised Correlation (Marchenko-Pastur)"):
                st.plotly_chart(
                    correlation_heatmap(ctx.denoised_corr),
                    width="stretch",
                    key="corr_denoised",
                )

        st.divider()
        render_monte_carlo_section(ctx.mc_result)
        if ctx.mc_paths is not None:
            st.plotly_chart(
                monte_carlo_chart(ctx.mc_paths, (5, 95)),
                width="stretch",
                key="mc_chart",
            )

    # ── Tab 4: Holdings ──
    with tabs[4]:
        render_stock_table(report.portfolio)
        st.divider()
        risk_attribution = compute_stock_risk_attribution(prices, ctx.weights, ctx.stock_betas)
        if not risk_attribution.empty:
            render_stock_risk_table(risk_attribution)

    # ── Tab 5: Fundamentals ──
    with tabs[5]:
        render_fundamentals_section(report.portfolio)

    # ── Tab 6: News ──
    with tabs[6]:
        render_news_section(report.portfolio)

    # ── Tab 7: Scenarios ──
    with tabs[7]:
        render_scenario_section(ctx.scenarios)
        st.divider()
        if ctx.macro_scenarios:
            st.subheader("Macro-Driven Stress Tests")
            st.caption("Sector-aware scenarios modeling real-world macro events with causal reasoning.")
            for scenario in ctx.macro_scenarios:
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
                            ]
                        )
                        st.dataframe(sector_df, width="stretch", hide_index=True)

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
        render_regime_section(ctx.regime_result)
        if ctx.regime_result:
            st.plotly_chart(
                regime_chart(portfolio_returns, ctx.regime_result.state_sequence),
                width="stretch",
                key="regime_chart",
            )

    # ── Tab 8: Recommendations ──
    with tabs[8]:
        render_recommendations_tab(
            ctx.opt_result,
            ctx.rebalance,
            report.recommendations,
            risk_data,
            profile,
            report,
        )

    # ── Tab 9: Export ──
    with tabs[9]:
        render_export_tab(
            report,
            ctx.mc_result,
            ctx.portfolio_cum,
            report.recommendations,
            risk_data,
        )

    render_disclaimer_footer()


def render_export_tab(report, mc_result, portfolio_cum, recommendations, risk_data) -> None:
    """Tab 9: Export."""
    render_export_section(
        report.portfolio,
        risk=report.risk,
        sector_data=report.sector.sector_allocation,
        mc_result=mc_result,
        portfolio_cum=portfolio_cum,
        recommendations=recommendations,
        risk_data=risk_data,
        benchmark=report.benchmark,
        factor_risk=report.factor_report,
        macro_drivers=report.macro_drivers,
        regime_result=report.regime,
        institutional_scores=report.institutional_scores,
        scenario_results=report.macro_scenarios,
        warning_report=report.warnings,
    )


def render_disclaimer_footer() -> None:
    """Permanent disclaimer + footer."""
    st.markdown(
        "<div style='padding:0.75rem 1rem;margin:1rem 0;background:rgba(245,158,11,0.08);"
        "border-left:4px solid #f59e0b;border-radius:0 6px 6px 0;font-size:0.85rem;' role='alert'>"
        "<strong>⚠️ Not financial advice.</strong> This tool provides portfolio risk analysis "
        "for educational and informational purposes only. Nothing on this platform constitutes "
        "investment advice or a solicitation to buy or sell securities. "
        "<strong>The creator is not a SEBI-registered investment advisor.</strong> "
        "All trading and investment decisions are solely your responsibility."
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<details style='font-size:0.85rem;color:#6b7280;'>"
        f"<summary style='cursor:pointer;font-weight:600;color:#f59e0b;display:flex;align-items:center;gap:0.4rem;'>"
        f"{icon_html(ALERT_TRIANGLE, size=14)} Detailed limitations"
        f"</summary>"
        f"<p><strong>Data accuracy.</strong> Data is sourced from third-party public APIs (yfinance, "
        "nselib) and may be delayed, incomplete, or inaccurate.</p>"
        f"<p><strong>Limitations you should know:</strong></p>"
        f"<ul>"
        f"<li><strong>Price data</strong> — yfinance free tier has 15-20 min delay.</li>"
        f"<li><strong>NSE data</strong> — nselib is an optional dependency.</li>"
        f"<li><strong>Risk metrics</strong> — VaR, CVaR, Monte Carlo assume normality.</li>"
        f"<li><strong>Beta</strong> — computed against a single benchmark index.</li>"
        f"<li><strong>Monte Carlo simulation</strong> — uses Geometric Brownian Motion.</li>"
        f"<li><strong>HMM regime detection</strong> — optional dependency (hmmlearn).</li>"
        f"<li><strong>Scenario analysis</strong> — estimated using stock beta × weight × market change.</li>"
        f"<li><strong>Delivery analysis</strong> — relies on nselib bhavcopy data (1-day lag).</li>"
        f"</ul>"
        f"<p><strong>No liability.</strong> Under no circumstances shall the creator be liable for any "
        "damages arising from your use of this tool.</p>"
        f"<p><strong>Past performance.</strong> Historical data does not guarantee future results.</p>"
        f"<p><strong>Use at your own risk.</strong> By using this tool, you accept these terms.</p>"
        f"<p style='font-size:0.75rem;color:#9ca3af;'>Last updated: June 2026</p>"
        f"</details>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="app-footer">'
        f'{icon_html(GITHUB)} Built by <a href="https://github.com/AshayK003">AshayK003</a> · '
        f"{icon_html(HEART)} "
        f'<a href="https://chai4.me/ashaykushwaha003">Support on Chai4Me</a>'
        f"</div>",
        unsafe_allow_html=True,
    )
