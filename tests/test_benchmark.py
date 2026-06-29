"""Tests for benchmark comparison module."""
import pytest
import numpy as np
import pandas as pd
from engine import BenchmarkComparison
from engine.benchmark import compare_to_benchmark


class TestCompareToBenchmark:
    @pytest.fixture
    def return_series(self):
        np.random.seed(42)
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        port = pd.Series(np.random.normal(0.0008, 0.015, 252), index=dates)
        bench = pd.Series(np.random.normal(0.0005, 0.01, 252), index=dates)
        return port, bench
    
    def test_returns_correct_type(self, return_series):
        port, bench = return_series
        result = compare_to_benchmark(port, bench)
        assert isinstance(result, BenchmarkComparison)
    
    def test_alpha_calculation(self, return_series):
        port, bench = return_series
        result = compare_to_benchmark(port, bench)
        assert isinstance(result.alpha, float)
        # Beta should be positive (both are correlated by construction)
        assert result.beta > 0
    
    def test_tracking_error_positive(self, return_series):
        port, bench = return_series
        result = compare_to_benchmark(port, bench)
        assert result.tracking_error > 0
    
    def test_empty_series(self):
        empty_port = pd.Series(dtype=float)
        empty_bench = pd.Series(dtype=float)
        result = compare_to_benchmark(empty_port, empty_bench)
        assert result.beta == 1.0  # default
    
    def test_identical_series(self):
        dates = pd.date_range(end="2024-01-01", periods=100, freq="B")
        s = pd.Series(np.random.normal(0.001, 0.01, 100), index=dates)
        result = compare_to_benchmark(s, s)
        assert result.beta == 1.0  # same thing
        assert result.alpha == 0.0  # no excess return
        assert result.tracking_error == 0.0  # no tracking error
        assert result.correlation > 0.99
    
    def test_outperformance_months(self):
        """When portfolio returns are artificially higher every month."""
        dates = pd.date_range(end="2024-01-01", periods=504, freq="B")  # ~2 years
        port = pd.Series(np.random.normal(0.002, 0.015, 504), index=dates)
        bench = pd.Series(np.random.normal(0.001, 0.015, 504), index=dates)
        result = compare_to_benchmark(port, bench)
        # Portfolio has higher mean return -> should outperform in most months
        assert result.outperformance_months > 0
