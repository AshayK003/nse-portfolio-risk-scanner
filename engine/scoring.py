"""
Institutional Risk Scoring engine.

Computes composite scores using Probability × Impact × Confidence framework.
Synthesizes all risk dimensions into actionable institutional-grade scores.
Pure functions — zero IO, zero Streamlit imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine.risk import RiskMetrics


@dataclass
class RiskScore:
    """A single scored risk with probability, impact, confidence, and reasoning."""

    name: str
    probability: float  # 0-1: likelihood of materialization
    impact: float  # 0-1: severity if it materializes
    confidence: float  # 0-1: how confident we are in this assessment
    composite: float  # P × I × C, normalized to 0-100
    reasoning: str  # causal explanation
    category: str  # "systematic", "idiosyncratic", "structural", "tail"


@dataclass
class InstitutionalRiskScores:
    """The five institutional-grade composite scores."""

    overall_risk_score: float  # 0-100, higher = riskier
    conviction_score: float  # 0-100, higher = more conviction in holdings
    portfolio_stress_score: float  # 0-100, higher = more stressed
    hidden_correlation_score: float  # 0-100, higher = more hidden correlations
    tail_risk_score: float  # 0-100, higher = more tail risk

    # Component breakdowns
    risk_factors: list[RiskScore] = field(default_factory=list)
    top_5_insights: list[RiskScore] = field(default_factory=list)
    score_interpretation: str = ""


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _score_volatility_risk(vol: float) -> RiskScore:
    """Score risk from portfolio volatility."""
    # Normalized: 15% vol = 0.5, 30% = 0.8, 5% = 0.2
    prob = _clamp(vol / 0.40)
    impact = _clamp(vol / 0.30)
    confidence = 0.9  # volatility is well-estimated from history
    composite = prob * impact * confidence * 100
    return RiskScore(
        name="Volatility Risk",
        probability=round(prob, 3),
        impact=round(impact, 3),
        confidence=round(confidence, 3),
        composite=round(composite, 1),
        reasoning=f"Portfolio annualized volatility is {vol:.1%}. "
        f"{'This is significantly above the typical Indian equity range of 15-20%, indicating elevated risk of large daily swings.' if vol > 0.25 else 'Within the normal range for an Indian equity portfolio.' if vol > 0.15 else 'Low volatility suggests defensive holdings or low beta stocks.'}",
        category="systematic",
    )


def _score_var_risk(var_95: float, var_99: float) -> RiskScore:
    """Score risk from Value at Risk."""
    # var_95 is negative (loss); normalize: -3% = 0.5, -5% = 0.8
    abs_var = abs(var_95)
    prob = _clamp(abs_var / 0.05)
    impact = _clamp(abs_var / 0.04)
    confidence = 0.85  # VaR is model-dependent
    composite = prob * impact * confidence * 100
    return RiskScore(
        name="Value at Risk",
        probability=round(prob, 3),
        impact=round(impact, 3),
        confidence=round(confidence, 3),
        composite=round(composite, 1),
        reasoning=f"Daily VaR(95%) is {var_95:.2f}%, meaning there's a 5% chance of losing more than {abs_var:.2f}% in a single day. "
        f"CVaR (expected shortfall beyond VaR) captures tail losses. "
        f"{'VaR is elevated — tail hedging should be considered.' if abs_var > 0.03 else 'VaR is within acceptable bounds for an equity portfolio.'}",
        category="tail",
    )


def _score_drawdown_risk(max_dd: float) -> RiskScore:
    """Score risk from maximum drawdown."""
    abs_dd = abs(max_dd)
    prob = _clamp(abs_dd / 0.30)
    impact = _clamp(abs_dd / 0.25)
    confidence = 0.95  # drawdown is directly observed
    composite = prob * impact * confidence * 100
    return RiskScore(
        name="Drawdown Risk",
        probability=round(prob, 3),
        impact=round(impact, 3),
        confidence=round(confidence, 3),
        composite=round(composite, 1),
        reasoning=f"Maximum observed drawdown is {max_dd:.1f}%. "
        f"{'This is a severe drawdown indicating significant capital at risk.' if abs_dd > 0.20 else 'Within the typical range for Indian equity portfolios.' if abs_dd > 0.10 else 'Modest drawdown suggests good risk management.'}",
        category="systematic",
    )


def _score_concentration_risk(sector_allocation: dict[str, float], weights: list[float]) -> RiskScore:
    """Score risk from portfolio concentration."""
    # Herfindahl of weights
    w = np.array(weights, dtype=float)
    hhi = float(np.sum(w**2))
    max_sector = max(sector_allocation.values()) if sector_allocation else 0
    max_stock = max(weights) if weights else 0

    prob = _clamp(max(max_sector / 40, max_stock / 30, hhi * 5))
    impact = _clamp(max_sector / 35)
    confidence = 0.9
    composite = prob * impact * confidence * 100
    return RiskScore(
        name="Concentration Risk",
        probability=round(prob, 3),
        impact=round(impact, 3),
        confidence=round(confidence, 3),
        composite=round(composite, 1),
        reasoning=f"Largest sector allocation is {max_sector:.1f}%, largest single holding is {max_stock * 100:.1f}%. "
        f"HHI (weight concentration) is {hhi:.4f}. "
        f"{'High concentration means a single sector or stock shock can devastate the portfolio.' if max_sector > 30 else 'Concentration is within acceptable bounds.'}",
        category="idiosyncratic",
    )


def _score_beta_risk(beta: float) -> RiskScore:
    """Score risk from market beta."""
    abs_dev = abs(beta - 1.0)
    prob = _clamp(abs_dev / 0.5)
    impact = _clamp(beta / 1.5) if beta > 1 else _clamp((2 - beta) / 2)
    confidence = 0.85
    composite = prob * impact * confidence * 100
    return RiskScore(
        name="Market Sensitivity (Beta)",
        probability=round(prob, 3),
        impact=round(impact, 3),
        confidence=round(confidence, 3),
        composite=round(composite, 1),
        reasoning=f"Portfolio beta is {beta:.2f}. "
        f"{'Beta significantly above 1 means amplified losses during market selloffs.' if beta > 1.2 else 'Beta below 1 provides some downside protection.' if beta < 0.8 else 'Beta near 1 means market-like risk exposure.'}",
        category="systematic",
    )


def _score_sharpe_risk(sharpe: float) -> RiskScore:
    """Score risk from risk-adjusted returns (low Sharpe = higher risk-adjusted risk)."""
    # Sharpe < 0.5 is concerning, > 1.5 is excellent
    prob = _clamp(1.0 - sharpe / 2.0)
    impact = _clamp(1.0 - sharpe / 1.5)
    confidence = 0.8
    composite = prob * impact * confidence * 100
    return RiskScore(
        name="Risk-Adjusted Return Quality",
        probability=round(prob, 3),
        impact=round(impact, 3),
        confidence=round(confidence, 3),
        composite=round(composite, 1),
        reasoning=f"Sharpe ratio is {sharpe:.2f}. "
        f"{'Poor risk-adjusted returns — the portfolio is not being compensated for the risk taken.' if sharpe < 0.5 else 'Good risk-adjusted returns.' if sharpe > 1.0 else 'Moderate risk-adjusted returns.'}",
        category="idiosyncratic",
    )


def _score_hidden_correlation(corr_matrix: pd.DataFrame, weights: list[float]) -> RiskScore:
    """
    Score hidden correlation risk.

    Detects when holdings that appear diversified are actually correlated,
    reducing the effective diversification benefit.
    """
    if corr_matrix.empty or len(weights) < 2:
        return RiskScore(
            name="Hidden Correlation Risk",
            probability=0.0,
            impact=0.0,
            confidence=0.0,
            composite=0.0,
            reasoning="Insufficient data for correlation analysis.",
            category="structural",
        )

    w = np.array(weights, dtype=float)
    if abs(w.sum() - 1.0) > 0.01:
        w = w / w.sum()

    # Average pairwise correlation
    n = corr_matrix.shape[0]
    mask = np.triu(np.ones((n, n), dtype=bool), k=1)
    upper_vals = corr_matrix.values[mask]
    avg_corr = float(np.nanmean(upper_vals))

    # High-correlation pairs (>0.7)
    high_corr_pairs = 0
    total_pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            total_pairs += 1
            if abs(corr_matrix.iloc[i, j]) > 0.7:
                high_corr_pairs += 1

    high_corr_pct = high_corr_pairs / total_pairs if total_pairs > 0 else 0

    # Effective diversification: how much diversification is actually achieved
    portfolio_var = float(w @ corr_matrix.values @ w)
    idio_var = float(np.sum(w**2))
    diversification_ratio = portfolio_var / idio_var if idio_var > 0 else 1.0

    # Score: high avg correlation + many high-corr pairs = high hidden risk
    prob = _clamp(avg_corr * 1.5 + high_corr_pct)
    impact = _clamp(diversification_ratio / 2.0)
    confidence = 0.8
    composite = prob * impact * confidence * 100

    return RiskScore(
        name="Hidden Correlation Risk",
        probability=round(prob, 3),
        impact=round(impact, 3),
        confidence=round(confidence, 3),
        composite=round(composite, 1),
        reasoning=f"Average pairwise correlation is {avg_corr:.2f}. {high_corr_pairs}/{total_pairs} pairs have correlation >0.7. "
        f"Diversification ratio is {diversification_ratio:.2f}x (1.0 = perfect diversification). "
        f"{'Holdings are more correlated than they appear — diversification benefit is overstated.' if avg_corr > 0.5 else 'Good diversification with low cross-correlations.' if avg_corr < 0.2 else 'Moderate correlation across holdings.'}",
        category="structural",
    )


def _score_tail_risk(cvar_95: float, var_95: float, var_99: float) -> RiskScore:
    """Score tail risk from CVaR and VaR spread."""
    abs_cvar = abs(cvar_95)
    abs_var95 = abs(var_95)
    abs_var99 = abs(var_99)

    # CVaR/VaR ratio: higher = fatter tails
    tail_ratio = abs_cvar / abs_var95 if abs_var95 > 0 else 1.0
    # VaR99/Va95 ratio: higher = more extreme tail
    extreme_ratio = abs_var99 / abs_var95 if abs_var95 > 0 else 1.0

    prob = _clamp(abs_cvar / 0.05)
    impact = _clamp(tail_ratio / 2.0)
    confidence = 0.75  # tail estimates are inherently uncertain
    composite = prob * impact * confidence * 100

    return RiskScore(
        name="Tail Risk (Extreme Losses)",
        probability=round(prob, 3),
        impact=round(impact, 3),
        confidence=round(confidence, 3),
        composite=round(composite, 1),
        reasoning=f"CVaR(95%) is {cvar_95:.2f}%, meaning average loss in the worst 5% of days. "
        f"Tail ratio (CVaR/VaR) is {tail_ratio:.2f} — {'fat tails indicate risk of extreme losses beyond what VaR suggests.' if tail_ratio > 1.5 else 'tails are relatively well-behaved.'} "
        f"{'VaR99/VaR95 ratio of ' + f'{extreme_ratio:.2f} confirms elevated extreme-tail risk.' if extreme_ratio > 1.8 else ''}",
        category="tail",
    )


def _score_momentum_risk(prices: pd.DataFrame, weights: list[float]) -> RiskScore:
    """Score risk from momentum breakdown."""
    if prices.empty or len(weights) < 2:
        return RiskScore(
            name="Momentum Breakdown Risk",
            probability=0.0,
            impact=0.0,
            confidence=0.0,
            composite=0.0,
            reasoning="Insufficient data for momentum analysis.",
            category="systematic",
        )

    returns = prices.pct_change().dropna()
    if returns.empty or len(returns) < 63:
        return RiskScore(
            name="Momentum Breakdown Risk",
            probability=0.0,
            impact=0.0,
            confidence=0.0,
            composite=0.0,
            reasoning="Insufficient history for momentum analysis.",
            category="systematic",
        )

    w = np.array(weights, dtype=float)
    if abs(w.sum() - 1.0) > 0.01:
        w = w / w.sum()

    # Short-term vs long-term momentum divergence
    short_mom = (1 + returns.iloc[-21:]).prod() - 1  # 1-month
    long_mom = (
        (1 + returns.iloc[-252:]).prod() - 1 if len(returns) >= 252 else (1 + returns).prod() - 1
    )  # 1-year
    portfolio_mom = float(np.dot(w, short_mom.values)) if len(short_mom) > 0 else 0
    portfolio_long_mom = float(np.dot(w, long_mom.values)) if len(long_mom) > 0 else 0

    # Divergence: short-term down while long-term up = momentum breakdown
    divergence = abs(portfolio_mom - portfolio_long_mom)
    prob = _clamp(divergence * 5)
    impact = _clamp(abs(portfolio_mom) * 10)
    confidence = 0.7
    composite = prob * impact * confidence * 100

    return RiskScore(
        name="Momentum Breakdown Risk",
        probability=round(prob, 3),
        impact=round(impact, 3),
        confidence=round(confidence, 3),
        composite=round(composite, 1),
        reasoning=f"1-month momentum: {portfolio_mom:.1%}, 1-year: {portfolio_long_mom:.1%}. "
        f"{'Significant divergence suggests momentum is breaking down — potential trend reversal.' if divergence > 0.1 else 'Short and long-term momentum are aligned.' if divergence < 0.03 else 'Minor momentum divergence — monitor closely.'}",
        category="systematic",
    )


def compute_institutional_scores(
    risk: RiskMetrics,
    prices: pd.DataFrame,
    weights: list[float],
    sector_allocation: dict[str, float],
    corr_matrix: pd.DataFrame | None = None,
) -> InstitutionalRiskScores:
    """
    Compute all five institutional risk scores.

    Synthesizes volatility, VaR, drawdown, concentration, beta, Sharpe,
    hidden correlation, tail risk, and momentum into composite scores.

    Args:
        risk: Computed RiskMetrics
        prices: Daily closing prices
        weights: Portfolio weights
        sector_allocation: Sector name -> % allocation
        corr_matrix: Correlation matrix (optional, computed if not provided)

    Returns:
        InstitutionalRiskScores with all five composite scores
    """
    if risk.volatility_annual == 0 and risk.var_95 == 0:
        return _empty_scores()

    # Compute individual risk scores
    risk_factors = [
        _score_volatility_risk(risk.volatility_annual / 100),
        _score_var_risk(risk.var_95 / 100, risk.var_99 / 100),
        _score_drawdown_risk(risk.max_drawdown / 100),
        _score_concentration_risk(sector_allocation, weights),
        _score_beta_risk(risk.beta),
        _score_sharpe_risk(risk.sharpe),
        _score_tail_risk(risk.cvar_95 / 100, risk.var_95 / 100, risk.var_99 / 100),
        _score_momentum_risk(prices, weights),
    ]

    if corr_matrix is None and not prices.empty:
        corr_matrix = prices.pct_change().dropna().corr()

    hidden_corr = _score_hidden_correlation(
        corr_matrix if corr_matrix is not None else pd.DataFrame(), weights
    )
    risk_factors.append(hidden_corr)

    # ── Compute composite scores ──

    # Overall Risk Score: weighted average of all risk factors
    weights_for_composite = {
        "Volatility Risk": 0.15,
        "Value at Risk": 0.12,
        "Drawdown Risk": 0.12,
        "Concentration Risk": 0.12,
        "Market Sensitivity (Beta)": 0.10,
        "Risk-Adjusted Return Quality": 0.10,
        "Tail Risk (Extreme Losses)": 0.12,
        "Momentum Breakdown Risk": 0.08,
        "Hidden Correlation Risk": 0.09,
    }
    overall_risk = sum(f.composite * weights_for_composite.get(f.name, 0.1) for f in risk_factors)
    overall_risk = _clamp(overall_risk, 0, 100)

    # Conviction Score: inverse of risk (higher risk = lower conviction)
    # Adjusted by Sharpe (good risk-adjusted returns = higher conviction)
    conviction = max(0, 100 - overall_risk)
    if risk.sharpe > 1.0:
        conviction = min(100, conviction * 1.15)
    elif risk.sharpe < 0.3:
        conviction = conviction * 0.8
    conviction = _clamp(conviction, 0, 100)

    # Portfolio Stress Score: combination of vol regime, drawdown, and VaR
    stress_components = [
        _clamp(risk.volatility_annual / 30) * 30,  # 30% weight
        _clamp(abs(risk.max_drawdown) / 25) * 30,  # 30% weight
        _clamp(abs(risk.var_95) / 0.04) * 25,  # 25% weight
        _clamp(abs(risk.cvar_95) / 0.05) * 15,  # 15% weight
    ]
    stress_score = _clamp(sum(stress_components), 0, 100)

    # Hidden Correlation Score
    hidden_corr_score = hidden_corr.composite

    # Tail Risk Score
    tail_risk = _score_tail_risk(risk.cvar_95 / 100, risk.var_95 / 100, risk.var_99 / 100)
    tail_risk_score = tail_risk.composite

    # Top 5 insights (sorted by composite score, descending)
    all_risks = sorted(risk_factors, key=lambda f: f.composite, reverse=True)
    top_5 = all_risks[:5]

    # Score interpretation
    interpretation = _interpret_scores(
        overall_risk, conviction, stress_score, hidden_corr_score, tail_risk_score
    )

    return InstitutionalRiskScores(
        overall_risk_score=round(overall_risk, 1),
        conviction_score=round(conviction, 1),
        portfolio_stress_score=round(stress_score, 1),
        hidden_correlation_score=round(hidden_corr_score, 1),
        tail_risk_score=round(tail_risk_score, 1),
        risk_factors=risk_factors,
        top_5_insights=top_5,
        score_interpretation=interpretation,
    )


def _interpret_scores(
    overall: float, conviction: float, stress: float, hidden_corr: float, tail: float
) -> str:
    """Generate a human-readable interpretation of the composite scores."""
    parts = []

    if overall > 70:
        parts.append(
            "HIGH RISK: Portfolio carries significant institutional-level risk across multiple dimensions."
        )
    elif overall > 45:
        parts.append(
            "MODERATE RISK: Portfolio risk is within manageable bounds but has areas requiring attention."
        )
    else:
        parts.append("LOW RISK: Portfolio is well-positioned with conservative risk characteristics.")

    if stress > 60:
        parts.append(
            "Portfolio is under elevated stress — current market conditions are adverse for this positioning."
        )
    if hidden_corr > 50:
        parts.append(
            "Hidden correlations are reducing effective diversification — the portfolio is less diversified than it appears."
        )
    if tail > 50:
        parts.append("Tail risk is elevated — extreme loss scenarios deserve hedging consideration.")
    if conviction < 30:
        parts.append("Low conviction — risk-adjusted returns do not justify the current risk level.")

    return " ".join(parts)


def _empty_scores() -> InstitutionalRiskScores:
    return InstitutionalRiskScores(
        overall_risk_score=0.0,
        conviction_score=0.0,
        portfolio_stress_score=0.0,
        hidden_correlation_score=0.0,
        tail_risk_score=0.0,
        risk_factors=[],
        top_5_insights=[],
        score_interpretation="Insufficient data for scoring.",
    )
