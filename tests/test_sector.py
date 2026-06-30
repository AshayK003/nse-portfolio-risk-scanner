"""Tests for sector classification module."""

from engine import Holding
from engine.sector import classify_holdings, compute_sector_exposure, load_sector_map


class TestClassifyHoldings:
    def test_known_ticker(self):
        holdings = [Holding(ticker="RELIANCE.NS", name="RIL", quantity=10, avg_price=2500)]
        result = classify_holdings(holdings)
        assert result[0].sector == "Oil & Gas"

    def test_etf_classification(self):
        holdings = [Holding(ticker="NIFTYBEES.NS", name="Nifty Bees", quantity=100, avg_price=250)]
        result = classify_holdings(holdings)
        assert result[0].sector == "ETF"

    def test_sector_map_loaded(self):
        sector_map = load_sector_map()
        assert "RELIANCE" in sector_map
        assert "TCS" in sector_map
        assert len(sector_map) > 50

    def test_unknown_ticker_gets_unknown(self):
        """Unknown tickers get 'Unknown' sector (no external API calls)."""
        holdings = [Holding(ticker="FAKECORP.NS", name="Fake", quantity=10, avg_price=100)]
        result = classify_holdings(holdings)
        assert result[0].sector == "Unknown"

    def test_custom_sector_map(self):
        custom = {"RELIANCE": "Custom Sector"}
        holdings = [Holding(ticker="RELIANCE.NS", name="RIL", quantity=10, avg_price=2500)]
        result = classify_holdings(holdings, sector_map=custom)
        assert result[0].sector == "Custom Sector"


class TestComputeSectorExposure:
    def test_single_sector(self):
        holdings = [
            Holding(
                ticker="SBIN.NS", name="SBI", quantity=10, avg_price=800, sector="Banking", current_price=900
            ),
            Holding(
                ticker="HDFCBANK.NS",
                name="HDFC",
                quantity=5,
                avg_price=1700,
                sector="Banking",
                current_price=1800,
            ),
        ]
        result = compute_sector_exposure(holdings)
        assert "Banking" in result.sector_allocation
        assert abs(result.sector_allocation["Banking"] - 100.0) < 0.1

    def test_diversification_score(self):
        holdings = [
            Holding(
                ticker="TCS.NS", name="TCS", quantity=10, avg_price=3500, sector="IT", current_price=4000
            ),
            Holding(
                ticker="SBIN.NS", name="SBI", quantity=50, avg_price=800, sector="Banking", current_price=900
            ),
        ]
        result = compute_sector_exposure(holdings)
        assert result.diversification_score > 45

    def test_concentration_detection(self):
        holdings = [
            Holding(
                ticker="SBIN.NS", name="SBI", quantity=100, avg_price=800, sector="Banking", current_price=900
            ),
            Holding(ticker="TCS.NS", name="TCS", quantity=1, avg_price=3500, sector="IT", current_price=4000),
        ]
        result = compute_sector_exposure(holdings)
        assert "Banking" in result.concentrated_sectors

    def test_empty_holdings(self):
        result = compute_sector_exposure([])
        assert result.sector_allocation == {}

    def test_unknown_sector_grouped(self):
        """Holdings with sector='Unknown' are grouped under Unknown."""
        holdings = [
            Holding(ticker="X.NS", name="X", quantity=10, avg_price=100,
                    sector="Unknown", current_price=100),
            Holding(ticker="Y.NS", name="Y", quantity=10, avg_price=100,
                    sector="Unknown", current_price=100),
        ]
        result = compute_sector_exposure(holdings)
        assert "Unknown" in result.sector_allocation
        assert result.sector_allocation["Unknown"] == 100.0

    def test_herfindahl_index_range(self):
        """HHI should be between 0 and 1."""
        holdings = [
            Holding(ticker="A.NS", name="A", quantity=10, avg_price=100,
                    sector="IT", current_price=100),
            Holding(ticker="B.NS", name="B", quantity=10, avg_price=100,
                    sector="Banking", current_price=100),
            Holding(ticker="C.NS", name="C", quantity=10, avg_price=100,
                    sector="Pharma", current_price=100),
        ]
        result = compute_sector_exposure(holdings)
        assert 0 <= result.herfindahl_index <= 1.0
