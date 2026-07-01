"""Tests for storage models — serialization round-trips and edge cases."""

from __future__ import annotations

import json

from engine import (
    AnalysisReport,
    BenchmarkComparison,
    Holding,
    Portfolio,
    SectorExposure,
)
from engine.risk import _empty_risk_metrics
from storage.models import (
    AnalysisRun,
    SavedPortfolio,
    analysis_from_report,
    portfolio_to_saved,
    saved_to_portfolio,
)


def _make_portfolio() -> Portfolio:
    return Portfolio(
        holdings=[
            Holding(ticker="RELIANCE.NS", name="RIL", quantity=10, avg_price=2500,
                    sector="Oil & Gas", current_price=2600, change_pct=1.5),
            Holding(ticker="TCS.NS", name="TCS", quantity=5, avg_price=3500,
                    sector="IT", current_price=3400, change_pct=-0.8),
        ],
        name="Test Fund",
    )


def _make_report() -> AnalysisReport:
    portfolio = _make_portfolio()
    return AnalysisReport(
        portfolio=portfolio,
        risk=_empty_risk_metrics(),
        sector=SectorExposure(
            holdings=portfolio.holdings,
            sector_allocation={"Oil & Gas": 60.0, "IT": 40.0},
            concentrated_sectors=[],
            diversification_score=70.0,
            herfindahl_index=0.32,
        ),
        benchmark=BenchmarkComparison(
            portfolio_return=20.0, benchmark_return=15.0, alpha=5.0,
            tracking_error=4.0, information_ratio=1.25, beta=0.9,
            correlation=0.88, rolling_alpha_6m=6.0,
            outperformance_months=7, total_months=12,
        ),
    )


class TestPortfolioRoundTrip:
    def test_to_saved_and_back(self):
        original = _make_portfolio()
        saved = portfolio_to_saved(original, name="My Fund")

        assert saved.name == "My Fund"
        assert saved.holdings_json != ""
        assert saved.total_invested > 0
        assert saved.total_current > 0

        restored = saved_to_portfolio(saved)

        assert restored.name == "My Fund"
        assert len(restored.holdings) == 2
        assert restored.holdings[0].ticker == "RELIANCE.NS"
        assert restored.holdings[0].quantity == 10
        assert restored.holdings[0].avg_price == 2500
        assert restored.holdings[0].sector == "Oil & Gas"
        assert restored.holdings[0].current_price == 2600
        assert restored.holdings[0].change_pct == 1.5

    def test_round_trip_preserves_all_fields(self):
        original = _make_portfolio()
        saved = portfolio_to_saved(original)
        restored = saved_to_portfolio(saved)

        for orig_h, rest_h in zip(original.holdings, restored.holdings, strict=True):
            assert orig_h.ticker == rest_h.ticker
            assert orig_h.name == rest_h.name
            assert orig_h.quantity == rest_h.quantity
            assert orig_h.avg_price == rest_h.avg_price
            assert orig_h.sector == rest_h.sector
            assert orig_h.current_price == rest_h.current_price

    def test_saved_totals_match_portfolio(self):
        original = _make_portfolio()
        saved = portfolio_to_saved(original)
        assert saved.total_invested == round(original.total_invested, 2)
        assert saved.total_current == round(original.total_current, 2)

    def test_empty_portfolio_round_trip(self):
        original = Portfolio(holdings=[], name="Empty")
        saved = portfolio_to_saved(original)
        restored = saved_to_portfolio(saved)
        assert len(restored.holdings) == 0
        assert restored.name == "Empty"

    def test_saved_to_portfolio_missing_optional_fields(self):
        """When JSON has no sector/current_price/change_pct, defaults are used."""
        sp = SavedPortfolio(
            name="Legacy",
            holdings_json=json.dumps([
                {"ticker": "TCS", "name": "TCS", "quantity": 5, "avg_price": 3500}
            ]),
        )
        p = saved_to_portfolio(sp)
        assert p.holdings[0].sector == ""
        assert p.holdings[0].current_price == 0.0
        assert p.holdings[0].change_pct == 0.0


class TestAnalysisFromReport:
    def test_creates_analysis_run(self):
        report = _make_report()
        run = analysis_from_report(report)

        assert run.portfolio_name == "Test Fund"
        assert run.holding_count == 2
        assert run.volatility == report.risk.volatility_annual
        assert run.var_95 == report.risk.var_95
        assert run.sharpe == report.risk.sharpe
        assert run.beta == report.risk.beta
        assert run.diversification_score == report.sector.diversification_score
        assert run.created_at != ""

    def test_custom_portfolio_name(self):
        report = _make_report()
        run = analysis_from_report(report, portfolio_name="Override")
        assert run.portfolio_name == "Override"

    def test_analysis_run_defaults(self):
        run = AnalysisRun()
        assert run.portfolio_name == ""
        assert run.holding_count == 0
        assert run.benchmark_name == "NIFTY 50"


class TestSavedPortfolioDefaults:
    def test_default_fields(self):
        sp = SavedPortfolio()
        assert sp.id is None
        assert sp.name == ""
        assert sp.holdings_json == ""
        assert sp.total_invested == 0.0
