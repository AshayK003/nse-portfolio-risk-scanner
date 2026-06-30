"""Tests for the portfolio optimization module."""

import pandas as pd

from engine.optimization import optimize_hrp, optimize_max_sharpe, optimize_min_volatility


class TestOptimizeHRP:
    def test_returns_weights(self, sample_prices):
        returns = sample_prices.pct_change().dropna()
        result = optimize_hrp(returns)
        assert result.method == "hrp"
        assert len(result.weights) == sample_prices.shape[1]

    def test_weights_sum_to_one(self, sample_prices):
        returns = sample_prices.pct_change().dropna()
        result = optimize_hrp(returns)
        total = sum(result.weights.values())
        assert abs(total - 1.0) < 0.01

    def test_all_weights_positive(self, sample_prices):
        returns = sample_prices.pct_change().dropna()
        result = optimize_hrp(returns)
        assert all(w >= 0 for w in result.weights.values())

    def test_single_asset(self):
        prices = pd.DataFrame({"A.NS": [100 + i for i in range(100)]})
        returns = prices.pct_change().dropna()
        result = optimize_hrp(returns)
        assert len(result.weights) == 1
        assert abs(result.weights["A.NS"] - 1.0) < 0.01

    def test_empty_returns(self):
        result = optimize_hrp(pd.DataFrame())
        assert result.weights == {}


class TestOptimizeMinVol:
    def test_returns_weights(self, sample_prices):
        returns = sample_prices.pct_change().dropna()
        result = optimize_min_volatility(returns)
        assert result.method == "min_volatility"
        assert len(result.weights) == sample_prices.shape[1]
        total = sum(result.weights.values())
        assert abs(total - 1.0) < 0.01

    def test_all_weights_positive(self, sample_prices):
        returns = sample_prices.pct_change().dropna()
        result = optimize_min_volatility(returns)
        assert all(w >= 0 for w in result.weights.values())


class TestOptimizeMaxSharpe:
    def test_returns_weights(self, sample_prices):
        returns = sample_prices.pct_change().dropna()
        result = optimize_max_sharpe(returns)
        assert result.method == "max_sharpe"
        assert len(result.weights) == sample_prices.shape[1]
        total = sum(result.weights.values())
        assert abs(total - 1.0) < 0.01

    def test_positive_sharpe(self, sample_prices):
        returns = sample_prices.pct_change().dropna()
        result = optimize_max_sharpe(returns)
        assert result.sharpe >= 0
