"""Tests for the portfolio parsing module."""

import pytest

from engine import Holding, Portfolio
from engine.portfolio import (
    _parse_float,
    normalize_ticker,
    parse_portfolio_csv,
    portfolio_from_dict,
    validate_portfolio,
)


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

    def test_bse_alias(self):
        assert normalize_ticker("BSE") == "^BSESN"

    def test_strips_eq_suffix(self):
        assert normalize_ticker("RELIANCE.EQ") == "RELIANCE.NS"

    def test_strips_ltd_suffix(self):
        assert normalize_ticker("RELIANCE.LTD") == "RELIANCE.NS"

    def test_handles_whitespace(self):
        assert normalize_ticker("  RELIANCE  ") == "RELIANCE.NS"


class TestParseFloat:
    def test_simple_integer(self):
        assert _parse_float("100") == 100.0

    def test_simple_decimal(self):
        assert _parse_float("100.50") == 100.5

    def test_indian_format_comma_thousands(self):
        assert _parse_float("1,23,456.78") == 123456.78

    def test_indian_format_large(self):
        """10,00,000 in Indian format = 10 lakhs = 1,000,000."""
        assert _parse_float("10,00,000") == 1000000.0

    def test_rupee_symbol(self):
        assert _parse_float("₹2500.00") == 2500.0

    def test_rs_prefix(self):
        assert _parse_float("Rs. 2500") == 2500.0

    def test_empty_string(self):
        assert _parse_float("") == 0.0

    def test_whitespace_only(self):
        assert _parse_float("   ") == 0.0

    def test_negative(self):
        assert _parse_float("-100.50") == -100.5


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
        assert len(portfolio.holdings) == 2

    def test_bom_encoding(self):
        """Windows Excel exports CSV with BOM prefix — must parse correctly."""
        csv = b"\xef\xbb\xbf" + b"ticker,quantity,avg_price\nRELIANCE,10,2500\n"
        portfolio = parse_portfolio_csv(csv)
        assert len(portfolio.holdings) == 1
        assert portfolio.holdings[0].ticker == "RELIANCE.NS"

    def test_indian_number_format(self):
        """User pastes Indian-formatted numbers: 1,23,456.78."""
        csv = b"ticker,quantity,avg_price\nRELIANCE,10,2500.00\nTCS,5,\"1,23,456.78\"\n"
        portfolio = parse_portfolio_csv(csv)
        assert len(portfolio.holdings) == 2
        assert portfolio.holdings[1].avg_price == 123456.78

    def test_malformed_row_skipped(self):
        """Row with non-numeric quantity is skipped, others survive."""
        csv = (
            b"ticker,quantity,avg_price\n"
            b"RELIANCE,10,2500\n"
            b"TCS,abc,3500\n"
            b"HDFCBANK,20,1600\n"
        )
        portfolio = parse_portfolio_csv(csv)
        assert len(portfolio.holdings) == 2
        assert portfolio.holdings[0].ticker == "RELIANCE.NS"
        assert portfolio.holdings[1].ticker == "HDFCBANK.NS"

    def test_negative_quantity_skipped(self):
        csv = b"ticker,quantity,avg_price\nRELIANCE,-10,2500\nTCS,5,3500\n"
        portfolio = parse_portfolio_csv(csv)
        assert len(portfolio.holdings) == 1

    def test_zero_price_skipped(self):
        csv = b"ticker,quantity,avg_price\nRELIANCE,10,0\nTCS,5,3500\n"
        portfolio = parse_portfolio_csv(csv)
        assert len(portfolio.holdings) == 1

    def test_empty_rows_skipped(self):
        csv = b"ticker,quantity,avg_price\nRELIANCE,10,2500\n\n\nTCS,5,3500\n"
        portfolio = parse_portfolio_csv(csv)
        assert len(portfolio.holdings) == 2

    def test_custom_column_names(self):
        csv = b"scrip,holdings,average cost\nRELIANCE,10,2500\n"
        portfolio = parse_portfolio_csv(csv)
        assert len(portfolio.holdings) == 1
        assert portfolio.holdings[0].ticker == "RELIANCE.NS"

    def test_three_column_fallback(self):
        """Unrecognized headers with exactly 3 columns -> best-effort mapping."""
        csv = b"col1,col2,col3\nRELIANCE,10,2500\n"
        portfolio = parse_portfolio_csv(csv)
        assert len(portfolio.holdings) == 1

    def test_too_few_columns_raises(self):
        with pytest.raises(ValueError, match="Could not find columns"):
            parse_portfolio_csv(b"a,b\n1,2\n")

    def test_error_messages_included(self):
        """When all rows fail, error message includes specific row errors."""
        csv = b"ticker,quantity,avg_price\nRELIANCE,0,0\n"
        with pytest.raises(ValueError, match="Row 2"):
            parse_portfolio_csv(csv)

    def test_portfolio_name(self):
        csv = b"ticker,quantity,avg_price\nRELIANCE,10,2500\n"
        portfolio = parse_portfolio_csv(csv, portfolio_name="My Fund")
        assert portfolio.name == "My Fund"


