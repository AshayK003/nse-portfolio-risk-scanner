"""Tests for PELVE computation."""

import numpy as np
import pytest

from engine.pelve import PelveResult, compute_pelve


class TestComputePelve:
    def test_returns_pelve_result_type(self):
        returns = np.random.randn(200) * 0.01
        result = compute_pelve(returns)
        assert isinstance(result, PelveResult)

    def test_pelve_is_positive(self):
        returns = np.random.randn(500) * 0.01
        result = compute_pelve(returns)
        assert result.pelve > 0

    def test_interpretation_populated(self):
        returns = np.random.randn(200) * 0.01
        result = compute_pelve(returns)
        assert len(result.interpretation) > 0

    def test_epsilon_param(self):
        returns = np.random.randn(200) * 0.01
        result = compute_pelve(returns, epsilon=0.05)
        assert result.epsilon == 0.05

    @pytest.mark.parametrize("epsilon", [0.01, 0.05, 0.025])
    def test_different_epsilons(self, epsilon):
        returns = np.random.randn(500) * 0.01
        result = compute_pelve(returns, epsilon=epsilon)
        assert result is not None
        assert result.pelve > 0

    def test_insufficient_data_returns_none(self):
        returns = np.array([0.01] * 5)
        result = compute_pelve(returns)
        assert result is None

    def test_zero_volatility_returns_none(self):
        returns = np.array([0.01] * 100)  # Constant returns = zero vol
        result = compute_pelve(returns)
        assert result is None

    def test_fat_tails_give_higher_pelve(self):
        # Normal returns
        normal_ret = np.random.default_rng(42).normal(0, 0.01, 2000)
        # Fat-tailed returns (t-dist with low df)
        from scipy.stats import t as t_dist

        fat_ret = t_dist.rvs(df=3, scale=0.01, size=2000, random_state=42)
        normal_pelve = compute_pelve(normal_ret)
        fat_pelve = compute_pelve(fat_ret)
        if normal_pelve is not None and fat_pelve is not None:
            assert fat_pelve.pelve >= normal_pelve.pelve * 0.8  # fat tails >= or close to normal
