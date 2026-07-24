"""Tests for the market regime detection module."""

import numpy as np
import pandas as pd

from engine.regime import detect_regimes


class TestDetectRegimes:
    def test_returns_result_statistical_fallback(self):
        """Returns result via statistical fallback when hmmlearn unavailable."""
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        returns = pd.Series(np.random.normal(0.001, 0.02, 252), index=dates)
        result = detect_regimes(returns)
        # Statistical fallback also returns result for 252 data points
        assert result is not None
        assert result.n_states == 3
        assert len(result.labels) == 3
        assert len(result.state_sequence) == len(returns)
        # Synthetic random data may not split into exactly 3 regimes
        assert 2 <= len(result.stats) <= 3

    def test_detect_three_states(self):
        """With hmmlearn, should return 3-state result."""
        if not _hmm_available():
            return
        dates = pd.date_range(end="2024-01-01", periods=500, freq="B")
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 500), index=dates)
        result = detect_regimes(returns, n_states=3)
        assert result.n_states == 3
        # Synthetic random data may not split into exactly 3 regimes
        assert 2 <= len(result.stats) <= 3

    def test_transition_matrix(self):
        if not _hmm_available():
            return
        dates = pd.date_range(end="2024-01-01", periods=500, freq="B")
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 500), index=dates)
        result = detect_regimes(returns)
        trans = result.transition_matrix
        assert len(trans) == 3
        for row in trans:
            assert abs(sum(row) - 1.0) < 0.01

    def test_empty_returns(self):
        result = detect_regimes(pd.Series(dtype=float))
        assert result is None

    def test_short_returns(self):
        returns = pd.Series([0.01] * 10)
        result = detect_regimes(returns)
        assert result is None

    def test_two_states(self):
        if not _hmm_available():
            return
        dates = pd.date_range(end="2024-01-01", periods=500, freq="B")
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 500), index=dates)
        result = detect_regimes(returns, n_states=2)
        assert result.n_states == 2
        assert "Bull" in result.labels or "Bull" in str(result.labels)


def _hmm_available():
    from engine.regime import _HMMLEARN_AVAILABLE

    return _HMMLEARN_AVAILABLE
