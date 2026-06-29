"""Tests for sector classification module."""
import pytest
from engine import Holding, SectorExposure
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
        # Test default map has expected content
        sector_map = load_sector_map()
        assert "RELIANCE" in sector_map
        assert "TCS" in sector_map
        assert len(sector_map) > 50  # should have at least 50 stocks


class TestComputeSectorExposure:
    def test_single_sector(self):
        holdings = [
            Holding(ticker="SBIN.NS", name="SBI", quantity=10, avg_price=800, 
                    sector="Banking", current_price=900),
            Holding(ticker="HDFCBANK.NS", name="HDFC", quantity=5, avg_price=1700,
                    sector="Banking", current_price=1800),
        ]
        result = compute_sector_exposure(holdings)
        assert "Banking" in result.sector_allocation
        assert abs(result.sector_allocation["Banking"] - 100.0) < 0.1
    
    def test_diversification_score(self):
        # Two sectors, 50/50 split -> high diversification
        holdings = [
            Holding(ticker="TCS.NS", name="TCS", quantity=10, avg_price=3500,
                    sector="IT", current_price=4000),
            Holding(ticker="SBIN.NS", name="SBI", quantity=50, avg_price=800,
                    sector="Banking", current_price=900),
        ]
        result = compute_sector_exposure(holdings)
        assert result.diversification_score > 45  # well diversified
    
    def test_concentration_detection(self):
        # 95% in one sector -> should flag
        holdings = [
            Holding(ticker="SBIN.NS", name="SBI", quantity=100, avg_price=800,
                    sector="Banking", current_price=900),
            Holding(ticker="TCS.NS", name="TCS", quantity=1, avg_price=3500,
                    sector="IT", current_price=4000),
        ]
        result = compute_sector_exposure(holdings)
        assert "Banking" in result.concentrated_sectors
    
    def test_empty_holdings(self):
        result = compute_sector_exposure([])
        assert result.sector_allocation == {}
