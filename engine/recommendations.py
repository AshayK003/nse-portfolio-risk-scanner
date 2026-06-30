"""
Portfolio recommendations engine.

Generates actionable recommendations with causal reasoning based on
the full risk analysis. Each recommendation includes expected risk
reduction and trade-offs.
Pure functions — zero IO, zero Streamlit imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionType(str, Enum):
    REDUCE = "reduce"
    HEDGE = "hedge"
    DIVERSIFY = "diversify"
    ACCUMULATE = "accumulate"
    MONITOR = "monitor"
    REBALANCE = "rebalance"


@dataclass
class Recommendation:
    """A single portfolio action recommendation."""

    action: ActionType
    target: str  # ticker, sector, or "PORTFOLIO"
    urgency: str  # "immediate", "near-term", "monitor"
    confidence: float  # 0-1
    expected_risk_reduction: float  # estimated % reduction in portfolio risk
    reasoning: str  # causal chain
    trade_off: str  # what you give up by following this recommendation
    details: str = ""  # specific guidance


@dataclass
class RecommendationReport:
    """Complete set of portfolio recommendations."""

    recommendations: list[Recommendation]
    summary: str  # one-paragraph executive summary
    priority_actions: list[Recommendation]  # top 3 immediate actions
    risk_reduction_potential: float  # total estimated risk reduction if all followed


def _rank_by_urgency(recs: list[Recommendation]) -> list[Recommendation]:
    urgency_order = {"immediate": 0, "near-term": 1, "monitor": 2}
    return sorted(recs, key=lambda r: (urgency_order.get(r.urgency, 3), -r.confidence))


def generate_recommendations(
    risk,
    sector,
    benchmark,
    portfolio,
    factor_report=None,
    institutional_scores=None,
    macro_drivers=None,
    corr_matrix=None,
    regime_result=None,
) -> RecommendationReport:
    """
    Generate actionable portfolio recommendations based on the full analysis.

    Uses causal reasoning: each recommendation traces back to a specific
    risk factor and explains why the action helps and what trade-off it entails.
    """
    recs = []

    # ── Concentration risk → Diversify / Reduce ──
    if sector.concentrated_sectors:
        for sec in sector.concentrated_sectors:
            sec_pct = sector.sector_allocation.get(sec, 0)
            recs.append(
                Recommendation(
                    action=ActionType.REDUCE if sec_pct > 35 else ActionType.DIVERSIFY,
                    target=sec,
                    urgency="immediate" if sec_pct > 40 else "near-term",
                    confidence=0.85,
                    expected_risk_reduction=round(sec_pct * 0.08, 1),
                    reasoning=f"{sec} occupies {sec_pct:.1f}% of your portfolio, well above the 20% prudent limit. "
                    f"A single adverse sector event (regulatory change, earnings miss, commodity shock) "
                    f"could erase {sec_pct:.0f}%+ of portfolio value in days.",
                    trade_off=f"Reducing {sec} exposure may sacrifice short-term upside if the sector rallies, "
                    f"but protects against concentrated drawdown risk.",
                    details=f"Consider reducing {sec} allocation from {sec_pct:.1f}% to 15-20% and redeploying to "
                    f"uncorrelated sectors.",
                )
            )

    # ── High beta → Hedge / Reduce ──
    if risk.beta > 1.3:
        recs.append(
            Recommendation(
                action=ActionType.HEDGE,
                target="PORTFOLIO",
                urgency="near-term",
                confidence=0.8,
                expected_risk_reduction=round((risk.beta - 1.0) * 5, 1),
                reasoning=f"Portfolio beta of {risk.beta:.2f} means amplified losses during market selloffs. "
                f"In a 10% market crash, this portfolio would lose ~{risk.beta * 10:.0f}% vs the market's 10%. "
                f"The excess loss compounds with drawdown duration and recovery time.",
                trade_off="Hedging (put options, index shorts) costs 1-3% annually in premium/roll costs and caps upside.",
                details="Consider buying Nifty 50 put options or adding low-beta defensive stocks (pharma, FMCG) to reduce effective beta toward 1.0.",
            )
        )
    elif risk.beta < 0.6:
        recs.append(
            Recommendation(
                action=ActionType.ACCUMULATE,
                target="PORTFOLIO",
                urgency="monitor",
                confidence=0.65,
                expected_risk_reduction=0.0,
                reasoning=f"Portfolio beta of {risk.beta:.2f} is unusually low. While this provides downside protection, "
                f"it also means the portfolio will significantly underperform in bull markets.",
                trade_off="Increasing beta improves upside capture but increases crash exposure.",
                details="Consider adding quality large-caps with beta 0.9-1.1 to participate in market upside.",
            )
        )

    # ── Poor risk-adjusted returns → Rebalance ──
    if risk.sharpe < 0.5:
        recs.append(
            Recommendation(
                action=ActionType.REBALANCE,
                target="PORTFOLIO",
                urgency="near-term",
                confidence=0.75,
                expected_risk_reduction=3.0,
                reasoning=f"Sharpe ratio of {risk.sharpe:.2f} indicates the portfolio is not being compensated "
                f"for the risk taken. For every unit of risk, you're getting {risk.sharpe:.2f} units of excess return. "
                f"Institutional portfolios target Sharpe > 1.0.",
                trade_off="Rebalancing may realize short-term capital gains and disrupt momentum in winning positions.",
                details="Consider shifting toward higher Sharpe-ratio holdings: quality companies with consistent "
                "earnings, reasonable valuations, and lower idiosyncratic risk.",
            )
        )

    # ── Deep drawdown → Monitor / Hedge ──
    if abs(risk.max_drawdown) > 20:
        recs.append(
            Recommendation(
                action=ActionType.MONITOR,
                target="PORTFOLIO",
                urgency="immediate" if abs(risk.max_drawdown) > 30 else "near-term",
                confidence=0.9,
                expected_risk_reduction=0.0,
                reasoning=f"Maximum drawdown of {risk.max_drawdown:.1f}% ({risk.max_drawdown_start} to {risk.max_drawdown_end}) "
                f"indicates the portfolio has experienced severe capital impairment. "
                f"Recovery from such drawdowns typically takes 6-18 months.",
                trade_off="Setting stop-losses or trailing stops may trigger premature exits during normal volatility.",
                details="Implement a 15-20% trailing stop-loss policy. Review positions that contributed most to the drawdown.",
            )
        )

    # ── High tail risk → Hedge ──
    if abs(risk.cvar_95) > 0.03:
        recs.append(
            Recommendation(
                action=ActionType.HEDGE,
                target="PORTFOLIO",
                urgency="near-term",
                confidence=0.75,
                expected_risk_reduction=round(abs(risk.cvar_95) * 10, 1),
                reasoning=f"CVaR(95%) of {risk.cvar_95:.2f}% means the average loss in the worst 5% of trading days "
                f"is significant. This tail risk is often underestimated by normal VaR models and can lead to "
                f"unexpectedly large losses during market dislocations.",
                trade_off="Tail risk hedging (deep OTM puts) has low probability of payoff but costs premium consistently.",
                details="Consider a 2-3% portfolio allocation to Nifty 50 put options with 5-10% out-of-the-money strike.",
            )
        )

    # ── Hidden correlation → Diversify ──
    if institutional_scores and institutional_scores.hidden_correlation_score > 50:
        recs.append(
            Recommendation(
                action=ActionType.DIVERSIFY,
                target="PORTFOLIO",
                urgency="near-term",
                confidence=0.7,
                expected_risk_reduction=round(institutional_scores.hidden_correlation_score * 0.05, 1),
                reasoning=f"Hidden correlation score of {institutional_scores.hidden_correlation_score:.0f}/100 indicates "
                f"holdings are more correlated than they appear. During stress events, correlations spike toward 1, "
                f"eliminating diversification benefits precisely when you need them most.",
                trade_off="True diversification requires holding assets that underperform during normal times.",
                details="Add uncorrelated asset classes: gold (GOLDBEES), international ETFs, or sectors with low correlation to current holdings.",
            )
        )

    # ── Macro driver risks ──
    if macro_drivers:
        for driver in macro_drivers:
            if driver.risk_level == "high":
                recs.append(
                    Recommendation(
                        action=ActionType.HEDGE,
                        target=driver.name,
                        urgency="near-term",
                        confidence=0.7,
                        expected_risk_reduction=round(driver.sensitivity * 3, 1),
                        reasoning=driver.reasoning,
                        trade_off=f"Hedging {driver.name} exposure reduces risk but may limit upside if the macro environment improves.",
                        details=f"Consider reducing exposure to sectors most sensitive to {driver.name} movements.",
                    )
                )

    # ── Regime-based recommendations ──
    if regime_result and regime_result.state_sequence:
        recent_states = (
            regime_result.state_sequence[-20:]
            if len(regime_result.state_sequence) >= 20
            else regime_result.state_sequence
        )
        bear_days = sum(1 for s in recent_states if s == 2)  # state 2 = bear
        if bear_days > len(recent_states) * 0.5:
            recs.append(
                Recommendation(
                    action=ActionType.HEDGE,
                    target="PORTFOLIO",
                    urgency="immediate",
                    confidence=0.75,
                    expected_risk_reduction=5.0,
                    reasoning=f"HMM regime detection shows {bear_days}/{len(recent_states)} recent trading days in bear regime. "
                    f"The market environment has shifted to risk-off. Historical bear regimes show 2-3x higher volatility.",
                    trade_off="Defensive positioning may miss sharp reversals which are common at regime transitions.",
                    details="Reduce equity exposure by 20-30%. Increase allocation to liquid beession or short-term debt.",
                )
            )

    # ── Single stock concentration ──
    if portfolio.holdings:
        max_weight = max(portfolio.weight)
        max_holding = max(portfolio.holdings, key=lambda h: h.current_value)
        if max_weight > 0.25:
            recs.append(
                Recommendation(
                    action=ActionType.REDUCE,
                    target=max_holding.ticker.replace(".NS", ""),
                    urgency="near-term" if max_weight > 0.35 else "monitor",
                    confidence=0.8,
                    expected_risk_reduction=round(max_weight * 4, 1),
                    reasoning=f"{max_holding.ticker.replace('.NS', '')} constitutes {max_weight * 100:.1f}% of the portfolio. "
                    f"Single-stock risk is the most controllable risk factor. A 50% drop in this stock "
                    f"would impair {max_weight * 50:.1f}% of total portfolio value.",
                    trade_off="Reducing a winning position may mean selling early and missing further upside.",
                    details=f"Consider reducing {max_holding.ticker.replace('.NS', '')} to 15-20% of portfolio and "
                    f"redistributing to 2-3 uncorrelated holdings.",
                )
            )

    # Sort and build report
    recs = _rank_by_urgency(recs)
    priority = [r for r in recs if r.urgency == "immediate"][:3]
    if len(priority) < 3:
        priority.extend([r for r in recs if r.urgency == "near-term"][: 3 - len(priority)])

    total_reduction = sum(r.expected_risk_reduction for r in recs)

    summary_parts = []
    if recs:
        summary_parts.append(f"Portfolio analysis identified {len(recs)} actionable recommendations.")
        if priority:
            summary_parts.append(
                f"{len(priority)} require immediate attention: "
                + ", ".join(f"{r.action.value} {r.target}" for r in priority[:3])
                + "."
            )
        summary_parts.append(
            f"Following all recommendations could reduce portfolio risk by approximately {total_reduction:.1f}%."
        )
    else:
        summary_parts.append(
            "Portfolio risk profile is within acceptable bounds. No immediate actions required."
        )

    return RecommendationReport(
        recommendations=recs,
        summary=" ".join(summary_parts),
        priority_actions=priority,
        risk_reduction_potential=round(total_reduction, 1),
    )
