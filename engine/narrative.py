"""
Rule-based natural language narrative generator.

Generates plain-English portfolio summaries from computed risk metrics.
No LLM, no API calls, no hallucinations — purely threshold-driven templates.
Pure functions — zero IO, zero Streamlit imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine import (
    AnalysisReport,
    BenchmarkComparison,
    Portfolio,
    RiskMetrics,
    SectorExposure,
)


@dataclass
class NarrativeReport:
    """Structured plain-English narrative about a portfolio."""

    summary: str  # Top-level overview paragraph
    risk_assessment: str  # Volatility, VaR, Sharpe in context
    concentration: str  # Sector and stock concentration exposure
    benchmark_context: str  # Alpha, beta, tracking error vs benchmark
    key_concerns: list[str]  # Top concerns ranked, each a sentence
    overall_verdict: str  # Final "Low / Moderate / High" risk verdict


def generate_narrative(report: AnalysisReport) -> NarrativeReport:
    """Generate a plain-English narrative from an AnalysisReport."""
    risk = report.risk
    sector = report.sector
    benchmark = report.benchmark
    portfolio = report.portfolio

    summary = _build_summary(portfolio, risk)
    risk_assessment = _build_risk_assessment(risk)
    concentration = _build_concentration(sector, portfolio)
    benchmark_context = _build_benchmark_context(benchmark) if benchmark else "Benchmark comparison is not available."
    key_concerns = _build_key_concerns(risk, sector, benchmark, portfolio)
    overall_verdict = _build_overall_verdict(risk, sector)

    return NarrativeReport(
        summary=summary,
        risk_assessment=risk_assessment,
        concentration=concentration,
        benchmark_context=benchmark_context,
        key_concerns=key_concerns,
        overall_verdict=overall_verdict,
    )


# ── Threshold helpers (calibrated for Indian equity context) ──

def _vol_level(vol: float) -> str:
    if vol < 15:
        return "low"
    if vol < 25:
        return "moderate"
    return "high"


def _sharpe_level(s: float) -> str:
    if s < 0.5:
        return "poor"
    if s < 1.0:
        return "fair"
    if s < 2.0:
        return "good"
    return "excellent"


def _beta_level(b: float) -> str:
    if b < 0.7:
        return "defensive"
    if b < 1.3:
        return "market-like"
    return "aggressive"


def _var_level(v: float) -> str:
    if v > -2.0:
        return "low"
    if v > -4.0:
        return "moderate"
    return "high"


def _drawdown_level(dd: float) -> str:
    if dd > -10:
        return "mild"
    if dd > -20:
        return "moderate"
    return "severe"


def _diversification_level(score: float) -> str:
    if score < 30:
        return "poor"
    if score < 60:
        return "moderate"
    return "good"


# ── Section builders ──

def _build_summary(portfolio: Portfolio, risk: RiskMetrics) -> str:
    hc = portfolio.holding_count
    invested = portfolio.total_invested
    current = portfolio.total_current
    pnl = portfolio.total_pnl
    pnl_pct = portfolio.total_pnl_pct
    vol_level = _vol_level(risk.volatility_annual)

    total_str = f"Rs {current:,.0f}" if current >= 1e7 else f"Rs {current:,.0f}"
    pnl_str = f"up {pnl_pct:+.1f}%" if pnl >= 0 else f"down {pnl_pct:+.1f}%"

    return (
        f"Your portfolio of {hc} holding{'s' if hc != 1 else ''} "
        f"(valued at {total_str}) is {pnl_str} on your total investment of "
        f"Rs {invested:,.0f}. "
        f"The overall portfolio risk is **{vol_level.upper()}**, "
        f"with annualized volatility of {risk.volatility_annual:.1f}%."
    )


def _build_risk_assessment(risk: RiskMetrics) -> str:
    vol = risk.volatility_annual
    var95 = risk.var_95
    sharpe = risk.sharpe
    cagr = risk.cagr
    dd = risk.max_drawdown

    vol_lvl = _vol_level(vol)
    sharpe_lvl = _sharpe_level(sharpe)
    dd_lvl = _drawdown_level(dd)

    daily_move = vol / 16

    parts = [
        f"Volatility of {vol:.1f}% is **{vol_lvl}** — you can expect daily moves of around "
        f"\u00b1{daily_move:.1f}% in either direction.",
        f"Value at Risk (VaR 95%) is {var95:.2f}%, meaning there is a 5% chance your portfolio "
        f"could lose more than {abs(var95):.1f}% in a single day — this is **{_var_level(var95)}** tail risk.",
        f"The Sharpe ratio of {sharpe:.2f} is **{sharpe_lvl}**, indicating "
        + (
            "strong risk-adjusted returns relative to the risk-free rate."
            if sharpe_lvl in ("good", "excellent")
            else "that returns barely compensate for the risk taken."
            if sharpe_lvl == "poor"
            else "adequate risk-adjusted performance."
        ),
        f"The maximum drawdown of {dd:.1f}% is **{dd_lvl}** and occurred "
        f"between {risk.max_drawdown_start} and {risk.max_drawdown_end}.",
    ]

    if cagr > 0:
        parts.append(f"The CAGR (annualized return) is {cagr:.1f}% over the analysis period.")

    return " ".join(parts)


def _build_concentration(sector: SectorExposure, portfolio: Portfolio) -> str:
    alloc = sector.sector_allocation
    div_score = sector.diversification_score
    div_lvl = _diversification_level(div_score)
    hhi = sector.herfindahl_index

    if not alloc:
        return "Sector data is not available for this portfolio."

    # Top 2 sectors by allocation
    sorted_sectors = sorted(alloc.items(), key=lambda x: x[1], reverse=True)
    top1 = f"{sorted_sectors[0][0]} ({sorted_sectors[0][1]:.0f}%)" if len(sorted_sectors) >= 1 else ""
    top2 = f"{sorted_sectors[1][0]} ({sorted_sectors[1][1]:.0f}%)" if len(sorted_sectors) >= 2 else ""

    # Top stock weight
    total = portfolio.total_current
    top_stock = max(portfolio.holdings, key=lambda h: h.current_value) if portfolio.holdings else None
    top_weight = (top_stock.current_value / total * 100) if top_stock and total > 0 else 0

    parts = [
        f"Diversification is **{div_lvl}** (score: {div_score:.0f}/100, Herfindahl index: {hhi:.3f}).",
    ]

    if top1:
        parts.append(f"The largest sector exposure is {top1}.")
    if top2:
        parts.append(f"The second-largest is {top2}.")
    if top_weight > 20:
        parts.append(
            f"Single-stock concentration is notable: **{top_stock.ticker.replace('.NS', '')}** "
            f"alone makes up {top_weight:.0f}% of your portfolio."
        )

    if sector.concentrated_sectors:
        concat = ", ".join(sector.concentrated_sectors)
        parts.append(
            f"Concentration risk detected in: {concat}. "
            f"Consider spreading across more sectors to reduce idiosyncratic risk."
        )

    return " ".join(parts)


def _build_benchmark_context(benchmark: BenchmarkComparison) -> str:
    alpha = benchmark.alpha
    beta = benchmark.beta
    te = benchmark.tracking_error
    ir = benchmark.information_ratio
    port_ret = benchmark.portfolio_return
    bm_ret = benchmark.benchmark_return
    outperf = benchmark.outperformance_months
    total_m = benchmark.total_months

    beta_lvl = _beta_level(beta)

    alpha_str = f"outperformed" if alpha >= 0 else f"underperformed"

    parts = [
        f"Your portfolio returned {port_ret:.1f}% vs the benchmark's {bm_ret:.1f}%, "
        f"a **{alpha_str}ance of {abs(alpha):.1f}%**.",
        f"Beta of {beta:.2f} is **{beta_lvl}** — "
        + (
            f"the portfolio moves {((beta - 1) * 100):.0f}% more than the market on average."
            if beta > 1.3
            else "the portfolio moves in line with the market."
            if 0.7 <= beta <= 1.3
            else "the portfolio is less sensitive to market movements than average."
        ),
    ]

    if te > 0:
        parts.append(f"Tracking error of {te:.1f}% indicates the portfolio's return pattern "
                      f"deviates {'significantly' if te > 8 else 'moderately' if te > 4 else 'modestly'} from the benchmark.")

    if total_m > 0:
        win_rate = outperf / total_m * 100
        parts.append(
            f"The portfolio beat the benchmark in {outperf} of {total_m} months "
            f"({win_rate:.0f}% win rate)."
        )

    return " ".join(parts)


def _build_key_concerns(
    risk: RiskMetrics,
    sector: SectorExposure,
    benchmark: BenchmarkComparison | None,
    portfolio: Portfolio,
) -> list[str]:
    concerns = []

    # 1. Volatility
    vol_lvl = _vol_level(risk.volatility_annual)
    if vol_lvl == "high":
        concerns.append(
            f"High volatility ({risk.volatility_annual:.1f}%) means sharp portfolio swings. "
            "Consider adding defensive or low-beta holdings as ballast."
        )
    elif vol_lvl == "moderate" and risk.sharpe < 1.0:
        concerns.append(
            f"Moderate volatility ({risk.volatility_annual:.1f}%) combined with a low Sharpe ratio "
            f"({risk.sharpe:.2f}) suggests you are taking risk without proportional returns."
        )

    # 2. Drawdown
    dd_lvl = _drawdown_level(risk.max_drawdown)
    if dd_lvl == "severe":
        concerns.append(
            f"Maximum drawdown of {risk.max_drawdown:.1f}% is severe — "
            "review stop-loss discipline and hedge adequacy."
        )

    # 3. VaR
    var_lvl = _var_level(risk.var_95)
    if var_lvl == "high":
        concerns.append(
            f"VaR of {risk.var_95:.2f}% means a 1-in-20 day loss could exceed "
            f"Rs {abs(risk.var_95 / 100) * portfolio.total_current:,.0f}. "
            "Consider reducing position sizes of high-volatility holdings."
        )

    # 4. Sharpe
    if risk.sharpe < 0.5:
        concerns.append(
            f"The Sharpe ratio of {risk.sharpe:.2f} is poor — the portfolio barely compensates for risk. "
            "Review asset allocation and consider cost optimization."
        )

    # 5. Sector concentration
    if sector.concentrated_sectors:
        top_conc = sector.concentrated_sectors[0]
        top_pct = sector.sector_allocation.get(top_conc, 0)
        concerns.append(
            f"**{top_conc}** is {top_pct:.0f}% of your portfolio — high single-sector dependency. "
            f"A sector-specific downturn would disproportionately impact your returns."
        )

    # 6. Single-stock concentration
    total = portfolio.total_current
    top_stock = max(portfolio.holdings, key=lambda h: h.current_value) if portfolio.holdings else None
    top_weight = (top_stock.current_value / total * 100) if top_stock and total > 0 else 0
    if top_weight > 30:
        concerns.append(
            f"**{top_stock.ticker.replace('.NS', '')}** alone is {top_weight:.0f}% of your portfolio. "
            f"Any stock-specific event could have an outsized impact."
        )

    # 7. Benchmark underperformance
    if benchmark and benchmark.alpha < -5:
        concerns.append(
            f"Significant underperformance (alpha of {benchmark.alpha:.1f}%) versus the benchmark. "
            f"Compare sector weights and check if fees or cash drag explain the gap."
        )

    # 8. Correlation risk (if available)
    if risk.correlation_to_benchmark > 0.95:
        concerns.append(
            f"Extremely high correlation ({risk.correlation_to_benchmark:.2f}) to the benchmark "
            f"implies the portfolio offers limited diversification from index investing."
        )

    return concerns[:5]  # Cap at top 5 concerns


def _build_overall_verdict(risk: RiskMetrics, sector: SectorExposure) -> str:
    vol_lvl = _vol_level(risk.volatility_annual)
    sharpe = risk.sharpe
    dd_lvl = _drawdown_level(risk.max_drawdown)
    div_lvl = _diversification_level(sector.diversification_score)

    score = 0
    score += 0 if vol_lvl == "low" else 1 if vol_lvl == "moderate" else 2
    score += 0 if sharpe >= 1.0 else 1 if sharpe >= 0.5 else 2
    score += 0 if dd_lvl == "mild" else 1 if dd_lvl == "moderate" else 2
    score += 0 if div_lvl == "good" else 1 if div_lvl == "moderate" else 2

    if score <= 2:
        verdict = "Low Risk"
        detail = "The portfolio shows healthy diversification, controlled volatility, and adequate risk-adjusted returns."
    elif score <= 4:
        verdict = "Moderate Risk"
        detail = "Some areas need attention — review the concerns above, particularly around concentration and drawdown exposure."
    else:
        verdict = "Higher Risk"
        detail = "Multiple risk factors are elevated. A systematic review of position sizing, sector allocation, and hedge coverage is recommended."

    return f"**{verdict}.** {detail}"
