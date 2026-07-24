"""Tests for Altman Z-Score bankruptcy prediction."""

from unittest.mock import MagicMock, patch

import pytest

from engine.fundamentals import (
    ZScoreResult,
    _classify_zone,
    compute_all_zscores,
    compute_zscore,
)


class TestClassifyZone:
    @pytest.mark.parametrize(
        "zscore,model,expected",
        [
            (3.5, "Original", "Safe"),
            (2.5, "Original", "Grey Zone"),
            (1.0, "Original", "Distress"),
            (3.0, "Original", "Safe"),
            (1.8, "Original", "Grey Zone"),
            (3.0, "Modified", "Safe"),
            (2.0, "Modified", "Grey Zone"),
            (0.5, "Modified", "Distress"),
        ],
    )
    def test_classify(self, zscore, model, expected):
        assert _classify_zone(zscore, model) == expected


class TestComputeZscore:
    def _mock_ticker(self, bs_data, info_data=None):
        """Create a mock yfinance Ticker."""
        mock = MagicMock()
        mock.info = info_data or {}
        mock_df = MagicMock()
        mock_df.empty = False
        if bs_data:
            # Simulate a real balance sheet DataFrame with columns as dates
            import pandas as pd

            dates = pd.date_range("2025-03-31", periods=1)
            df = pd.DataFrame(bs_data, index=dates).T
            mock_df.__getitem__ = lambda self, key: df
            # Override .loc to return first column
            mock_df.columns = dates
            mock_df.loc[:, mock_df.columns[0]] = pd.Series(bs_data)
            # Make .loc behave sensibly
            mock_df = df
        else:
            mock_df = bs_data  # pass through None/empty
        mock.balance_sheet = mock_df
        return mock

    @patch("yfinance.Ticker")
    def test_manufacturer_zscore(self, mock_ticker):
        """RELIANCE-like manufacturer should use Original formula."""
        bs = {
            "Total Assets": 1000000,
            "Total Current Assets": 500000,
            "Current Assets": 500000,
            "Total Current Liabilities": 200000,
            "Current Liabilities": 200000,
            "Total Liabilities Net Minority Interest": 600000,
            "Total Liabilities": 600000,
            "Retained Earnings": 300000,
            "Retained Earnings Total": 300000,
            "EBIT": 120000,
            "Operating Income": 120000,
            "Total Revenue": 800000,
            "Revenue": 800000,
        }
        info = {"longName": "Reliance Industries Ltd", "sector": "Energy", "marketCap": 1500000}
        mock = self._mock_ticker(bs, info)
        mock_ticker.return_value = mock

        result = compute_zscore("RELIANCE.NS")
        assert result is not None
        assert result.model == "Original"
        assert result.zone in ("Safe", "Grey Zone", "Distress")
        assert result.ticker == "RELIANCE.NS"

    @patch("yfinance.Ticker")
    def test_nonmanufacturer_zscore(self, mock_ticker):
        """Bank/financial should use Modified formula."""
        bs = {
            "Total Assets": 2000000,
            "Total Current Assets": 800000,
            "Current Assets": 800000,
            "Total Current Liabilities": 600000,
            "Current Liabilities": 600000,
            "Total Liabilities Net Minority Interest": 1500000,
            "Total Liabilities": 1500000,
            "Retained Earnings": 400000,
            "Retained Earnings Total": 400000,
            "EBIT": 100000,
            "Operating Income": 100000,
            "Total Revenue": 300000,
            "Revenue": 300000,
        }
        info = {"longName": "HDFC Bank Ltd", "sector": "Financial Services", "marketCap": 5000000}
        mock = self._mock_ticker(bs, info)
        mock_ticker.return_value = mock

        result = compute_zscore("HDFCBANK.NS")
        assert result is not None
        assert result.model == "Modified"
        assert result.ticker == "HDFCBANK.NS"

    @patch("yfinance.Ticker")
    def test_missing_balance_sheet_returns_none(self, mock_ticker):
        mock = MagicMock()
        mock.info = {}
        mock.balance_sheet = None
        mock_ticker.return_value = mock

        result = compute_zscore("FAKE.NS")
        assert result is None

    @patch("yfinance.Ticker")
    def test_empty_balance_sheet_returns_none(self, mock_ticker):
        import pandas as pd

        mock = MagicMock()
        mock.info = {}
        mock.balance_sheet = pd.DataFrame()
        mock_ticker.return_value = mock

        result = compute_zscore("FAKE.NS")
        assert result is None

    @patch("yfinance.Ticker")
    def test_zero_assets_returns_none(self, mock_ticker):
        bs = {"Total Assets": 0}
        mock = self._mock_ticker(bs, {})
        mock_ticker.return_value = mock

        result = compute_zscore("BAD.NS")
        assert result is None


class TestComputeAllZscores:
    @patch("yfinance.Ticker")
    def test_returns_list(self, mock_ticker):
        bs = {
            "Total Assets": 1000000,
            "Total Current Assets": 500000,
            "Current Assets": 500000,
            "Total Current Liabilities": 200000,
            "Current Liabilities": 200000,
            "Total Liabilities Net Minority Interest": 600000,
            "Total Liabilities": 600000,
            "Retained Earnings": 300000,
            "Retained Earnings Total": 300000,
            "EBIT": 120000,
            "Operating Income": 120000,
            "Total Revenue": 800000,
            "Revenue": 800000,
        }
        info = {"longName": "Test", "sector": "Technology", "marketCap": 1500000}
        mock = MagicMock()
        mock.info = info
        df = MagicMock()
        df.empty = False
        import pandas as pd

        dates = pd.date_range("2025-03-31", periods=1)
        df_actual = pd.DataFrame(bs, index=dates).T
        mock.balance_sheet = df_actual
        mock_ticker.return_value = mock

        results = compute_all_zscores(["TEST.NS", "FAKE.NS"])
        assert len(results) >= 1
        assert all(isinstance(r, ZScoreResult) for r in results)

    def test_empty_list(self):
        assert compute_all_zscores([]) == []
