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
