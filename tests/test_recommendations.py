"""Tests for the portfolio recommendations engine."""

from engine import BenchmarkComparison, Holding, Portfolio, RiskMetrics, SectorExposure
from engine.__init__ import AGGRESSIVE, CONSERVATIVE, MODERATE
from engine.recommendations import (
    ActionType,
    RecommendationReport,
    generate_recommendations,
)


class TestGenerateRecommendations:
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

    def _make_sector(self, concentrated=None):
        return SectorExposure(
            holdings=[],
            sector_allocation={"Banking": 40.0, "IT": 35.0, "Oil & Gas": 25.0},
            concentrated_sectors=concentrated or ["Banking"],
            diversification_score=55.0,
            herfindahl_index=0.35,
        )

    def _make_benchmark(self, **overrides):
        defaults = dict(
            portfolio_return=22.0,
            benchmark_return=18.0,
            alpha=4.0,
            tracking_error=5.0,
            information_ratio=0.8,
            beta=0.95,
            correlation=0.88,
            up_capture=100.0,
            down_capture=100.0,
            rolling_alpha_6m=5.0,
            outperformance_months=7,
            total_months=12,
        )
        defaults.update(overrides)
        return BenchmarkComparison(**defaults)

    def _make_portfolio(self):
        holdings = [
            Holding(
                ticker="RELIANCE",
                name="Reliance",
                quantity=10,
                avg_price=2500,
                current_price=2700,
                sector="Energy",
            ),
            Holding(
                ticker="TCS",
                name="TCS",
                quantity=5,
                avg_price=3500,
                current_price=3800,
                sector="IT",
            ),
            Holding(
                ticker="HDFCBANK",
                name="HDFC Bank",
                quantity=20,
                avg_price=1600,
                current_price=1700,
                sector="Banking",
            ),
        ]
        return Portfolio(holdings=holdings, name="Test Portfolio")

    def test_returns_report_type(self):
        portfolio = self._make_portfolio()
        risk = self._make_risk()
        sector = self._make_sector()
        benchmark = self._make_benchmark()

        report = generate_recommendations(
            portfolio=portfolio,
            risk=risk,
            sector=sector,
            benchmark=benchmark,
            profile=MODERATE,
        )

        assert isinstance(report, RecommendationReport)
        assert report.summary is not None
        assert len(report.priority_actions) > 0

    def test_conservative_profile_more_actions(self):
        portfolio = self._make_portfolio()
        risk = self._make_risk()
        sector = self._make_sector()
        benchmark = self._make_benchmark()

        aggressive_report = generate_recommendations(
            portfolio=portfolio,
            risk=risk,
            sector=sector,
            benchmark=benchmark,
            profile=AGGRESSIVE,
        )
        conservative_report = generate_recommendations(
            portfolio=portfolio,
            risk=risk,
            sector=sector,
            benchmark=benchmark,
            profile=CONSERVATIVE,
        )

        # Conservative has LOWER thresholds so it triggers MORE recommendations
        assert len(conservative_report.priority_actions) >= len(aggressive_report.priority_actions)

    def test_high_vol_triggers_reduce(self):
        portfolio = self._make_portfolio()
        risk = self._make_risk(volatility_annual=45.0)
        sector = self._make_sector()
        benchmark = self._make_benchmark()

        report = generate_recommendations(
            portfolio=portfolio,
            risk=risk,
            sector=sector,
            benchmark=benchmark,
            profile=MODERATE,
        )

        # Should have at least one REDUCE action for high volatility
        reduce_actions = [a for a in report.priority_actions if a.action == ActionType.REDUCE]
        assert len(reduce_actions) > 0

    def test_concentrated_sector_triggers_reduce(self):
        portfolio = self._make_portfolio()
        risk = self._make_risk()
        sector = self._make_sector(concentrated=["Tech", "Energy", "Banking"])
        benchmark = self._make_benchmark()

        report = generate_recommendations(
            portfolio=portfolio,
            risk=risk,
            sector=sector,
            benchmark=benchmark,
            profile=MODERATE,
        )

        reduce_actions = [a for a in report.priority_actions if a.action == ActionType.REDUCE]
        assert len(reduce_actions) > 0

    def test_high_drawdown_triggers_monitor(self):
        portfolio = self._make_portfolio()
        risk = self._make_risk(max_drawdown=-45.0)
        sector = self._make_sector()
        benchmark = self._make_benchmark()

        report = generate_recommendations(
            portfolio=portfolio,
            risk=risk,
            sector=sector,
            benchmark=benchmark,
            profile=MODERATE,
        )

        monitor_actions = [a for a in report.priority_actions if a.action == ActionType.MONITOR]
        assert len(monitor_actions) > 0

    def test_low_beta_triggers_accumulate(self):
        portfolio = self._make_portfolio()
        risk = self._make_risk(beta=0.4)  # Low beta triggers ACCUMULATE
        sector = self._make_sector()
        benchmark = self._make_benchmark()

        report = generate_recommendations(
            portfolio=portfolio,
            risk=risk,
            sector=sector,
            benchmark=benchmark,
            profile=MODERATE,
        )

        accumulate_actions = [a for a in report.recommendations if a.action == ActionType.ACCUMULATE]
        assert len(accumulate_actions) > 0

    def test_negative_alpha_triggers_reduce(self):
        portfolio = self._make_portfolio()
        risk = self._make_risk()
        sector = self._make_sector()
        benchmark = self._make_benchmark(alpha=-5.0)

        report = generate_recommendations(
            portfolio=portfolio,
            risk=risk,
            sector=sector,
            benchmark=benchmark,
            profile=MODERATE,
        )

        reduce_actions = [a for a in report.priority_actions if a.action == ActionType.REDUCE]
        assert len(reduce_actions) > 0

    def test_low_sharpe_triggers_reduce(self):
        portfolio = self._make_portfolio()
        risk = self._make_risk(sharpe=0.2, sortino=0.1)
        sector = self._make_sector()
        benchmark = self._make_benchmark()

        report = generate_recommendations(
            portfolio=portfolio,
            risk=risk,
            sector=sector,
            benchmark=benchmark,
            profile=MODERATE,
        )

        reduce_actions = [a for a in report.priority_actions if a.action == ActionType.REDUCE]
        assert len(reduce_actions) > 0
