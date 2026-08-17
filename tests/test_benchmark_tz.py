"""Tests for benchmark reliability on deploy environments.

Two real defects surfaced on Streamlit Cloud:
1. fetch_benchmark() returned a tz-aware index while equity prices are
   tz-naive -> the inner-join in compare_to_benchmark yielded 0 overlapping
   rows -> _empty_comparison() (all zeros, beta=1.0) silently shown to investors.
2. compare_to_benchmark must never emit all-zero fake metrics when the
   benchmark data is unavailable; it should signal "no data".

These tests pin the correct behaviour so the bugs cannot silently return.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.benchmark import compare_to_benchmark


def _series(values, index, name, tz=None):
    idx = pd.DatetimeIndex(index, tz=tz) if tz else pd.DatetimeIndex(index)
    return pd.Series(values, index=idx, name=name)


class TestBenchmarkTimezoneAlignment:
    """Portfolio prices are tz-naive; benchmark from yfinance is tz-aware.
    They must still align on date."""

    def test_tz_aware_benchmark_aligns_with_naive_portfolio(self):
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        # Equity returns are tz-naive (as produced by fetch_prices)
        port = pd.Series(np.random.normal(0.0008, 0.015, 252), index=dates, name="portfolio")
        # Benchmark returns arrive tz-aware (as produced by fetch_benchmark on some envs)
        bench = _series(
            np.random.normal(0.0005, 0.01, 252), dates, name="benchmark", tz="Asia/Kolkata"
        )
        result = compare_to_benchmark(port, bench)
        # Must NOT be the silent all-zero placeholder
        assert result.total_months > 0
        assert result.tracking_error != 0.0
        assert result.correlation != 0.0

    def test_tz_mismatch_still_produces_real_metrics_not_zeros(self):
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        port = pd.Series(np.random.normal(0.0008, 0.015, 252), index=dates, name="portfolio")
        bench = _series(
            np.random.normal(0.0005, 0.01, 252), dates, name="benchmark", tz="UTC"
        )
        result = compare_to_benchmark(port, bench)
        assert result.total_months > 0
        assert result.portfolio_return != 0.0 or result.benchmark_return != 0.0


class TestCompareToBenchmarkSignalsMissingData:
    """When genuinely no data overlaps, the result must be detectable as
    'no data' rather than indistinguishable all-zero metrics."""

    def test_no_overlap_yields_zero_overlap_flag_not_fake_metrics(self):
        port_dates = pd.date_range("2023-01-01", periods=50, freq="B")
        bench_dates = pd.date_range("2024-06-01", periods=50, freq="B")
        port = pd.Series(np.random.normal(0.001, 0.01, 50), index=port_dates, name="portfolio")
        bench = pd.Series(np.random.normal(0.001, 0.01, 50), index=bench_dates, name="benchmark")
        result = compare_to_benchmark(port, bench)
        # No overlapping dates -> comparison is undefined
        assert result is None or result.total_months == 0
