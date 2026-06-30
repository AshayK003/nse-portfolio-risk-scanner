"""Tests for the risk computation module."""

import numpy as np
import pandas as pd

from engine import RiskMetrics
from engine.risk import compute_correlation_matrix, compute_risk_metrics


class TestComputeRiskMetrics:
    def test_returns_correct_types(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        result = compute_risk_metrics(sample_prices, weights)

        assert isinstance(result, RiskMetrics)
        assert isinstance(result.volatility_annual, float)
        assert isinstance(result.var_95, float)
        assert isinstance(result.sharpe, float)

    def test_volatility_is_positive(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        result = compute_risk_metrics(sample_prices, weights)
        assert result.volatility_annual > 0

    def test_var_95_is_negative(self, sample_prices):
        """VaR at 95% should be negative (loss)."""
        weights = [0.4, 0.3, 0.3]
        result = compute_risk_metrics(sample_prices, weights)
        assert result.var_95 < 0

    def test_max_drawdown_is_negative(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        result = compute_risk_metrics(sample_prices, weights)
        assert result.max_drawdown < 0

    def test_empty_prices(self):
        empty = pd.DataFrame()
        result = compute_risk_metrics(empty, [])
        assert result.volatility_annual == 0.0

    def test_single_stock(self, sample_prices):
        single = sample_prices.iloc[:, :1]
        result = compute_risk_metrics(single, [1.0])
        assert result.volatility_annual > 0

    def test_weights_dont_need_to_sum_exactly_1(self, sample_prices):
        """Should auto-normalize weights."""
        weights = [40, 30, 30]  # sums to 100, not 1
        result = compute_risk_metrics(sample_prices, weights)
        assert isinstance(result, RiskMetrics)

    def test_with_benchmark(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        # Create benchmark that's highly correlated with the portfolio
        portfolio_returns = sample_prices.pct_change().dropna().dot(np.array(weights))
        bench = portfolio_returns * 0.8 + pd.Series(
            np.random.normal(0.0, 0.002, len(portfolio_returns)),
            index=portfolio_returns.index,
        )
        result = compute_risk_metrics(sample_prices, weights, benchmark_returns=bench)
        assert isinstance(result.beta, float)
        assert result.beta > 0  # correlated -> positive beta


class TestCorrelationMatrix:
    def test_returns_dataframe(self, sample_prices):
        corr = compute_correlation_matrix(sample_prices)
        assert isinstance(corr, pd.DataFrame)

    def test_square_matrix(self, sample_prices):
        corr = compute_correlation_matrix(sample_prices)
        assert corr.shape[0] == corr.shape[1]
        assert corr.shape[0] == sample_prices.shape[1]

    def test_diagonal_ones(self, sample_prices):
        corr = compute_correlation_matrix(sample_prices)
        for i in range(corr.shape[0]):
            assert abs(corr.iloc[i, i] - 1.0) < 0.001
