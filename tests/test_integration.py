"""Integration tests — full pipeline from CSV to risk report.

All network calls are mocked. These tests verify that the layers
(engine, data, storage) work together without exceptions.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd

from engine import AnalysisReport, Holding, Portfolio
from engine.benchmark import compare_to_benchmark
from engine.performance import compute_portfolio_returns
from engine.portfolio import parse_portfolio_csv, validate_portfolio
from engine.risk import compute_correlation_matrix, compute_risk_metrics
from engine.sector import classify_holdings, compute_sector_exposure, load_sector_map


def _make_mock_prices(tickers: list[str], periods: int = 252) -> pd.DataFrame:
    """Create synthetic price data that mimics yfinance output."""
    np.random.seed(42)
    dates = pd.bdate_range(end="2024-01-01", periods=periods)
    data = {}
    for ticker in tickers:
        returns = np.random.normal(0.0008, 0.015, periods)
        data[ticker] = 100 * np.cumprod(1 + returns)
    return pd.DataFrame(data, index=dates)


def _mock_fetch_prices(holdings, period="1y", force_refresh=False, progress_callback=None):
    """Mock fetch_prices that returns synthetic data instead of hitting yfinance."""
    tickers = [h.ticker for h in holdings]
    prices = _make_mock_prices(tickers)
    latest = prices.iloc[-1]
    for h in holdings:
        if h.ticker in latest:
            h.current_price = round(latest[h.ticker], 2)
            if h.avg_price > 0:
                h.change_pct = round((h.current_price - h.avg_price) / h.avg_price * 100, 2)
    return prices


def _mock_fetch_benchmark(ticker="^NSEI", period="1y"):
    """Mock fetch_benchmark returning synthetic index data."""
    np.random.seed(99)
    dates = pd.bdate_range(end="2024-01-01", periods=252)
    returns = np.random.normal(0.0005, 0.01, 252)
    prices = 100 * np.cumprod(1 + returns)
    return pd.Series(prices, index=dates, name="Close")


class TestFullPipelineCSVToRisk:
    """End-to-end: CSV bytes -> Portfolio -> risk metrics -> no exceptions."""

    @patch("data.prices.fetch_benchmark", side_effect=_mock_fetch_benchmark)
    @patch("data.prices.fetch_prices", side_effect=_mock_fetch_prices)
    def test_csv_to_risk_metrics(self, mock_fetch, mock_benchmark):
        csv = b"ticker,quantity,avg_price\nRELIANCE,10,2500\nTCS,5,3500\nHDFCBANK,20,1600\n"
        portfolio = parse_portfolio_csv(csv)
        warnings = validate_portfolio(portfolio)
        assert len(warnings) == 0

        # Classify sectors
        sector_map = load_sector_map()
        portfolio.holdings = classify_holdings(portfolio.holdings, sector_map)

        # Fetch prices
        prices = _mock_fetch_prices(portfolio.holdings)

        # Compute risk
        weights = portfolio.weight
        risk = compute_risk_metrics(prices, weights)
        assert risk.volatility_annual > 0
        assert risk.sharpe != 0

        # Compute sector exposure
        sector = compute_sector_exposure(portfolio.holdings)
        assert len(sector.sector_allocation) > 0

    @patch("data.prices.fetch_benchmark", side_effect=_mock_fetch_benchmark)
    @patch("data.prices.fetch_prices", side_effect=_mock_fetch_prices)
    def test_pipeline_with_benchmark_comparison(self, mock_fetch, mock_benchmark):
        csv = b"ticker,quantity,avg_price\nRELIANCE,10,2500\nTCS,5,3500\n"
        portfolio = parse_portfolio_csv(csv)
        prices = _mock_fetch_prices(portfolio.holdings)

        weights = portfolio.weight
        portfolio_returns = compute_portfolio_returns(prices, weights)
        benchmark_prices = _mock_fetch_benchmark()
        benchmark_returns = benchmark_prices.pct_change().dropna()

        # Align dates
        common_idx = portfolio_returns.index.intersection(benchmark_returns.index)
        portfolio_returns = portfolio_returns.loc[common_idx]
        benchmark_returns = benchmark_returns.loc[common_idx]

        comparison = compare_to_benchmark(portfolio_returns, benchmark_returns)
        assert isinstance(comparison.alpha, float)
        assert isinstance(comparison.tracking_error, float)
        assert comparison.total_months > 0

    @patch("data.prices.fetch_benchmark", side_effect=_mock_fetch_benchmark)
    @patch("data.prices.fetch_prices", side_effect=_mock_fetch_prices)
    def test_pipeline_sector_classification_after_price_fetch(self, mock_fetch, mock_benchmark):
        """Sector classification must happen after price fetch (which sets current_price)."""
        csv = b"ticker,quantity,avg_price\nRELIANCE,10,2500\nTCS,5,3500\n"
        portfolio = parse_portfolio_csv(csv)
        _mock_fetch_prices(portfolio.holdings)  # sets current_price

        # NOW classify (after prices are set)
        portfolio.holdings = classify_holdings(portfolio.holdings, load_sector_map())

        # Verify current_price is set and sector is set
        for h in portfolio.holdings:
            assert h.current_price > 0
            assert h.sector != ""

        sector = compute_sector_exposure(portfolio.holdings)
        total_alloc = sum(sector.sector_allocation.values())
        assert abs(total_alloc - 100.0) < 0.1

    @patch("data.prices.fetch_benchmark", side_effect=_mock_fetch_benchmark)
    @patch("data.prices.fetch_prices", side_effect=_mock_fetch_prices)
    def test_full_analysis_report_construction(self, mock_fetch, mock_benchmark):
        """Build a complete AnalysisReport — same path as app.py."""
        csv = b"ticker,quantity,avg_price\nRELIANCE,10,2500\nTCS,5,3500\nHDFCBANK,20,1600\n"
        portfolio = parse_portfolio_csv(csv)
        portfolio.holdings = classify_holdings(portfolio.holdings, load_sector_map())
        prices = _mock_fetch_prices(portfolio.holdings)

        weights = portfolio.weight
        portfolio_returns = compute_portfolio_returns(prices, weights)
        benchmark_prices = _mock_fetch_benchmark()
        benchmark_returns = benchmark_prices.pct_change().dropna()

        common_idx = portfolio_returns.index.intersection(benchmark_returns.index)
        portfolio_returns = portfolio_returns.loc[common_idx]
        benchmark_returns = benchmark_returns.loc[common_idx]

        risk = compute_risk_metrics(prices, weights, benchmark_returns=benchmark_returns)
        sector = compute_sector_exposure(portfolio.holdings)
        benchmark = compare_to_benchmark(portfolio_returns, benchmark_returns)

        report = AnalysisReport(
            portfolio=portfolio,
            risk=risk,
            sector=sector,
            benchmark=benchmark,
        )

        assert report.portfolio.holding_count == 3
        assert report.risk.volatility_annual > 0
        assert len(report.sector.sector_allocation) > 0
        assert report.benchmark.total_months > 0


class TestMismatchedDimensions:
    """Ensure partial fetch failures don't cause dimension mismatch crashes."""

    def test_partial_fetch_dropped_ticker(self):
        """Portfolio has 3 holdings, prices only return 2 — dot product must not crash."""

        portfolio = Portfolio(
            holdings=[
                Holding(ticker="RELIANCE.NS", name="RIL", quantity=10, avg_price=2500),
                Holding(ticker="TCS.NS", name="TCS", quantity=5, avg_price=3500),
                Holding(ticker="BADTICKER.NS", name="Bad", quantity=1, avg_price=100),
            ],
        )
        # Simulate fetch returning data for only 2 of 3 tickers
        dates = pd.bdate_range(end="2024-01-01", periods=252)
        prices = pd.DataFrame(
            {
                "RELIANCE.NS": 100 * np.cumprod(1 + np.random.normal(0.0008, 0.015, 252)),
                "TCS.NS": 100 * np.cumprod(1 + np.random.normal(0.0008, 0.015, 252)),
            },
            index=dates,
        )
        # Simulate the app.py filter logic: remove holdings without price data
        portfolio.holdings = [h for h in portfolio.holdings if h.ticker in prices.columns]

        # Simulate current_price update done by fetch_prices
        latest = prices.iloc[-1]
        for h in portfolio.holdings:
            if h.ticker in latest:
                h.current_price = round(latest[h.ticker], 2)

        weights = portfolio.weight
        assert len(weights) == prices.shape[1], "Weights must match prices columns"
        returns = compute_portfolio_returns(prices, weights)
        assert isinstance(returns, pd.Series)
        assert len(returns) > 0

    def test_no_price_data_returns_empty_portfolio(self):
        """If no tickers have price data, portfolio holds should be empty after filter."""
        portfolio = Portfolio(
            holdings=[
                Holding(ticker="BAD1.NS", name="Bad1", quantity=10, avg_price=100),
                Holding(ticker="BAD2.NS", name="Bad2", quantity=5, avg_price=200),
            ],
        )
        prices = pd.DataFrame()  # empty — no data fetched

        # Filter logic
        portfolio.holdings = [h for h in portfolio.holdings if h.ticker in prices.columns]
        assert portfolio.holding_count == 0


