"""Tests for the portfolio recommendations engine."""

from engine import BenchmarkComparison, Holding, Portfolio, RiskMetrics, SectorExposure
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

    def _make_benchmark(self):
        return BenchmarkComparison(
            portfolio_return=22.0,
            benchmark_return=18.0,
            alpha=4.0,
            tracking_error=5.0,
            information_ratio=0.8,
            beta=0.95,
            correlation=0.88,
            rolling_alpha_6m=5.0,
            outperformance_months=7,
            total_months=12,
        )

    def _make_portfolio(self):
        holdings = [
            Holding(
                ticker="RELIANCE",
                name="Reliance",
                quantity=10,
                avg_price=2500,
                current_price=2700,
                sector="Oil & Gas",
            ),
            Holding(ticker="TCS", name="TCS", quantity=5, avg_price=3500, current_price=3800, sector="IT"),
            Holding(
                ticker="HDFCBANK",
                name="HDFC Bank",
                quantity=20,
                avg_price=1600,
                current_price=1700,
                sector="Banking",
            ),
        ]
        return Portfolio(holdings=holdings)

    def test_returns_report_type(self):
        result = generate_recommendations(
            risk=self._make_risk(),
            sector=self._make_sector(),
            benchmark=self._make_benchmark(),
            portfolio=self._make_portfolio(),
        )
        assert isinstance(result, RecommendationReport)

    def test_has_recommendations(self):
        result = generate_recommendations(
            risk=self._make_risk(),
            sector=self._make_sector(),
            benchmark=self._make_benchmark(),
            portfolio=self._make_portfolio(),
        )
        assert len(result.recommendations) > 0

    def test_concentration_triggers_reduce(self):
        result = generate_recommendations(
            risk=self._make_risk(),
            sector=self._make_sector(concentrated=["Banking"]),
            benchmark=self._make_benchmark(),
            portfolio=self._make_portfolio(),
        )
        banking_recs = [r for r in result.recommendations if r.target == "Banking"]
        assert len(banking_recs) > 0
        assert banking_recs[0].action in (ActionType.REDUCE, ActionType.DIVERSIFY)

    def test_high_beta_triggers_hedge(self):
        result = generate_recommendations(
            risk=self._make_risk(beta=1.5),
            sector=self._make_sector(concentrated=[]),
            benchmark=self._make_benchmark(),
            portfolio=self._make_portfolio(),
        )
        hedge_recs = [r for r in result.recommendations if r.action == ActionType.HEDGE]
        assert len(hedge_recs) > 0

    def test_low_sharpe_triggers_rebalance(self):
        result = generate_recommendations(
            risk=self._make_risk(sharpe=0.3),
            sector=self._make_sector(concentrated=[]),
            benchmark=self._make_benchmark(),
            portfolio=self._make_portfolio(),
        )
        rebal_recs = [r for r in result.recommendations if r.action == ActionType.REBALANCE]
        assert len(rebal_recs) > 0

    def test_recommendations_have_trade_offs(self):
        result = generate_recommendations(
            risk=self._make_risk(),
            sector=self._make_sector(),
            benchmark=self._make_benchmark(),
            portfolio=self._make_portfolio(),
        )
        for rec in result.recommendations:
            assert len(rec.trade_off) > 0
            assert len(rec.reasoning) > 0

    def test_priority_actions_populated(self):
        result = generate_recommendations(
            risk=self._make_risk(beta=1.5, sharpe=0.2),
            sector=self._make_sector(concentrated=["Banking"]),
            benchmark=self._make_benchmark(),
            portfolio=self._make_portfolio(),
        )
        assert len(result.priority_actions) > 0

    def test_summary_populated(self):
        result = generate_recommendations(
            risk=self._make_risk(),
            sector=self._make_sector(),
            benchmark=self._make_benchmark(),
            portfolio=self._make_portfolio(),
        )
        assert len(result.summary) > 0

    def test_risk_reduction_non_negative(self):
        result = generate_recommendations(
            risk=self._make_risk(),
            sector=self._make_sector(),
            benchmark=self._make_benchmark(),
            portfolio=self._make_portfolio(),
        )
        assert result.risk_reduction_potential >= 0

    def test_action_type_enum(self):
        assert ActionType.REDUCE.value == "reduce"
        assert ActionType.HEDGE.value == "hedge"
        assert ActionType.DIVERSIFY.value == "diversify"
        assert ActionType.ACCUMULATE.value == "accumulate"
        assert ActionType.MONITOR.value == "monitor"
        assert ActionType.REBALANCE.value == "rebalance"
