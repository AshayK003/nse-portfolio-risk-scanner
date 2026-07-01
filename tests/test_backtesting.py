"""Tests for Kupiec VaR backtesting."""

import numpy as np
import pytest

from engine.backtesting import KupiecResult, backtest_var, kupiec_pof


class TestKupiecPOF:
    def test_returns_kupiec_result_type(self):
        forecasts = np.array([0.02] * 100)
        returns = np.random.randn(100) * 0.01
        result = kupiec_pof(forecasts, returns)
        assert isinstance(result, KupiecResult)

    def test_zero_exceptions_when_var_always_holds(self):
        """If losses never exceed VaR, exceptions = 0."""
        forecasts = np.array([0.5] * 100)  # 50% VaR
        returns = np.array([-0.01] * 100)  # -1% returns
        result = kupiec_pof(forecasts, returns, confidence=0.95)
        # -1% > -50%, so VaR never breached
        assert result.exceptions == 0
        assert result.observations == 100

    def test_all_exceptions_when_var_always_breached(self):
        """If losses always exceed VaR, exceptions = n."""
        forecasts = np.array([0.001] * 100)  # 0.1% VaR
        returns = np.array([-0.05] * 100)    # -5% returns
        result = kupiec_pof(forecasts, returns, confidence=0.95)
        assert result.exceptions == 100

    def test_exception_rate_approaches_expected_with_good_model(self):
        """With a sufficiently large sample, actual rate ~ expected."""
        rng = np.random.default_rng(42)
        n = 2000
        confidence = 0.95
        p = 1 - confidence
        sigma = 0.01
        # Generate normal returns
        returns = rng.normal(0, sigma, n)
        # VaR at correct level
        from scipy.stats import norm
        var_forecasts = np.full(n, sigma * norm.ppf(confidence))
        result = kupiec_pof(var_forecasts, returns, confidence=confidence)
        # Expected ~ n * p = 100
        assert abs(result.exceptions - n * p) < 60  # generous tolerance

    def test_zero_observations(self):
        result = kupiec_pof(np.array([]), np.array([]))
        assert result.observations == 0
        assert result.passed is True

    def test_mismatched_length_raises(self):
        with pytest.raises(ValueError):
            kupiec_pof(np.array([0.02] * 10), np.array([0.01] * 5))

    def test_multiple_confidences(self):
        forecasts = np.array([0.02] * 500)
        rng = np.random.default_rng(42)
        returns = rng.normal(0, 0.01, 500)
        results = backtest_var(forecasts, returns, confidences=[0.95, 0.99])
        assert len(results) == 2
        assert results[0].confidence == 0.95
        assert results[1].confidence == 0.99


class TestEdgeCases:
    def test_variance_handles_barely_positive_forecasts(self):
        forecasts = np.array([1e-6] * 100)
        returns = np.array([0.0] * 100)
        # Should not crash with near-zero values
        result = kupiec_pof(forecasts, returns)
        assert result.observations == 100
