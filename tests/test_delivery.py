"""Tests for the delivery analysis module."""

from unittest.mock import patch

import pandas as pd

from engine.delivery import (
    DeliveryInfo,
    _compute_delivery,
    _fetch_bhavcopy_single,
    fetch_delivery_for_holdings,
)


class TestComputeDelivery:
    def test_valid_data_returns_delivery_info(self):
        df = pd.DataFrame(
            {
                "SYMBOL": ["RELIANCE"] * 5,
                "DELIV_QTY": [1000, 1200, 1100, 1300, 1400],
                "TOTTRDQTY": [5000, 6000, 5500, 6500, 7000],
            }
        )

        result = _compute_delivery(df)

        assert result is not None
        assert isinstance(result, DeliveryInfo)
        assert result.ticker == "RELIANCE"
        assert 0 < result.delivery_pct <= 100

    def test_insufficient_data_returns_none(self):
        """Less than 2 rows should return None (can't compute meaningful delivery)."""
        df = pd.DataFrame(
            {
                "SYMBOL": ["RELIANCE"],
                "DELIV_QTY": [1000],
                "TOTTRDQTY": [5000],
            }
        )

        result = _compute_delivery(df)

        assert result is None

    def test_zero_total_traded_returns_none(self):
        df = pd.DataFrame(
            {
                "SYMBOL": ["RELIANCE"] * 5,
                "DELIV_QTY": [1000, 1200, 1100, 1300, 1400],
                "TOTTRDQTY": [0, 0, 0, 0, 0],
            }
        )

        result = _compute_delivery(df)

        assert result is None

    def test_missing_columns_returns_none(self):
        df = pd.DataFrame(
            {
                "SYMBOL": ["RELIANCE"] * 5,
                "DELIV_QTY": [1000, 1200, 1100, 1300, 1400],
            }
        )

        result = _compute_delivery(df)

        assert result is None

    def test_delivery_pct_capped_at_100(self):
        df = pd.DataFrame(
            {
                "SYMBOL": ["RELIANCE"] * 5,
                "DELIV_QTY": [5000, 6000, 5500, 6500, 7000],
                "TOTTRDQTY": [5000, 6000, 5500, 6500, 7000],
            }
        )

        result = _compute_delivery(df)

        assert result is not None
        assert result.delivery_pct == 100.0

    def test_multiple_symbols_uses_first(self):
        df = pd.DataFrame(
            {
                "SYMBOL": ["RELIANCE"] * 3 + ["TCS"] * 2,
                "DELIV_QTY": [1000, 1200, 1100, 2000, 2200],
                "TOTTRDQTY": [5000, 6000, 5500, 10000, 11000],
            }
        )

        result = _compute_delivery(df)

        assert result is not None
        assert result.ticker == "RELIANCE"

    def test_trend_rising(self):
        """Test rising trend detection when recent delivery avg > earlier avg by >3%."""
        deliv = [1000 + i * 100 for i in range(15)]  # Rising
        total = [5000] * 15
        df = pd.DataFrame(
            {
                "SYMBOL": ["RELIANCE"] * 15,
                "DELIV_QTY": deliv,
                "TOTTRDQTY": total,
            }
        )

        result = _compute_delivery(df)

        assert result is not None
        assert result.delivery_trend == "rising"

    def test_trend_falling(self):
        """Test falling trend detection when recent delivery avg < earlier avg by >3%."""
        deliv = [2000 - i * 100 for i in range(15)]  # Falling
        total = [5000] * 15
        df = pd.DataFrame(
            {
                "SYMBOL": ["RELIANCE"] * 15,
                "DELIV_QTY": deliv,
                "TOTTRDQTY": total,
            }
        )

        result = _compute_delivery(df)

        assert result is not None
        assert result.delivery_trend == "falling"

    def test_trend_stable(self):
        """Test stable trend when diff within +/-3%."""
        deliv = [1000] * 15  # Constant
        total = [5000] * 15
        df = pd.DataFrame(
            {
                "SYMBOL": ["RELIANCE"] * 15,
                "DELIV_QTY": deliv,
                "TOTTRDQTY": total,
            }
        )

        result = _compute_delivery(df)

        assert result is not None
        assert result.delivery_trend == "stable"


class TestFetchBhavcopySingle:
    def test_returns_none_when_nselib_unavailable(self):
        with patch("engine.delivery._NSELIB_AVAILABLE", False):
            result = _fetch_bhavcopy_single("RELIANCE", "1M")
            assert result is None


class TestFetchDeliveryForHoldings:
    def test_returns_empty_when_nselib_unavailable(self):
        with patch("engine.delivery._NSELIB_AVAILABLE", False):
            result = fetch_delivery_for_holdings(["RELIANCE"], period="1M")
            assert result == {}

    def test_skips_tickers_with_no_data(self):
        with (
            patch("engine.delivery._NSELIB_AVAILABLE", True),
            patch("engine.delivery._fetch_bhavcopy_single") as mock_fetch,
        ):
            mock_fetch.return_value = None

            result = fetch_delivery_for_holdings(["RELIANCE", "TCS"], period="1M")

            assert result == {}

    def test_returns_delivery_info_when_data_available(self):
        with (
            patch("engine.delivery._NSELIB_AVAILABLE", True),
            patch("engine.delivery._fetch_bhavcopy_single") as mock_fetch,
        ):
            # Create mock bhavcopy data
            mock_data = pd.DataFrame(
                {
                    "SYMBOL": ["RELIANCE"] * 5,
                    "DELIV_QTY": [1000, 1200, 1100, 1300, 1400],
                    "TOTTRDQTY": [5000, 6000, 5500, 6500, 7000],
                    "DATE": pd.date_range(end="2024-01-15", periods=5, freq="B"),
                }
            )

            mock_fetch.return_value = mock_data

            result = fetch_delivery_for_holdings(["RELIANCE"], period="1M")

            assert "RELIANCE" in result
            assert isinstance(result["RELIANCE"], DeliveryInfo)
            assert result["RELIANCE"].ticker == "RELIANCE"

    def test_exception_in_fetch_is_caught(self):
        with (
            patch("engine.delivery._NSELIB_AVAILABLE", True),
            patch("engine.delivery._fetch_bhavcopy_single") as mock_fetch,
        ):
            mock_fetch.side_effect = Exception("Network error")

            result = fetch_delivery_for_holdings(["RELIANCE"], period="1M")

            assert result == {}
