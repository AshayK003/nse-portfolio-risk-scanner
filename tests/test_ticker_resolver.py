"""Tests for robust NSE ticker resolution and sample template generation."""

from engine.ticker_resolver import (
    ALIASES,
    NSE_TICKERS,
    build_ticker_options,
    get_company_name,
    parse_ticker_option,
)
from ui.sample_template import build_sample_excel


class TestGetCompanyName:
    def test_known_ticker(self):
        assert get_company_name("RELIANCE.NS") == NSE_TICKERS["RELIANCE"]

    def test_unknown_ticker_returns_clean(self):
        # Unknown ticker should return the cleaned symbol, not empty
        assert get_company_name("FAKETICKER") == "FAKETICKER"

    def test_no_empty_name(self):
        name = get_company_name("VEDL")
        assert name  # non-empty


class TestTickerOptions:
    def test_options_built(self):
        opts = build_ticker_options()
        assert len(opts) == len(NSE_TICKERS)
        assert all(" — " in o for o in opts)

    def test_parse_option(self):
        assert parse_ticker_option("RELIANCE — Reliance Industries") == "RELIANCE"

    def test_aliases_nonempty(self):
        assert len(ALIASES) > 100


class TestParsePortfolioExcel:
    def test_roundtrip_through_excel(self):
        from engine.portfolio import parse_portfolio_excel

        xlsx = build_sample_excel()
        pf = parse_portfolio_excel(xlsx, portfolio_name="Test")
        assert pf.holding_count == 7
        tickers = {h.ticker.replace(".NS", "") for h in pf.holdings}
        assert "RELIANCE" in tickers
        assert "HDFCBANK" in tickers
