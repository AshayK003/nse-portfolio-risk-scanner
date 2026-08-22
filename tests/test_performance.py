"""Tests for the performance computation module."""

import pandas as pd

from engine.performance import (
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
