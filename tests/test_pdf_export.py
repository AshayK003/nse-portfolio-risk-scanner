"""Tests for the self-contained PDF report generator (ui.pdf_reportlab).

The generator uses reportlab + matplotlib directly — no external pdf-studio
dependency — and applies the pdf-studio "ledger" theme (deep-green foundation,
gold accent, Lora headings, Inter body). These tests run regardless of whether
pdf-studio is installed.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from engine import Holding, Portfolio, RiskMetrics
from engine.risk import MonteCarloResult
from engine.recommendations.types import (
    ActionType,
    RecommendationCard,
    RecommendationReport,
    RegimeContext,
    Urgency,
)
from ui import pdf_reportlab as gen


def _sample_portfolio() -> Portfolio:
    holdings = [
        Holding(
            ticker="RELIANCE.NS",
            name="Reliance Industries",
            quantity=10,
            avg_price=2500,
            current_price=2800,
            sector="Oil & Gas",
        ),
        Holding(
            ticker="TCS.NS",
            name="Tata Consultancy Services",
            quantity=5,
            avg_price=3500,
            current_price=3800,
            sector="IT",
        ),
        Holding(
            ticker="HDFCBANK.NS",
            name="HDFC Bank",
            quantity=20,
            avg_price=1600,
            current_price=1700,
            sector="Banking",
        ),
    ]
    return Portfolio(holdings=holdings, name="Test Portfolio")


def _sample_risk_metrics() -> RiskMetrics:
    return RiskMetrics(
        volatility_annual=18.5,
        var_95=8.2,
        var_99=11.0,
        cvar_95=10.1,
        max_drawdown=-22.0,
        max_drawdown_start="2024-03-01",
        max_drawdown_end="2024-06-15",
        beta=0.92,
        correlation_to_benchmark=0.88,
        sharpe=1.05,
        sortino=1.6,
        cagr=14.2,
        total_return=28.0,
    )


def _sample_mc_result() -> MonteCarloResult:
    return MonteCarloResult(
        n_simulations=10000,
        horizon_days=252,
        expected_return=12.5,
        median_return=10.8,
        var_95=-15.2,
        var_99=-22.0,
        cvar_95=-18.0,
        prob_profit=72.0,
        ci_lower=-8.5,
        ci_upper=35.0,
    )


def _sample_portfolio_cum() -> pd.Series:
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=252, freq="B")
    returns = np.random.normal(0.0005, 0.015, 252)
    cum_values = np.cumprod(1 + returns)
    return pd.Series(cum_values, index=dates)


def _sample_sector_data() -> dict:
    return {"Banking": 45.0, "IT": 30.0, "Oil & Gas": 15.0, "Auto": 10.0}


def _sample_export_df(portfolio: Portfolio) -> pd.DataFrame:
    rows = []
    for h in portfolio.holdings:
        rows.append(
            {
                "Ticker": h.ticker.replace(".NS", ""),
                "Name": h.name,
                "Quantity": h.quantity,
                "Avg Price": h.avg_price,
                "Current Price": h.current_price,
                "Invested": h.invested_value,
                "Current Value": h.current_value,
                "P&L": h.pnl,
                "P&L %": h.pnl_pct,
                "Sector": h.sector,
            }
        )
    return pd.DataFrame(rows)


def _get_plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


# ── Chart figure tests (all return Figure objects) ──

def test_gauge():
    risk = _sample_risk_metrics()
    plt = _get_plt()
    result = gen._gauge(risk, plt)
    assert result is not None
    assert hasattr(result, "savefig")


def test_gauge_none_risk():
    plt = _get_plt()
    result = gen._gauge(None, plt)
    assert result is None


def test_gauge_none_plt():
    risk = _sample_risk_metrics()
    result = gen._gauge(risk, None)
    assert result is None


def test_cover_banner():
    portfolio = _sample_portfolio()
    plt = _get_plt()
    result = gen._cover_banner(portfolio, plt)
    assert result is not None
    assert hasattr(result, "savefig")


def test_cover_banner_none():
    portfolio = _sample_portfolio()
    result = gen._cover_banner(portfolio, None)
    assert result is None


def test_drawdown_chart():
    plt = _get_plt()
    cum = _sample_portfolio_cum()
    result = gen._drawdown_chart(cum, plt)
    assert result is not None
    assert hasattr(result, "savefig")


def test_monte_carlo_chart():
    plt = _get_plt()
    mc = _sample_mc_result()
    result = gen._monte_carlo_chart(mc, plt)
    assert result is not None
    assert hasattr(result, "savefig")


def test_sector_weight_composite():
    plt = _get_plt()
    portfolio = _sample_portfolio()
    sector_data = _sample_sector_data()
    result = gen._sector_weight_composite(sector_data, portfolio, plt)
    assert result is not None
    assert hasattr(result, "savefig")


def test_pnl_chart():
    plt = _get_plt()
    portfolio = _sample_portfolio()
    df = _sample_export_df(portfolio)
    result = gen._pnl_chart(df, plt)
    assert result is not None
    assert hasattr(result, "savefig")


def test_risk_assessment_low_vol():
    risk = _sample_risk_metrics()
    risk.volatility_annual = 12.0
    risk.sharpe = 1.5
    text, color = gen._risk_assessment_text(risk)
    assert "LOW" in text


def test_risk_assessment_high_vol():
    risk = _sample_risk_metrics()
    risk.volatility_annual = 35.0
    risk.sharpe = 0.3
    text, color = gen._risk_assessment_text(risk)
    assert "HIGH" in text


def test_risk_assessment_none():
    text, color = gen._risk_assessment_text(None)
    assert "not available" in text


# ── Full PDF generation tests ──

def test_generate_pdf_report_full():
    """Generate a full PDF with all sections; verify ledger theme applied."""
    portfolio = _sample_portfolio()
    risk = _sample_risk_metrics()
    sector_data = _sample_sector_data()
    df = _sample_export_df(portfolio)
    mc_result = _sample_mc_result()
    portfolio_cum = _sample_portfolio_cum()

    pdf_bytes = gen.generate_pdf_report(
        portfolio=portfolio,
        risk=risk,
        sector_data=sector_data,
        df=df,
        mc_result=mc_result,
        portfolio_cum=portfolio_cum,
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"
    # Embedded fonts confirm the ledger theme typography (Lora + Inter)
    assert len(pdf_bytes) > 5000


def test_generate_pdf_report_with_factor_macro_scenario():
    """Exercise the factor / macro / scenario PDF blocks with real engine objects.

    Regression guard: pages 6-7 read FactorRiskReport / MacroDriver /
    MacroScenarioResult fields directly. Earlier code referenced attributes
    that never existed on those dataclasses, so the PDF crashed at runtime
    unless real instances were passed — which the other tests never did.
    """
    from engine import FactorExposure, FactorRiskReport, MacroDriver
    from engine.scenario import run_macro_scenarios

    portfolio = _sample_portfolio()
    risk = _sample_risk_metrics()
    sector_data = _sample_sector_data()
    df = _sample_export_df(portfolio)
    mc_result = _sample_mc_result()
    portfolio_cum = _sample_portfolio_cum()

    factor_risk = FactorRiskReport(
        factors=[
            FactorExposure(
                name="Market",
                exposure=0.92,
                risk_contribution_pct=55.0,
                description="Broad market sensitivity.",
            ),
            FactorExposure(
                name="Momentum",
                exposure=0.31,
                risk_contribution_pct=20.0,
                description="Recent trend strength.",
            ),
        ],
        idiosyncratic_risk_pct=25.0,
        total_factor_risk_pct=75.0,
        dominant_factor="Market",
        diversification_by_factor={"Market": 0.6, "Momentum": 0.4},
    )

    macro_drivers = [
        MacroDriver(
            name="Crude Oil",
            sensitivity=0.12,
            current_regime="neutral",
            risk_level="medium",
            reasoning="Manageable oil exposure.",
        )
    ]

    betas = {h.ticker: 1.0 for h in portfolio.holdings}
    scenario_results = run_macro_scenarios(portfolio.holdings, betas)

    pdf_bytes = gen.generate_pdf_report(
        portfolio=portfolio,
        risk=risk,
        sector_data=sector_data,
        df=df,
        mc_result=mc_result,
        portfolio_cum=portfolio_cum,
        factor_risk=factor_risk,
        macro_drivers=macro_drivers,
        scenario_results=scenario_results,
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 5000


def test_generate_pdf_report_with_institutional_scores():
    """Exercise the institutional-scores PDF block with a real engine object.

    Regression guard: the block read quality/momentum/value/volatility/liquidity/
    esg/composite — none of which exist on InstitutionalRiskScores. It crashed at
    runtime unless a real instance was passed, which the other tests never did.
    """
    from engine.scoring import compute_institutional_scores

    portfolio = _sample_portfolio()
    risk = _sample_risk_metrics()
    sector_data = _sample_sector_data()
    df = _sample_export_df(portfolio)
    mc_result = _sample_mc_result()
    portfolio_cum = _sample_portfolio_cum()

    np.random.seed(7)
    dates = pd.date_range(end=datetime.now(), periods=60, freq="B")
    prices = pd.DataFrame(
        {h.ticker: np.random.normal(100, 2, 60).cumprod() for h in portfolio.holdings},
        index=dates,
    )
    weights = [1.0 / len(portfolio.holdings)] * len(portfolio.holdings)
    sector_alloc = {h.sector: 100.0 / len(portfolio.holdings) for h in portfolio.holdings}

    institutional_scores = compute_institutional_scores(risk, prices, weights, sector_alloc)

    pdf_bytes = gen.generate_pdf_report(
        portfolio=portfolio,
        risk=risk,
        sector_data=sector_data,
        df=df,
        mc_result=mc_result,
        portfolio_cum=portfolio_cum,
        institutional_scores=institutional_scores,
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 5000


def test_generate_pdf_report_with_regime_recommendations_warnings():
    """Exercise the regime / recommendations / warnings PDF blocks with real objects.

    Regression guard: these three blocks read attributes that never existed on
    the engine dataclasses (regime: current_regime/regime_probabilities/regime_returns;
    warnings: warning_report.warnings / w.message). They crashed at runtime unless
    real instances were passed — which the other tests never did.
    """
    from engine.recommendations import ActionType, RecommendationCard, RecommendationReport
    from engine.regime import RegimeResult
    from engine.warnings import SignalSeverity, WarningReport, WarningSignal

    portfolio = _sample_portfolio()
    risk = _sample_risk_metrics()
    sector_data = _sample_sector_data()
    df = _sample_export_df(portfolio)
    mc_result = _sample_mc_result()
    portfolio_cum = _sample_portfolio_cum()

    regime_result = RegimeResult(
        n_states=3,
        labels=["Bull", "Neutral", "Bear"],
        state_sequence=["Bull", "Neutral", "Bear", "Bear", "Neutral"],
        transition_matrix=[[0.7, 0.2, 0.1], [0.1, 0.8, 0.1], [0.15, 0.15, 0.7]],
        stats=[
            {
                "label": "Bull",
                "count": 2,
                "pct": 40.0,
                "mean_return": 0.12,
                "annual_vol": 12.0,
                "cum_return": 8.5,
            },
            {
                "label": "Neutral",
                "count": 2,
                "pct": 40.0,
                "mean_return": 0.02,
                "annual_vol": 8.0,
                "cum_return": 1.2,
            },
            {
                "label": "Bear",
                "count": 1,
                "pct": 20.0,
                "mean_return": -0.08,
                "annual_vol": 18.0,
                "cum_return": -5.1,
            },
        ],
    )

    recommendations = RecommendationReport(
        cards=[
            RecommendationCard(
                id="hedge_portfolio_1",
                title="Hedge Portfolio",
                priority=1,
                urgency=Urgency.NEAR_TERM,
                action=ActionType.BUY,  # Hedge is a BUY action (buying protection)
                tickers=["PORTFOLIO"],
                qtys={"PORTFOLIO": 1},
                prices={"PORTFOLIO": 1.0},
                reason="Portfolio beta is elevated; a partial hedge reduces crash exposure.",
                regime_context=RegimeContext.NEUTRAL,
                rule_verdicts=[],
                tax_breakdown={},
                impact_breakdown={},
                net_risk_reduction_bps=300,
                confidence=0.75,
                guardrails=["Hedging caps upside in a rally"],
                alternatives=["Reduce equity exposure instead"],
            ),
            RecommendationCard(
                id="trim_banking_1",
                title="Trim Banking",
                priority=2,
                urgency=Urgency.IMMEDIATE,
                action=ActionType.TRIM,
                tickers=["BANKING"],
                qtys={"BANKING": 1},
                prices={"BANKING": 1.0},
                reason="Concentration in banking raises sector drawdown risk.",
                regime_context=RegimeContext.NEUTRAL,
                rule_verdicts=[],
                tax_breakdown={},
                impact_breakdown={},
                net_risk_reduction_bps=400,
                confidence=0.8,
                guardrails=["Reduces participation in a banking-led rally"],
                alternatives=["Buy index puts instead"],
            ),
        ],
        generated_at="2024-01-01T00:00:00",
        regime_context=RegimeContext.NEUTRAL,
        total_risk_reduction_bps=700,
        total_tax_cost=0.0,
        total_impact_cost=0.0,
        confidence=0.77,
        summary="Moderate risk profile; one near-term hedge recommended.",
    )

    warning_report = WarningReport(
        signals=[
            WarningSignal(
                name="Death Cross: RELIANCE",
                severity=SignalSeverity.WARNING,
                signal_type="technical",
                description="20-day MA crossed below 50-day MA for RELIANCE.",
                reasoning="Short-term trend weakened versus medium-term.",
                affected_holdings=["RELIANCE"],
                suggested_action="Monitor closely; tighten stops.",
            )
        ],
        overall_warning_level="amber",
        signal_count_by_severity={"warning": 1},
        summary="One technical warning active.",
    )

    pdf_bytes = gen.generate_pdf_report(
        portfolio=portfolio,
        risk=risk,
        sector_data=sector_data,
        df=df,
        mc_result=mc_result,
        portfolio_cum=portfolio_cum,
        regime_result=regime_result,
        recommendations=recommendations,
        warning_report=warning_report,
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 5000


def test_generate_pdf_report_minimal():
    """Generate PDF with no optional data."""
    portfolio = _sample_portfolio()
    df = _sample_export_df(portfolio)

    pdf_bytes = gen.generate_pdf_report(
        portfolio=portfolio,
        risk=None,
        sector_data=None,
        df=df,
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1000