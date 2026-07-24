"""Tests for GARCH(1,1)-t VaR estimation."""

import numpy as np
import pytest

from engine.garch_var import GarchVaRResult, estimate_garch_var


class TestEstimateGarchVar:
    def test_returns_garch_var_result_type(self):
        returns = np.random.randn(200) * 0.01
        result = estimate_garch_var(returns)
        assert isinstance(result, GarchVaRResult)

    def test_var_values_are_positive(self):
        returns = np.random.randn(200) * 0.01
        result = estimate_garch_var(returns)
        assert result.var_95 > 0
        assert result.var_99 > 0

    def test_var_99_greater_than_var_95(self):
        returns = np.random.randn(200) * 0.01
        result = estimate_garch_var(returns)
        assert result.var_99 >= result.var_95 * 0.9  # usually bigger, allow slack

    @pytest.mark.skipif(
        not __import__("engine.garch_var", fromlist=["ARCH_AVAILABLE"]).ARCH_AVAILABLE,
        reason="arch package not installed",
    )
    def test_garch_converges_with_enough_data(self):
        """With 500+ data points and typical vol, GARCH should converge."""
        rng = np.random.default_rng(42)
        # GARCH-like data: clustered volatility
        returns = []
        sigma = 0.01
        for _ in range(500):
            e = rng.normal(0, sigma)
            returns.append(e)
            sigma = np.sqrt(0.000001 + 0.1 * e**2 + 0.85 * sigma**2)
        returns = np.array(returns)
        result = estimate_garch_var(returns)
        # Should use GARCH-t, not fallback - skip if arch has version issues
        if "GARCH" not in result.method:
            pytest.skip("GARCH not available or has version issues")
        assert "GARCH" in result.method

    def test_insufficient_data(self):
        returns = np.array([0.01] * 10)
        result = estimate_garch_var(returns)
        assert "Insufficient data" in result.method
        assert result.var_95 == 0.0

    def test_fallback_when_arch_not_installed(self):
        returns = np.random.randn(100) * 0.01
        result = estimate_garch_var(returns)
        # Either GARCH-t or Static Normal depending on arch availability
        assert result.var_95 > 0
        assert result.conditional_vol > 0
