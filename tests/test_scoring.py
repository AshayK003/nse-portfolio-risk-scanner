"""Tests for the institutional risk scoring module."""

import pandas as pd

from engine import RiskMetrics
from engine.scoring import (
    InstitutionalRiskScores,
    RiskScore,
    compute_institutional_scores,
)


class TestComputeInstitutionalScores:
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

    def test_returns_correct_type(self, sample_prices):
        risk = self._make_risk()
        weights = [0.4, 0.3, 0.3]
        sector_alloc = {"Banking": 40.0, "IT": 35.0, "Oil & Gas": 25.0}
        result = compute_institutional_scores(risk, sample_prices, weights, sector_alloc)
        assert isinstance(result, InstitutionalRiskScores)

    def test_scores_in_range(self, sample_prices):
        risk = self._make_risk()
        weights = [0.4, 0.3, 0.3]
        sector_alloc = {"Banking": 40.0, "IT": 35.0, "Oil & Gas": 25.0}
        result = compute_institutional_scores(risk, sample_prices, weights, sector_alloc)
        assert 0 <= result.overall_risk_score <= 100
        assert 0 <= result.conviction_score <= 100
        assert 0 <= result.portfolio_stress_score <= 100
        assert 0 <= result.hidden_correlation_score <= 100
        assert 0 <= result.tail_risk_score <= 100

    def test_risk_factors_populated(self, sample_prices):
        risk = self._make_risk()
        weights = [0.4, 0.3, 0.3]
        sector_alloc = {"Banking": 40.0, "IT": 35.0, "Oil & Gas": 25.0}
        result = compute_institutional_scores(risk, sample_prices, weights, sector_alloc)
        assert len(result.risk_factors) > 0

    def test_top_5_insights_sorted_by_composite(self, sample_prices):
        risk = self._make_risk()
        weights = [0.4, 0.3, 0.3]
        sector_alloc = {"Banking": 40.0, "IT": 35.0, "Oil & Gas": 25.0}
        result = compute_institutional_scores(risk, sample_prices, weights, sector_alloc)
        assert len(result.top_5_insights) <= 5
        composites = [i.composite for i in result.top_5_insights]
        assert composites == sorted(composites, reverse=True)

    def test_interpretation_populated(self, sample_prices):
        risk = self._make_risk()
        weights = [0.4, 0.3, 0.3]
        sector_alloc = {"Banking": 40.0, "IT": 35.0}
        result = compute_institutional_scores(risk, sample_prices, weights, sector_alloc)
        assert len(result.score_interpretation) > 0

    def test_high_risk_portfolio(self, sample_prices):
        risk = self._make_risk(
            volatility_annual=35.0, var_95=-5.0, cvar_95=-6.0, max_drawdown=-35.0, sharpe=0.2
        )
        weights = [0.4, 0.3, 0.3]
        sector_alloc = {"Banking": 60.0, "IT": 40.0}
        result = compute_institutional_scores(risk, sample_prices, weights, sector_alloc)
        assert result.overall_risk_score > 50

    def test_low_risk_portfolio(self, sample_prices):
        risk = self._make_risk(
            volatility_annual=10.0, var_95=-1.2, cvar_95=-1.5, max_drawdown=-8.0, sharpe=1.8
        )
        weights = [0.4, 0.3, 0.3]
        sector_alloc = {"Banking": 20.0, "IT": 20.0, "Pharma": 20.0, "FMCG": 20.0, "Oil & Gas": 20.0}
        result = compute_institutional_scores(risk, sample_prices, weights, sector_alloc)
        assert result.overall_risk_score < 50
        assert result.conviction_score > 50

    def test_empty_risk(self):
        risk = RiskMetrics(
            volatility_annual=0.0,
            var_95=0.0,
            var_99=0.0,
            cvar_95=0.0,
            max_drawdown=0.0,
            max_drawdown_start="",
            max_drawdown_end="",
            beta=1.0,
            correlation_to_benchmark=0.0,
            sharpe=0.0,
            sortino=0.0,
            cagr=0.0,
            total_return=0.0,
        )
        result = compute_institutional_scores(risk, pd.DataFrame(), [], {})
        assert result.overall_risk_score == 0.0

    def test_risk_score_fields(self):
        score = RiskScore(
            name="Test",
            probability=0.5,
            impact=0.6,
            confidence=0.8,
            composite=24.0,
            reasoning="Test reasoning",
            category="systematic",
        )
        assert score.name == "Test"
        assert score.composite == 24.0
        assert score.category == "systematic"
