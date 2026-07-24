"""Tests for the risk computation module."""

import numpy as np
import pandas as pd

from engine import RiskMetrics
from engine.risk import (
    compute_correlation_matrix,
    compute_risk_metrics,
    compute_stock_risk,
    denoise_correlation,
    monte_carlo_simulation,
    rolling_volatility,
)


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
        portfolio_returns = sample_prices.pct_change().dropna().dot(np.array(weights))
        bench = portfolio_returns * 0.8 + pd.Series(
            np.random.normal(0.0, 0.002, len(portfolio_returns)),
            index=portfolio_returns.index,
        )
        result = compute_risk_metrics(sample_prices, weights, benchmark_returns=bench)
        assert isinstance(result.beta, float)
        assert result.beta > 0

    def test_all_zero_prices(self):
        """All prices identical -> zero volatility, zero returns."""
        dates = pd.date_range(end="2024-01-01", periods=10, freq="B")
        prices = pd.DataFrame(
            {"A.NS": [100.0] * 10, "B.NS": [100.0] * 10},
            index=dates,
        )
        result = compute_risk_metrics(prices, [0.5, 0.5])
        assert result.volatility_annual == 0.0
        assert result.var_95 == 0.0

    def test_empty_weights(self):
        dates = pd.date_range(end="2024-01-01", periods=10, freq="B")
        prices = pd.DataFrame({"A.NS": [100.0] * 10}, index=dates)
        result = compute_risk_metrics(prices, [])
        assert result.volatility_annual == 0.0

    def test_drawdown_dates_populated(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        result = compute_risk_metrics(sample_prices, weights)
        assert result.max_drawdown_start != ""
        assert result.max_drawdown_end != ""

    def test_cagr_and_total_return(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        result = compute_risk_metrics(sample_prices, weights)
        assert isinstance(result.cagr, float)
        assert isinstance(result.total_return, float)


class TestComputeStockRisk:
    def test_returns_dict(self):
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252), index=dates)
        result = compute_stock_risk(returns)
        assert "volatility" in result
        assert "var_95" in result
        assert "max_drawdown" in result

    def test_volatility_positive(self):
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252), index=dates)
        result = compute_stock_risk(returns)
        assert result["volatility"] > 0

    def test_max_drawdown_negative(self):
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252), index=dates)
        result = compute_stock_risk(returns)
        assert result["max_drawdown"] <= 0


class TestRollingVolatility:
    def test_returns_series(self):
        dates = pd.date_range(end="2024-01-01", periods=100, freq="B")
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 100), index=dates)
        result = rolling_volatility(returns)
        assert isinstance(result, pd.Series)
        assert len(result) == 100

    def test_first_window_is_nan(self):
        dates = pd.date_range(end="2024-01-01", periods=50, freq="B")
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 50), index=dates)
        result = rolling_volatility(returns, window=21)
        assert pd.isna(result.iloc[0])
        assert not pd.isna(result.iloc[21])

    def test_custom_window(self):
        dates = pd.date_range(end="2024-01-01", periods=60, freq="B")
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 60), index=dates)
        result = rolling_volatility(returns, window=10)
        assert not pd.isna(result.iloc[10])

    def test_short_series(self):
        dates = pd.date_range(end="2024-01-01", periods=5, freq="B")
        returns = pd.Series([0.01, -0.01, 0.02, -0.02, 0.01], index=dates)
        result = rolling_volatility(returns, window=21)
        # All NaN since series shorter than window
        assert result.isna().all()


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


class TestMonteCarloSimulation:
    def test_returns_result(self):
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252), index=dates)
        result = monte_carlo_simulation(returns, n_simulations=1000, horizon_days=252)
        assert result.n_simulations == 1000
        assert isinstance(result.expected_return, float)
        assert isinstance(result.prob_profit, float)

    def test_ci_bounds(self):
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252), index=dates)
        result = monte_carlo_simulation(returns, n_simulations=1000, horizon_days=252)
        assert result.ci_lower <= result.ci_upper

    def test_var_negative(self):
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252), index=dates)
        result = monte_carlo_simulation(returns, n_simulations=1000, horizon_days=252)
        assert result.var_95 < 0

    def test_empty_returns(self):
        result = monte_carlo_simulation(pd.Series(dtype=float))
        assert result.expected_return == 0.0

    def test_prob_profit_range(self):
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252), index=dates)
        result = monte_carlo_simulation(returns, n_simulations=1000, horizon_days=252)
        assert 0 <= result.prob_profit <= 100


class TestDenoiseCorrelation:
    def test_returns_dataframe(self, sample_prices):
        corr = sample_prices.pct_change().dropna().corr()
        result = denoise_correlation(corr, len(sample_prices))
        assert isinstance(result, pd.DataFrame)
        assert result.shape == corr.shape

    def test_diagonal_ones(self, sample_prices):
        corr = sample_prices.pct_change().dropna().corr()
        result = denoise_correlation(corr, len(sample_prices))
        for i in range(result.shape[0]):
            assert abs(result.iloc[i, i] - 1.0) < 0.01

    def test_symmetric(self, sample_prices):
        corr = sample_prices.pct_change().dropna().corr()
        result = denoise_correlation(corr, len(sample_prices))
        for i in range(result.shape[0]):
            for j in range(result.shape[1]):
                assert abs(result.iloc[i, j] - result.iloc[j, i]) < 0.01

    def test_empty_corr(self):
        result = denoise_correlation(pd.DataFrame(), 100)
        assert result.empty

    def test_single_asset(self):
        import pandas as pd

        corr = pd.DataFrame({"A": [1.0]})
        result = denoise_correlation(corr, 100)
        assert abs(result.iloc[0, 0] - 1.0) < 0.01


class TestStockRiskAttribution:
    def test_returns_correct_columns(self, sample_prices):
        from engine.risk import compute_stock_risk_attribution

        weights = [0.4, 0.3, 0.3]
        df = compute_stock_risk_attribution(sample_prices, weights)
        assert not df.empty
        expected = {
            "Ticker",
            "Weight (%)",
            "Beta",
            "Ann. Vol (%)",
            "Avg Corr",
            "MRC",
            "Risk Contrib (%)",
            "VaR 95%",
        }
        assert set(df.columns) >= expected
        assert len(df) == 3

    def test_weights_normalised(self, sample_prices):
        from engine.risk import compute_stock_risk_attribution

        weights = [40, 30, 30]  # not normalised
        df = compute_stock_risk_attribution(sample_prices, weights)
        assert not df.empty
        total_weight = df["Weight (%)"].sum()
        assert abs(total_weight - 100.0) < 1.0

    def test_risk_contributions_sum_to_100(self, sample_prices):
        from engine.risk import compute_stock_risk_attribution

        weights = [0.4, 0.3, 0.3]
        df = compute_stock_risk_attribution(sample_prices, weights)
        assert not df.empty
        total = df["Risk Contrib (%)"].sum()
        assert abs(total - 100.0) < 1.0

    def test_empty_returns_empty(self):
        from engine.risk import compute_stock_risk_attribution

        df = compute_stock_risk_attribution(pd.DataFrame(), [])
        assert df.empty

    def test_with_betas(self, sample_prices):
        from engine.risk import compute_stock_risk_attribution

        tickers = sample_prices.columns.tolist()
        weights = [0.4, 0.3, 0.3]
        betas = {t: 1.2 for t in tickers}
        df = compute_stock_risk_attribution(sample_prices, weights, stock_betas=betas)
        assert not df.empty
        assert all(df["Beta"] == 1.2)
