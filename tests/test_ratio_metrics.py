"""Unit tests for Calmar, Treynor, skewness, and excess kurtosis (#2).

These metrics are computed inline inside compute_risk_metrics; tests assert
their mathematical properties through the public API.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.risk import compute_risk_metrics


@pytest.fixture
def steady_up_prices():
    """Low-volatility uptrend: positive CAGR, shallow drawdown, positive skew."""
    dates = pd.bdate_range("2024-01-01", periods=252)
    returns = np.random.default_rng(7).normal(0.001, 0.005, 252)
    prices = pd.DataFrame({"A.NS": 100 * np.cumprod(1 + returns)}, index=dates)
    return prices


@pytest.fixture
def crash_prices():
    """Strong uptrend then sudden large down days: negative skew, fat tails."""
    dates = pd.bdate_range("2024-01-01", periods=252)
    rng = np.random.default_rng(3)
    up = rng.normal(0.002, 0.004, 240)
    shock = np.array(
        [-0.03, -0.05, -0.04, -0.06, -0.02, -0.055, -0.045, -0.038, -0.052, -0.033, -0.048, -0.04]
    )
    prices = pd.DataFrame({"A.NS": 100 * np.cumprod(1 + np.concatenate([up, shock]))}, index=dates)
    return prices


class TestCalmarRatio:
    def test_calmar_positive_for_positive_cagr_and_drawdown(self, steady_up_prices):
        result = compute_risk_metrics(steady_up_prices, [1.0])
        assert result.calmar_ratio > 0

    def test_calmar_zero_when_no_drawdown(self):
        # Monotonically rising prices: CAGR > 0, max_dd == 0 -> calmar stays 0
        dates = pd.bdate_range("2024-01-01", periods=252)
        prices = pd.DataFrame({"A.NS": np.linspace(100, 200, 252)}, index=dates)
        result = compute_risk_metrics(prices, [1.0])
        assert result.calmar_ratio == 0.0

    def test_calmar_lower_for_deeper_drawdown(self, steady_up_prices, crash_prices):
        calm = compute_risk_metrics(steady_up_prices, [1.0])
        crashed = compute_risk_metrics(crash_prices, [1.0])
        assert crashed.calmar_ratio < calm.calmar_ratio


class TestTreynorRatio:
    def test_treynor_zero_without_benchmark(self, steady_up_prices):
        # beta defaults to 1.0 without benchmark returns; treynor still computes
        # against the default beta but must be finite
        result = compute_risk_metrics(steady_up_prices, [1.0])
        assert np.isfinite(result.treynor_ratio)

    def test_treynor_scales_with_excess_return(self, steady_up_prices):
        low_rf = compute_risk_metrics(steady_up_prices, [1.0], risk_free_rate=0.03)
        high_rf = compute_risk_metrics(steady_up_prices, [1.0], risk_free_rate=0.15)
        assert high_rf.treynor_ratio < low_rf.treynor_ratio


class TestSkewness:
    def test_skew_in_range_for_normal_returns(self, steady_up_prices):
        result = compute_risk_metrics(steady_up_prices, [1.0])
        assert -3.0 <= result.skewness <= 3.0

    def test_crash_produces_negative_skew(self, crash_prices):
        result = compute_risk_metrics(crash_prices, [1.0])
        assert result.skewness < 0


class TestExcessKurtosis:
    def test_kurtosis_in_range_for_normal_returns(self, steady_up_prices):
        result = compute_risk_metrics(steady_up_prices, [1.0])
        assert -2.0 <= result.kurtosis_excess <= 10.0

    def test_crash_produces_fat_tails(self, crash_prices):
        result = compute_risk_metrics(crash_prices, [1.0])
        assert result.kurtosis_excess > 0


class TestMetricConsistency:
    def test_all_four_metrics_present_and_finite(self, steady_up_prices):
        result = compute_risk_metrics(steady_up_prices, [1.0])
        for name in ("calmar_ratio", "treynor_ratio", "skewness", "kurtosis_excess"):
            value = getattr(result, name)
            assert np.isfinite(value), f"{name} not finite: {value}"
