"""Tests for the delivery analysis module."""

from unittest.mock import MagicMock, patch

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
        assert result.delivery_trend == "stable"

    def test_missing_columns_returns_none(self):
        df = pd.DataFrame({"random_col": [1, 2, 3]})

        result = _compute_delivery(df)

        assert result is None

    def test_zero_total_quantity_returns_none(self):
        df = pd.DataFrame(
            {
                "SYMBOL": ["RELIANCE"],
                "DELIV_QTY": [100],
                "TOTTRDQTY": [0],
            }
        )

        result = _compute_delivery(df)

        assert result is None

    def test_rising_delivery_trend(self):
        df = pd.DataFrame(
            {
                "SYMBOL": ["RELIANCE"] * 20,
                "DELIV_QTY": [100] * 10 + [500] * 10,
                "TOTTRDQTY": [1000] * 20,
            }
        )

        result = _compute_delivery(df)

        assert result is not None
        assert result.delivery_trend == "rising"


class TestFetchBhavcopySingle:
    @patch("engine.delivery._NSELIB_AVAILABLE", False)
    def test_returns_none_without_nselib(self):
        result = _fetch_bhavcopy_single("RELIANCE")

        assert result is None

    @patch("engine.delivery._NSELIB_AVAILABLE", True)
    @patch("engine.delivery.capital_market", create=True)
    def test_returns_filtered_ticker_data(self, mock_capital_market):
        mock_capital_market.bhav_copy_with_delivery.return_value = pd.DataFrame(
            {
                "SYMBOL": ["TCS", "RELIANCE", "RELIANCE"],
                "DATE": ["2026-01-03", "2026-01-02", "2026-01-01"],
                "DELIV_QTY": [100, 200, 300],
                "TOTTRDQTY": [1000, 1000, 1000],
            }
        )

        result = _fetch_bhavcopy_single("RELIANCE.NS", period="1M")

        assert result is not None
        assert result["SYMBOL"].tolist() == ["RELIANCE", "RELIANCE"]
        assert result["DATE"].is_monotonic_increasing
        mock_capital_market.bhav_copy_with_delivery.assert_called_once_with(
            period="1M"
        )

    @patch("engine.delivery._NSELIB_AVAILABLE", True)
    @patch("engine.delivery.capital_market", create=True)
    def test_returns_none_on_nselib_error(self, mock_capital_market):
        mock_capital_market.bhav_copy_with_delivery.side_effect = Exception(
            "API error"
        )

        result = _fetch_bhavcopy_single("RELIANCE")

        assert result is None

    @patch("engine.delivery._NSELIB_AVAILABLE", True)
    @patch("engine.delivery.capital_market", create=True)
    def test_returns_none_for_empty_data(self, mock_capital_market):
        mock_capital_market.bhav_copy_with_delivery.return_value = pd.DataFrame()

        result = _fetch_bhavcopy_single("RELIANCE")

        assert result is None


class TestFetchDeliveryForHoldings:
    @patch("engine.delivery._NSELIB_AVAILABLE", True)
    def test_empty_tickers_returns_empty_dict(self):
        result = fetch_delivery_for_holdings([])

        assert result == {}

    @patch("engine.delivery._NSELIB_AVAILABLE", True)
    @patch("engine.delivery._compute_delivery")
    @patch("engine.delivery._fetch_bhavcopy_single")
    def test_single_ticker_returns_delivery_info(
        self,
        mock_fetch,
        mock_compute,
    ):
        mock_fetch.return_value = pd.DataFrame(
            {
                "SYMBOL": ["RELIANCE"],
                "DELIV_QTY": [200],
                "TOTTRDQTY": [1000],
            }
        )
        expected = DeliveryInfo(
            ticker="RELIANCE",
            delivery_pct=20.0,
            delivery_trend="stable",
            avg_delivery=20.0,
        )
        mock_compute.return_value = expected

        result = fetch_delivery_for_holdings(["RELIANCE"], period="1M")

        assert result == {"RELIANCE": expected}
        mock_fetch.assert_called_once_with("RELIANCE", "1M")
        mock_compute.assert_called_once_with(mock_fetch.return_value)