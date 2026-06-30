"""Tests for the performance computation module."""

import numpy as np
import pandas as pd

from engine import Holding
from engine.performance import (
    compute_holding_returns,
    compute_max_drawdown,
    compute_portfolio_returns,
    compute_total_return,
    compute_win_rate,
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


class TestComputeTotalReturn:
    def test_total_return(self):
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        returns = pd.Series(np.random.normal(0.001, 0.02, 252), index=dates)
        result = compute_total_return(returns)
        assert "total" in result
        assert isinstance(result["total"], float)

    def test_period_returns(self):
        dates = pd.date_range(end="2024-01-01", periods=300, freq="B")
        returns = pd.Series(np.random.normal(0.001, 0.02, 300), index=dates)
        result = compute_total_return(returns)
        # With 300 trading days, should have at least 1m, 3m, 6m
        assert "1m" in result
        assert "3m" in result

    def test_short_history(self):
        dates = pd.date_range(end="2024-01-01", periods=10, freq="B")
        returns = pd.Series(np.random.normal(0.001, 0.02, 10), index=dates)
        result = compute_total_return(returns)
        assert "total" in result
        # Should not have period returns for very short history
        assert "1y" not in result


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


class TestComputeWinRate:
    def test_win_rate_bounds(self):
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        returns = pd.Series(np.random.normal(0.001, 0.02, 252), index=dates)
        result = compute_win_rate(returns)
        assert 0 <= result["win_rate"] <= 100
        assert 0 <= result["loss_rate"] <= 100
        assert result["total_days"] == 252

    def test_all_positive(self):
        returns = pd.Series(np.full(100, 0.01))
        result = compute_win_rate(returns)
        assert result["win_rate"] == 100.0
        assert result["loss_rate"] == 0.0

    def test_empty_series(self):
        result = compute_win_rate(pd.Series(dtype=float))
        assert result["win_rate"] == 0
        assert result["total_days"] == 0


class TestComputeHoldingReturns:
    def test_returns_dataframe(self):
        holdings = [
            Holding(
                ticker="RELIANCE.NS",
                name="RIL",
                quantity=10,
                avg_price=2500,
                current_price=2600,
                sector="Oil & Gas",
            ),
            Holding(ticker="TCS.NS", name="TCS", quantity=5, avg_price=3500, current_price=3400, sector="IT"),
        ]
        df = compute_holding_returns(holdings)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "ticker" in df.columns
        assert "pnl_pct" in df.columns

    def test_weight_calculation(self):
        holdings = [
            Holding(ticker="STOCK_A", name="Stock A", quantity=100, avg_price=10, current_price=10),
            Holding(ticker="STOCK_B", name="Stock B", quantity=100, avg_price=10, current_price=30),
        ]
        df = compute_holding_returns(holdings)
        # Stock B should have 75% weight (3000/4000)
        weight_b = df[df["ticker"] == "STOCK_B"]["weight_pct"].values[0]
        assert abs(weight_b - 75.0) < 1.0

    def test_empty_holdings(self):
        df = compute_holding_returns([])
        assert len(df) == 0