class TestValidatePortfolio:
    def test_valid_portfolio(self, sample_portfolio):
        warnings = validate_portfolio(sample_portfolio)
        assert len(warnings) == 0

    def test_empty_portfolio_warning(self):
        p = Portfolio(holdings=[])
        warnings = validate_portfolio(p)
        assert any("empty" in w.lower() for w in warnings)

    def test_concentration_warning(self, sample_portfolio):
        sample_portfolio.holdings[0].current_price = 100
        sample_portfolio.holdings[1].current_price = 100
        sample_portfolio.holdings[2].current_price = 5000
        warnings = validate_portfolio(sample_portfolio)
        assert any("concentration" in w.lower() for w in warnings)

    def test_large_portfolio_warning(self):
        holdings = [
            Holding(ticker=f"S{i}.NS", name=f"S{i}", quantity=1, avg_price=100, current_price=100)
            for i in range(60)
        ]
        p = Portfolio(holdings=holdings)
        warnings = validate_portfolio(p)
        assert any("60" in w for w in warnings)


class TestPortfolioWeightEdgeCases:
    def test_weight_with_zero_current_value(self):
        """When all current_prices are 0, weight should return zeros."""
        holdings = [
            Holding(ticker="A", name="A", quantity=10, avg_price=100, current_price=0),
            Holding(ticker="B", name="B", quantity=5, avg_price=200, current_price=0),
        ]
        p = Portfolio(holdings=holdings)
        weights = p.weight
        assert weights == [0.0, 0.0]

    def test_weight_partial_zero_current(self):
        """One holding has zero current_price, others don't."""
        holdings = [
            Holding(ticker="A", name="A", quantity=10, avg_price=100, current_price=100),
            Holding(ticker="B", name="B", quantity=5, avg_price=200, current_price=0),
        ]
        p = Portfolio(holdings=holdings)
        weights = p.weight
        assert weights[0] == 1.0
        assert weights[1] == 0.0

    def test_weight_sums_to_one(self):
        holdings = [
            Holding(ticker="A", name="A", quantity=10, avg_price=100, current_price=150),
            Holding(ticker="B", name="B", quantity=5, avg_price=200, current_price=300),
        ]
        p = Portfolio(holdings=holdings)
        weights = p.weight
        assert abs(sum(weights) - 1.0) < 1e-10

    def test_empty_portfolio_weight(self):
        p = Portfolio(holdings=[])
        assert p.weight == []

    def test_total_pnl_pct_zero_invested(self):
        """Portfolio with zero invested value -> 0% pnl_pct, not division by zero."""
        p = Portfolio(holdings=[])
        assert p.total_pnl_pct == 0.0


class TestPortfolioFromDict:
    def test_basic_conversion(self):
        data = {
            "name": "Test",
            "holdings": [
                {"ticker": "RELIANCE", "name": "RIL", "quantity": 10, "avg_price": 2500}
            ],
        }
        p = portfolio_from_dict(data)
        assert p.name == "Test"
        assert len(p.holdings) == 1
        assert p.holdings[0].ticker == "RELIANCE.NS"

    def test_missing_fields_defaults(self):
        data = {"holdings": [{"ticker": "TCS"}]}
        p = portfolio_from_dict(data)
        assert p.holdings[0].name == "TCS"
        assert p.holdings[0].quantity == 0
        assert p.holdings[0].avg_price == 0.0

    def test_empty_data(self):
        p = portfolio_from_dict({})
        assert p.name == "My Portfolio"
        assert len(p.holdings) == 0
