"""Tests for the performance computation module."""

import numpy as np
import pandas as pd

from engine.performance import (
    compute_max_drawdown,
    compute_portfolio_returns,
)


class TestComputePortfolioReturns:
    def test_weighted_returns(self, sample_prices):
        weights = [0.5, 0.3, 0.2]
        result = compute_portfolio_returns(sample_prices, weights)
        assert isinstance(result, pd.Series)
        assert len(result) > 0

    def test_weights_auto_normalize(self, sample_prices):
        """Weights that don't sum to 1 should be auto-normalized."""
        weights = [50, 30, 20]  # sums to 100, not 1
        result = compute_portfolio_returns(sample_prices, weights)
        assert isinstance(result, pd.Series)
        assert len(result) > 0

    def test_single_stock(self, sample_prices):
        single = sample_prices.iloc[:, :1]
        result = compute_portfolio_returns(single, [1.0])
        assert isinstance(result, pd.Series)
        assert len(result) > 0

    def test_empty_prices(self):
        empty = pd.DataFrame()
        result = compute_portfolio_returns(empty, [])
        assert len(result) == 0




class TestComputeMaxDrawdown:
    def test_drawdown_is_negative(self):
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        series = pd.Series(np.cumprod(1 + np.random.normal(0.001, 0.02, 252)), index=dates)
        result = compute_max_drawdown(series)
        assert result["max_drawdown"] <= 0

    def test_drawdown_from_dataframe(self, sample_prices):
        """Should accept DataFrame and use first column."""
        result = compute_max_drawdown(sample_prices)
        assert result["max_drawdown"] <= 0
        assert "start" in result
        assert "end" in result

    def test_max_drawdown_first_element_peak(self):
        """Max drawdown peak at first element should not raise IndexError."""
        prices = pd.Series([100, 95, 90, 85, 80], index=pd.date_range("2024-01-01", periods=5))
        result = compute_max_drawdown(prices)
        assert result["max_drawdown"] < 0

    def test_always_rising(self):
        """A monotonically increasing series should have 0 drawdown."""
        dates = pd.date_range(end="2024-01-01", periods=100, freq="B")
        series = pd.Series(np.linspace(100, 200, 100), index=dates)
        result = compute_max_drawdown(series)
        assert abs(result["max_drawdown"] - 0) < 0.01


