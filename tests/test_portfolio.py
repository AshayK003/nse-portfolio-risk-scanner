"""Tests for the portfolio parsing module."""
import pytest
from engine import Holding, Portfolio
from engine.portfolio import parse_portfolio_csv, normalize_ticker, validate_portfolio


class TestNormalizeTicker:
    def test_clean_ticker(self):
        assert normalize_ticker("RELIANCE") == "RELIANCE.NS"
    
    def test_strips_ns_suffix(self):
        assert normalize_ticker("RELIANCE.NS") == "RELIANCE.NS"
    
    def test_handles_nse_suffix(self):
        assert normalize_ticker("RELIANCE.NSE") == "RELIANCE.NS"
    
    def test_handles_lowercase(self):
        assert normalize_ticker("reliance") == "RELIANCE.NS"
    
    def test_index_ticker(self):
        assert normalize_ticker("^NSEI") == "^NSEI"
    
    def test_nifty_alias(self):
        assert normalize_ticker("NIFTY") == "^NSEI"
    
    def test_sensex_alias(self):
        assert normalize_ticker("SENSEX") == "^BSESN"


class TestParsePortfolio:
    def test_parse_valid_csv(self, sample_csv):
        portfolio = parse_portfolio_csv(sample_csv)
        assert len(portfolio.holdings) == 3
        assert portfolio.holdings[0].ticker == "RELIANCE.NS"
        assert portfolio.holdings[0].quantity == 10
        assert portfolio.holdings[0].avg_price == 2500.00
    
    def test_parse_zerodha_format(self, zerodha_csv):
        portfolio = parse_portfolio_csv(zerodha_csv)
        assert len(portfolio.holdings) == 3
        assert portfolio.holdings[1].ticker == "TCS.NS"
    
    def test_parse_empty_csv(self):
        with pytest.raises(ValueError, match="No valid holdings found"):
            parse_portfolio_csv(b"ticker,quantity,avg_price\n")
    
    def test_parse_no_header(self):
        with pytest.raises(ValueError):
            parse_portfolio_csv(b"")
    
    def test_duplicate_ticker_detection(self):
        csv = b"ticker,quantity,avg_price\nRELIANCE,10,2500\nRELIANCE,5,2600\nTCS,5,3500\n"
        portfolio = parse_portfolio_csv(csv)
        # Should have 2 (RELIANCE deduped, TCS)
        assert len(portfolio.holdings) == 2


class TestValidatePortfolio:
    def test_valid_portfolio(self, sample_portfolio):
        warnings = validate_portfolio(sample_portfolio)
        assert len(warnings) == 0
    
    def test_empty_portfolio_warning(self):
        p = Portfolio(holdings=[])
        warnings = validate_portfolio(p)
        assert any("empty" in w.lower() for w in warnings)
    
    def test_concentration_warning(self, sample_portfolio):
        # Make HDFCBANK dominant by setting current prices
        sample_portfolio.holdings[0].current_price = 100  # RELIANCE: 1000
        sample_portfolio.holdings[1].current_price = 100  # TCS: 500
        sample_portfolio.holdings[2].current_price = 5000  # HDFCBANK: 100000 -> ~98%
        warnings = validate_portfolio(sample_portfolio)
        assert any("concentration" in w.lower() for w in warnings)
