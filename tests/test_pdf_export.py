"""Tests for the PDF report export module."""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from engine import Holding, Portfolio, RiskMetrics
from engine.risk import MonteCarloResult

# Skip PDF tests if pdf-studio not available
try:
    from pdf_studio import Document  # noqa: F401
    _PDF_STUDIO_AVAILABLE = True
except ImportError:
    _PDF_STUDIO_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _PDF_STUDIO_AVAILABLE, reason="pdf-studio not installed")


def _sample_portfolio() -> Portfolio:
    """Create a portfolio with non-zero current prices for PDF testing."""
    holdings = [
        Holding(ticker="RELIANCE.NS", name="Reliance Industries", quantity=10, avg_price=2500,
                current_price=2800, sector="Oil & Gas"),
        Holding(ticker="TCS.NS", name="Tata Consultancy Services", quantity=5, avg_price=3500,
                current_price=3800, sector="IT"),
        Holding(ticker="HDFCBANK.NS", name="HDFC Bank", quantity=20, avg_price=1600,
                current_price=1700, sector="Banking"),
    ]
    return Portfolio(holdings=holdings, name="Test Portfolio")


def _sample_risk_metrics() -> RiskMetrics:
    return RiskMetrics(
        volatility_annual=18.5,
        var_95=-2.8,
        var_99=-4.5,
        cvar_95=-3.5,
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
        rows.append({
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
        })
    return pd.DataFrame(rows)


def _get_plt():
    """Shared matplotlib import for chart tests."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


# ── Chart figure tests (all return Figure objects) ──


def test_gauge():
    from ui.charts_pdf import _gauge
    risk = _sample_risk_metrics()
    plt = _get_plt()
    result = _gauge(risk, plt)
    assert result is not None
    assert hasattr(result, "savefig")


def test_gauge_none_risk():
    from ui.charts_pdf import _gauge
    plt = _get_plt()
    result = _gauge(None, plt)
    assert result is None


def test_gauge_none_plt():
    from ui.charts_pdf import _gauge
    risk = _sample_risk_metrics()
    result = _gauge(risk, None)
    assert result is None


def test_cover_banner():
    from ui.charts_pdf import _cover_banner
    portfolio = _sample_portfolio()
    plt = _get_plt()
    result = _cover_banner(portfolio, plt)
    assert result is not None
    assert hasattr(result, "savefig")


def test_cover_banner_none():
    from ui.charts_pdf import _cover_banner
    portfolio = _sample_portfolio()
    result = _cover_banner(portfolio, None)
    assert result is None


def test_drawdown_chart():
    from ui.charts_pdf import _drawdown_chart
    plt = _get_plt()
    cum = _sample_portfolio_cum()
    result = _drawdown_chart(cum, plt)
    assert result is not None
    assert hasattr(result, "savefig")


def test_monte_carlo_chart():
    from ui.charts_pdf import _monte_carlo_chart
    plt = _get_plt()
    mc = _sample_mc_result()
    result = _monte_carlo_chart(mc, plt)
    assert result is not None
    assert hasattr(result, "savefig")


def test_sector_weight_composite():
    from ui.charts_pdf import _sector_weight_composite
    plt = _get_plt()
    portfolio = _sample_portfolio()
    sector_data = _sample_sector_data()
    result = _sector_weight_composite(sector_data, portfolio, plt)
    assert result is not None
    assert hasattr(result, "savefig")


def test_pnl_chart():
    from ui.charts_pdf import _pnl_chart
    plt = _get_plt()
    portfolio = _sample_portfolio()
    df = _sample_export_df(portfolio)
    result = _pnl_chart(df, plt)
    assert result is not None
    assert hasattr(result, "savefig")


# ── Data table helper tests ──


def test_cover_metrics():
    from ui.charts_pdf import _cover_metrics
    portfolio = _sample_portfolio()
    risk = _sample_risk_metrics()
    table = _cover_metrics(portfolio, risk)
    assert isinstance(table, list)
    assert "Holdings" in table[1][0]  # first data row, col 0
    assert len(table) == 4  # header + 3 data rows


def test_full_metrics():
    from ui.charts_pdf import _full_metrics
    portfolio = _sample_portfolio()
    risk = _sample_risk_metrics()
    table = _full_metrics(portfolio, risk)
    assert isinstance(table, list)
    assert len(table) >= 5  # header + 4+ data rows


def test_risk_metrics_table():
    from ui.charts_pdf import _risk_metrics_table
    portfolio = _sample_portfolio()
    risk = _sample_risk_metrics()
    table = _risk_metrics_table(risk, portfolio)
    assert isinstance(table, list)
    assert len(table) == 9  # header + 8 risk metric rows (6 original + 2 new)


# ── Full PDF generation tests ──


def test_generate_pdf_report_full():
    """Generate a full PDF with all sections."""
    from ui.charts_pdf import _generate_pdf_report
    portfolio = _sample_portfolio()
    risk = _sample_risk_metrics()
    sector_data = _sample_sector_data()
    df = _sample_export_df(portfolio)
    mc_result = _sample_mc_result()
    portfolio_cum = _sample_portfolio_cum()

    pdf_bytes = _generate_pdf_report(
        portfolio=portfolio,
        risk=risk,
        sector_data=sector_data,
        df=df,
        mc_result=mc_result,
        portfolio_cum=portfolio_cum,
    )
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_pdf_report_minimal():
    """Generate PDF with no optional data (risk=None, sector=None, etc.)."""
    from ui.charts_pdf import _generate_pdf_report
    portfolio = _sample_portfolio()
    df = _sample_export_df(portfolio)

    pdf_bytes = _generate_pdf_report(
        portfolio=portfolio,
        risk=None,
        sector_data=None,
        df=df,
    )
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes[:4] == b"%PDF"


# ── Utility function tests ──


def test_risk_assessment_low_vol():
    from ui.charts_pdf import _risk_assessment_text
    risk = _sample_risk_metrics()
    risk.volatility_annual = 12.0
    risk.sharpe = 1.5
    text, color = _risk_assessment_text(risk)
    assert "LOW" in text
    assert color == (220, 245, 220)


def test_risk_assessment_high_vol():
    from ui.charts_pdf import _risk_assessment_text
    risk = _sample_risk_metrics()
    risk.volatility_annual = 35.0
    risk.sharpe = 0.3
    text, color = _risk_assessment_text(risk)
    assert "HIGH" in text
    assert color == (250, 220, 220)


def test_risk_assessment_none():
    from ui.charts_pdf import _risk_assessment_text
    text, color = _risk_assessment_text(None)
    assert "not available" in text
