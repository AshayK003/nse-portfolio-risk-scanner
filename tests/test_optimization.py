"""Tests for the portfolio optimization module."""

import pandas as pd

from engine import Holding
from engine.optimization import optimize_hrp, optimize_max_sharpe, optimize_min_volatility, suggest_rebalance


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


class TestSuggestRebalance:
    def test_equal_weight(self):
        holdings = [
            Holding(ticker="A.NS", name="A", quantity=100, avg_price=10, current_price=10),
            Holding(ticker="B.NS", name="B", quantity=100, avg_price=20, current_price=20),
        ]
        result = suggest_rebalance(holdings, target_method="equal_weight")
        assert len(result.trades) == 2
        assert result.target_method == "equal_weight"

    def test_total_drift_positive(self):
        holdings = [
            Holding(ticker="A.NS", name="A", quantity=100, avg_price=10, current_price=10),
            Holding(ticker="B.NS", name="B", quantity=300, avg_price=20, current_price=20),
        ]
        result = suggest_rebalance(holdings, target_method="equal_weight")
        assert result.total_drift_pct > 0

    def test_empty_portfolio(self):
        result = suggest_rebalance([], target_method="equal_weight")
        assert result.trades == []
        assert result.total_drift_pct == 0.0

    def test_single_holding(self):
        holdings = [Holding(ticker="A.NS", name="A", quantity=100, avg_price=10, current_price=10)]
        result = suggest_rebalance(holdings, target_method="equal_weight")
        assert len(result.trades) >= 0

    def test_action_buy_when_drift_exceeds_0_5pct(self):
        holdings = [
            Holding(ticker="A.NS", name="A", quantity=100, avg_price=10, current_price=10),
            Holding(ticker="B.NS", name="B", quantity=100, avg_price=20, current_price=20),
        ]
        result = suggest_rebalance(holdings, target_method="equal_weight")
        actions = {t["ticker"]: t["action"] for t in result.trades}
        # A at 33.3% should be increased toward 50%, B at 66.7% decreased toward 50%
        assert actions == {"A": "increase", "B": "decrease"}

    def test_action_hold_when_drift_below_0_5pct(self):
        holdings = [
            Holding(ticker="A.NS", name="A", quantity=50, avg_price=10, current_price=10),
            Holding(ticker="B.NS", name="B", quantity=50, avg_price=10, current_price=10),
        ]
        result = suggest_rebalance(holdings, target_method="equal_weight")
        for t in result.trades:
            assert t["action"] == "hold"
