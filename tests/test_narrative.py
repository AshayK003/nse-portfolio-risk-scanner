"""Tests for the rule-based narrative generation engine."""

from engine import (
    AnalysisReport,
    BenchmarkComparison,
    Portfolio,
    RiskMetrics,
    SectorExposure,
)


class TestGenerateNarrative:
    """Core narrative generation tests."""

    def _make_portfolio(self, **overrides):
        from engine import Holding

        holdings = [
            Holding(
                ticker="RELIANCE.NS",
                name="Reliance Industries",
                quantity=10,
                avg_price=2500,
                sector="Oil & Gas",
                current_price=2800,
            ),
            Holding(ticker="TCS.NS", name="TCS", quantity=5, avg_price=3500, sector="IT", current_price=3800),
            Holding(
                ticker="HDFCBANK.NS",
                name="HDFC Bank",
                quantity=20,
                avg_price=1600,
                sector="Banking",
                current_price=1700,
            ),
        ]
        p = Portfolio(holdings=holdings, name=overrides.get("name", "Test"))
        return p

    def _make_risk(self, **overrides):
        defaults = dict(
            volatility_annual=18.0,
            var_95=-2.5,
            var_99=-4.0,
            cvar_95=-3.2,
            max_drawdown=-18.0,
            max_drawdown_start="2024-03-01",
            max_drawdown_end="2024-06-15",
            beta=0.95,
            correlation_to_benchmark=0.88,
            sharpe=1.1,
            sortino=1.6,
            cagr=12.0,
            total_return=22.0,
        )
        defaults.update(overrides)
        return RiskMetrics(**defaults)

    def _make_sector(self, **overrides):
        defaults = dict(
            sector_allocation={"Banking": 40.0, "IT": 35.0, "Oil & Gas": 25.0},
            concentrated_sectors=["Banking"],
            diversification_score=55.0,
            herfindahl_index=0.35,
        )
        defaults.update(overrides)
        return SectorExposure(
            holdings=self._make_portfolio().holdings,
            **defaults,
        )

    def _make_benchmark(self, **overrides):
        defaults = dict(
            portfolio_return=22.0,
            benchmark_return=18.0,
            alpha=4.0,
            tracking_error=5.5,
            information_ratio=0.73,
            beta=0.95,
            correlation=0.88,
            up_capture=100.0,
            down_capture=100.0,
            rolling_alpha_6m=6.0,
            outperformance_months=8,
            total_months=12,
        )
        defaults.update(overrides)
        return BenchmarkComparison(**defaults)

    def _make_report(self, **overrides):
        portfolio = overrides.get("portfolio") if "portfolio" in overrides else self._make_portfolio()
        risk = overrides.get("risk") if "risk" in overrides else self._make_risk()
        sector = overrides.get("sector") if "sector" in overrides else self._make_sector()
        benchmark = overrides.get("benchmark") if "benchmark" in overrides else self._make_benchmark()
        return AnalysisReport(
            portfolio=portfolio,
            risk=risk,
            sector=sector,
            benchmark=benchmark,
        )
