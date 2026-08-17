"""Tests for the portfolio optimization module."""

import numpy as np
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


class TestHardCap:
    """H1 fix: the per-position weight cap must be a TRUE hard cap.

    The previous redistribution leaked weight past the cap (2 assets + 0.35 cap
    produced [0.35, 0.65]). The cap is now a SLSQP bound plus an idempotent clamp.

    NOTE on feasibility: a cap c on n assets is only satisfiable if c >= 1/n
    (every weight <= c AND sum to 1 requires n*c >= 1). When c < 1/n the code
    degrades to equal weight — the closest feasible allocation — rather than
    silently leaking past the cap. Tests below use FEASIBLE caps.
    """

    def test_cap_binds_for_min_vol(self, sample_prices):
        # 5 synthetic assets, cap 0.30 is feasible (1/5 = 0.20 < 0.30).
        returns = sample_prices.pct_change().dropna()
        returns = returns.assign(ZZ=returns.iloc[:, 0] * 0.9 + returns.iloc[:, 1] * 0.1)
        result = optimize_min_volatility(returns, max_single_weight=0.30)
        assert max(result.weights.values()) <= 0.30 + 1e-6
        # Unconstrained min-vol would exceed 0.30 (proves the bound actually bites).
        unconstrained = optimize_min_volatility(returns)
        assert max(unconstrained.weights.values()) > 0.30 + 1e-6

    def test_cap_holds_for_hrp_and_sharpe(self, sample_prices):
        returns = sample_prices.pct_change().dropna()
        returns = returns.assign(ZZ=returns.iloc[:, 0] * 0.9 + returns.iloc[:, 1] * 0.1)
        for fn in (optimize_hrp, optimize_max_sharpe):
            result = fn(returns, max_single_weight=0.40)
            for w in result.weights.values():
                assert w <= 0.40 + 1e-6

    def test_cap_preserves_sum(self, sample_prices):
        returns = sample_prices.pct_change().dropna()
        returns = returns.assign(ZZ=returns.iloc[:, 0] * 0.9 + returns.iloc[:, 1] * 0.1)
        result = optimize_max_sharpe(returns, max_single_weight=0.25)
        assert abs(sum(result.weights.values()) - 1.0) < 1e-6

    def test_infeasible_cap_degrades_to_equal_weight(self):
        # 2 assets + 0.35 cap is impossible (2*0.35 < 1.0). Code must degrade
        # gracefully to equal weight, not leak past the cap.
        prices = pd.DataFrame(
            {
                "A.NS": 100 + np.arange(100) * 0.5,
                "B.NS": 100 + np.arange(100) * 0.3,
            }
        )
        returns = prices.pct_change().dropna()
        result = optimize_max_sharpe(returns, max_single_weight=0.35)
        weights = list(result.weights.values())
        for w in weights:
            assert abs(w - 0.5) < 1e-6  # equal weight
        assert abs(sum(weights) - 1.0) < 1e-6


class TestOptimizeAdvancedReceivesReturns:
    """Regression guard for the prices-vs-returns bug (fixed in compute.py).

    optimize_advanced() expects a *returns* DataFrame. compute_all must pass
    prices.pct_change().dropna(), never raw price levels. If it ever passes
    prices directly, the advanced optimizer silently returns None (or garbage),
    so we capture the argument and assert it is stationary (returns), not trending.
    """

    def test_compute_all_passes_returns_not_prices(self, sample_prices):
        from unittest.mock import patch

        from engine.compute import compute_all
        from engine.portfolio import portfolio_from_dict

        # Build a 2-holding portfolio matching sample_prices columns
        tickers = [c.replace(".NS", "") for c in sample_prices.columns]
        data = {
            "holdings": [
                {"ticker": t, "quantity": 10, "avg_price": 100.0} for t in tickers
            ]
        }
        portfolio = portfolio_from_dict(data)

        # compute_all drops holdings with current_price == 0; set a positive price
        for h in portfolio.holdings:
            h.current_price = 100.0

        captured = {}

        # Stub optimize_advanced to record its argument and return None
        def _spy(returns, method="CVaR", obj="Sharpe"):
            captured["arg"] = returns
            return None

        with patch("engine.compute.optimize_advanced", side_effect=_spy), patch(
            "engine.compute._fetch_prices", return_value=sample_prices
        ), patch(
            "engine.compute._fetch_benchmark",
            return_value=(None, pd.Series(dtype=float)),
        ):
            compute_all(portfolio, "^NSEI", "moderate", 0.065)

        assert "arg" in captured, "optimize_advanced was not called"
        arg = captured["arg"]
        # Returns are stationary (mean ~ 0), prices are trending (mean >> 0 slope).
        # Assert the passed frame is NOT raw prices: a price series has a strong
        # monotonic drift; returns do not. Check std is small relative to mean
        # for at least one column (returns have no unit scale like prices ~100).
        assert isinstance(arg, __import__("pandas").DataFrame)
        # Price levels here are ~100+; returns are fractional (|x| < 0.1 typically)
        assert arg.abs().max().max() < 1.0 + 1e-9, (
            f"optimize_advanced received price-like levels (max={arg.abs().max().max()}), "
            f"expected returns (fractional)"
        )
