"""Tests for the price fetching module — retry logic and parallel fetch."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.prices import _fetch_with_retry, fetch_prices
from engine import Holding


def _make_price_df(values: list[float] | None = None) -> pd.DataFrame:
    """Create a minimal price DataFrame for testing."""
    if values is None:
        values = [100.0, 101.0, 102.0]
    dates = pd.bdate_range(end="2024-01-01", periods=len(values))
    return pd.DataFrame({"Close": values}, index=dates)


class TestFetchWithRetry:
    @patch("data.prices._cached_fetch")
    def test_success_on_first_attempt(self, mock_fetch):
        expected = _make_price_df()
        mock_fetch.return_value = expected

        ticker, df = _fetch_with_retry("RELIANCE.NS", "1y")

        assert ticker == "RELIANCE.NS"
        assert df is not None
        assert mock_fetch.call_count == 1

    @patch("data.prices.time.sleep")
    @patch("data.prices._cached_fetch")
    def test_retries_on_empty_result(self, mock_fetch, mock_sleep):
        empty_df = pd.DataFrame()
        success_df = _make_price_df()
        mock_fetch.side_effect = [empty_df, empty_df, success_df]

        ticker, df = _fetch_with_retry("TCS.NS", "1y")

        assert ticker == "TCS.NS"
        assert df is not None
        assert mock_fetch.call_count == 3
        assert mock_sleep.call_count == 2  # slept between retries

    @patch("data.prices.time.sleep")
    @patch("data.prices._cached_fetch")
    def test_returns_none_after_all_retries_fail(self, mock_fetch, mock_sleep):
        mock_fetch.return_value = None

        ticker, df = _fetch_with_retry("BADTICKER.NS", "1y")

        assert ticker == "BADTICKER.NS"
        assert df is None
        assert mock_fetch.call_count == 3

    @patch("data.prices.time.sleep")
    @patch("data.prices._cached_fetch")
    def test_retries_on_exception(self, mock_fetch, mock_sleep):
        success_df = _make_price_df()
        mock_fetch.side_effect = [ConnectionError("timeout"), success_df]

        ticker, df = _fetch_with_retry("INFY.NS", "1y")

        assert ticker == "INFY.NS"
        assert df is not None
        assert mock_fetch.call_count == 2

    @patch("data.prices.time.sleep")
    @patch("data.prices._cached_fetch")
    def test_backoff_timing(self, mock_fetch, mock_sleep):
        mock_fetch.return_value = None

        _fetch_with_retry("TEST.NS", "1y")

        # Should have slept with increasing backoff: 0.5, 1.5
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(0.5)
        mock_sleep.assert_any_call(1.5)


class TestFetchPricesParallel:
    @patch("data.prices._fetch_with_retry")
    def test_parallel_fetch_collects_results(self, mock_retry):
        holdings = [
            Holding(ticker="A.NS", name="A", quantity=10, avg_price=100),
            Holding(ticker="B.NS", name="B", quantity=5, avg_price=200),
        ]
        mock_retry.side_effect = [
            ("A.NS", _make_price_df([100.0, 101.0])),
            ("B.NS", _make_price_df([200.0, 202.0])),
        ]

        prices = fetch_prices(holdings, period="1y")

        assert "A.NS" in prices.columns
        assert "B.NS" in prices.columns
        assert len(prices) == 2

    @patch("data.prices._fetch_with_retry")
    def test_partial_failure_still_returns_data(self, mock_retry):
        holdings = [
            Holding(ticker="GOOD.NS", name="Good", quantity=10, avg_price=100),
            Holding(ticker="BAD.NS", name="Bad", quantity=5, avg_price=200),
        ]
        mock_retry.side_effect = [
            ("GOOD.NS", _make_price_df([100.0, 101.0])),
            ("BAD.NS", None),
        ]

        prices = fetch_prices(holdings, period="1y")

        assert "GOOD.NS" in prices.columns
        assert "BAD.NS" not in prices.columns

    @patch("data.prices._fetch_with_retry")
    def test_updates_holding_current_price(self, mock_retry):
        holdings = [
            Holding(ticker="A.NS", name="A", quantity=10, avg_price=100),
        ]
        mock_retry.return_value = ("A.NS", _make_price_df([100.0, 101.0, 102.0]))

        fetch_prices(holdings, period="1y")

        assert holdings[0].current_price == 102.0
        # total change from avg_price=100 to current_price=102 -> +2.00%
        assert holdings[0].change_pct == pytest.approx(2.00, abs=0.01)

    def test_empty_holdings_returns_empty(self):
        prices = fetch_prices([], period="1y")
        assert prices.empty

    @patch("data.prices._fetch_with_retry")
    def test_all_failures_raises_valueerror(self, mock_retry):
        holdings = [
            Holding(ticker="A.NS", name="A", quantity=10, avg_price=100),
            Holding(ticker="B.NS", name="B", quantity=5, avg_price=200),
        ]
        mock_retry.return_value = ("X.NS", None)

        with pytest.raises(ValueError, match="Could not fetch prices"):
            fetch_prices(holdings, period="1y")

    @patch("data.prices._fetch_with_retry")
    def test_progress_callback_called(self, mock_retry):
        mock_retry.return_value = ("A.NS", _make_price_df())
        holdings = [Holding(ticker="A.NS", name="A", quantity=10, avg_price=100)]
        callback = MagicMock()

        fetch_prices(holdings, period="1y", progress_callback=callback)

        assert callback.call_count >= 1
