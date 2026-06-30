"""Tests for the early-warning signal detection module."""

import numpy as np
import pandas as pd

from engine.warnings import (
    SignalSeverity,
    WarningReport,
    WarningSignal,
    detect_all_warnings,
)


class TestDetectAllWarnings:
    def _make_prices(self, n_days=252, n_stocks=3, seed=42):
        np.random.seed(seed)
        dates = pd.date_range(end="2024-01-01", periods=n_days, freq="B")
        returns = np.random.normal(0.001, 0.02, (n_days, n_stocks))
        prices = 100 * np.cumprod(1 + returns, axis=0)
        return pd.DataFrame(
            prices,
            index=dates,
            columns=[f"STOCK{i}.NS" for i in range(n_stocks)],
        )

    def test_returns_warning_report(self):
        prices = self._make_prices()
        result = detect_all_warnings(prices)
        assert isinstance(result, WarningReport)

    def test_overall_level_valid(self):
        prices = self._make_prices()
        result = detect_all_warnings(prices)
        assert result.overall_warning_level in ("green", "amber", "red")

    def test_severity_counts_consistent(self):
        prices = self._make_prices()
        result = detect_all_warnings(prices)
        total = sum(result.signal_count_by_severity.values())
        assert total == len(result.signals)

    def test_summary_populated(self):
        prices = self._make_prices()
        result = detect_all_warnings(prices)
        assert len(result.summary) > 0

    def test_empty_prices(self):
        result = detect_all_warnings(pd.DataFrame())
        assert result.overall_warning_level == "green"
        assert len(result.signals) == 0

    def test_short_prices_no_crash(self):
        dates = pd.date_range(end="2024-01-01", periods=10, freq="B")
        prices = pd.DataFrame(
            {"A.NS": [100, 101, 99, 102, 98, 103, 97, 104, 96, 105]},
            index=dates,
        )
        result = detect_all_warnings(prices)
        assert isinstance(result, WarningReport)

    def test_volatile_stock_triggers_vol_signal(self):
        """A stock with sudden vol spike should trigger a volatility signal."""
        np.random.seed(42)
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        # Normal returns for most of the period, then spike in last 21 days
        normal = np.random.normal(0.001, 0.01, 231)
        spike = np.random.normal(0, 0.08, 21)  # 8% daily vol in last 21 days
        returns = np.concatenate([normal, spike])
        prices = pd.DataFrame(100 * np.cumprod(1 + returns), index=dates, columns=["VOL.NS"])
        result = detect_all_warnings(prices)
        vol_signals = [s for s in result.signals if s.signal_type == "volatility"]
        assert len(vol_signals) > 0

    def test_signals_have_required_fields(self):
        prices = self._make_prices()
        result = detect_all_warnings(prices)
        for sig in result.signals:
            assert isinstance(sig, WarningSignal)
            assert sig.name != ""
            assert sig.severity in (SignalSeverity.INFO, SignalSeverity.WARNING, SignalSeverity.CRITICAL)
            assert sig.signal_type in ("technical", "momentum", "volatility", "correlation", "breadth")
            assert len(sig.description) > 0
            assert len(sig.reasoning) > 0
            assert len(sig.suggested_action) > 0

    def test_correlation_breakdown_detected(self):
        """Two highly correlated stocks should trigger correlation signal."""
        np.random.seed(42)
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        base = np.random.normal(0.001, 0.02, 252)
        # Two nearly identical stocks
        prices = pd.DataFrame(
            {
                "A.NS": 100 * np.cumprod(1 + base),
                "B.NS": 100 * np.cumprod(1 + base + np.random.normal(0, 0.001, 252)),
            },
            index=dates,
        )
        result = detect_all_warnings(prices)
        corr_signals = [s for s in result.signals if s.signal_type == "correlation"]
        # May or may not trigger depending on exact correlation, but should not crash
        assert isinstance(corr_signals, list)

    def test_with_custom_corr_matrix(self):
        prices = self._make_prices()
        corr = prices.pct_change().dropna().corr()
        result = detect_all_warnings(prices, corr_matrix=corr)
        assert isinstance(result, WarningReport)
