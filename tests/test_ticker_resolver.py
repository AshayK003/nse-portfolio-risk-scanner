"""Tests for robust NSE ticker resolution and sample template generation."""

import io

import pandas as pd
import pytest

from engine.ticker_resolver import (
    ALIASES,
    NSE_TICKERS,
    build_ticker_options,
    get_company_name,
    parse_ticker_option,
    resolve_ticker,
)
from ui.sample_template import build_sample_csv, build_sample_excel


class TestResolveTickerOffline:
    def test_exact_ticker(self):
        ticker, name = resolve_ticker("RELIANCE")
        assert ticker == "RELIANCE"
        assert "Reliance" in name

    def test_exact_ticker_with_ns_suffix(self):
        ticker, _ = resolve_ticker("TCS.NS")
        assert ticker == "TCS"

    def test_alias_resolves(self):
        # "HDFC BANK" → HDFCBANK
        ticker, _ = resolve_ticker("HDFC BANK")
        assert ticker == "HDFCBANK"

    def test_company_name_reverse_lookup(self):
        ticker, _ = resolve_ticker("Infosys")
        assert ticker == "INFY"

    def test_partial_company_name(self):
        # "Tata Steel" partial contains match returns a valid ticker
        ticker, _ = resolve_ticker("Tata Steel")
        assert ticker == "TATASTEEL"

    def test_ticker_prefix(self):
        ticker, _ = resolve_ticker("HDFC")
        assert ticker in NSE_TICKERS

    def test_unknown_returns_none(self):
        ticker, name = resolve_ticker("ZZZZNONEXISTENT")
        assert ticker is None
        assert name is None


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


class TestSampleTemplate:
    def test_excel_has_expected_columns(self):
        data = build_sample_excel()
        assert isinstance(data, bytes)
        df = pd.read_excel(io.BytesIO(data))
        assert list(df.columns)[:4] == ["Ticker", "Name", "Quantity", "Avg Price"]
        assert len(df) == 7
        assert df.iloc[0]["Ticker"] == "RELIANCE"

    def test_csv_has_expected_columns(self):
        data = build_sample_csv()
        assert isinstance(data, bytes)
        text = data.decode("utf-8-sig")
        assert "Ticker,Name,Quantity,Avg Price" in text


class TestParsePortfolioExcel:
    def test_roundtrip_through_excel(self):
        from engine.portfolio import parse_portfolio_excel

        xlsx = build_sample_excel()
        pf = parse_portfolio_excel(xlsx, portfolio_name="Test")
        assert pf.holding_count == 7
        tickers = {h.ticker.replace(".NS", "") for h in pf.holdings}
        assert "RELIANCE" in tickers
        assert "HDFCBANK" in tickers