class TestPortfolioParsingEdgeCases:
    """Edge cases that could break the pipeline."""

    def test_single_holding_portfolio(self):
        csv = b"ticker,quantity,avg_price\nRELIANCE,10,2500\n"
        portfolio = parse_portfolio_csv(csv)
        assert portfolio.holding_count == 1

        portfolio.holdings = classify_holdings(portfolio.holdings, load_sector_map())
        prices = _mock_fetch_prices(portfolio.holdings)
        weights = portfolio.weight
        risk = compute_risk_metrics(prices, weights)
        assert risk.volatility_annual > 0

    def test_heavy_weight_portfolio(self):
        """One stock is 99% of portfolio — should still compute without errors."""
        csv = (
            b"ticker,quantity,avg_price\n"
            b"RELIANCE,1000,2500\n"
            b"TCS,1,3500\n"
        )
        portfolio = parse_portfolio_csv(csv)
        portfolio.holdings = classify_holdings(portfolio.holdings, load_sector_map())
        prices = _mock_fetch_prices(portfolio.holdings)
        weights = portfolio.weight

        assert max(weights) > 0.99  # RELIANCE dominates
        risk = compute_risk_metrics(prices, weights)
        assert isinstance(risk.sharpe, float)

    def test_correlation_matrix_two_stocks(self):
        csv = b"ticker,quantity,avg_price\nRELIANCE,10,2500\nTCS,5,3500\n"
        portfolio = parse_portfolio_csv(csv)
        prices = _mock_fetch_prices(portfolio.holdings)
        corr = compute_correlation_matrix(prices)
        assert corr.shape == (2, 2)
