"""Tests for the portfolio parsing module."""

import pytest

from engine import Holding, Portfolio
from engine.portfolio import (
    _detect_delimiter,
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

    def test_bse_stock_preserved(self):
        """BSE Ltd is a stock, not an alias for SENSEX index."""
        assert normalize_ticker("BSE") == "BSE.NS"

    def test_strips_eq_suffix(self):
        assert normalize_ticker("RELIANCE.EQ") == "RELIANCE.NS"

    def test_strips_ltd_suffix(self):
        assert normalize_ticker("RELIANCE.LTD") == "RELIANCE.NS"

    def test_handles_whitespace(self):
        assert normalize_ticker("  RELIANCE  ") == "RELIANCE.NS"


class TestDelimiterDetection:
    def test_comma(self):
        assert _detect_delimiter("a,b,c\n1,2,3\n") == ","

    def test_semicolon(self):
        assert _detect_delimiter("a;b;c\n1;2;3\n") == ";"

    def test_pipe(self):
        assert _detect_delimiter("a|b|c\n1|2|3\n") == "|"

    def test_tab(self):
        assert _detect_delimiter("a\tb\tc\n1\t2\t3\n") == "\t"

    def test_empty_content_defaults_comma(self):
        assert _detect_delimiter("") == ","


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
        csv = b'ticker,quantity,avg_price\nRELIANCE,10,2500.00\nTCS,5,"1,23,456.78"\n'
        portfolio = parse_portfolio_csv(csv)
        assert len(portfolio.holdings) == 2
        assert portfolio.holdings[1].avg_price == 123456.78

    def test_malformed_row_skipped(self):
        """Row with non-numeric quantity is skipped, others survive."""
        csv = b"ticker,quantity,avg_price\nRELIANCE,10,2500\nTCS,abc,3500\nHDFCBANK,20,1600\n"
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

    def test_avg_price_preferred_over_price(self):
        """When CSV has both 'Price' (LTP) and 'Avg Price', prefer Avg Price."""
        csv = b"Symbol,Qty,Price,Avg Price\nRELIANCE,10,2750,2500\nTCS,5,4200,3500\n"
        portfolio = parse_portfolio_csv(csv)
        assert portfolio.holdings[0].avg_price == 2500.0, (
            f"Expected avg_price=2500 (from Avg Price column), got {portfolio.holdings[0].avg_price}"
        )
        assert portfolio.holdings[1].avg_price == 3500.0

    def test_atp_alias(self):
        """CSV with 'ATP' column uses it as avg_price."""
        csv = b"Symbol,Qty,ATP,Price\nRELIANCE,10,2500,2750\n"
        portfolio = parse_portfolio_csv(csv)
        assert portfolio.holdings[0].avg_price == 2500.0

    def test_atp_with_currency_suffix(self):
        """'ATP (₹)' column is matched via suffix stripping."""
        csv = "Stock,Shares,ATP (₹),Cost (₹),Price (₹)\nRELIANCE,10,2500,25000,2750\n".encode()
        portfolio = parse_portfolio_csv(csv)
        assert portfolio.holdings[0].avg_price == 2500.0

    def test_price_preferred_over_cost(self):
        """With both 'Price' and 'Cost', prefer 'Price' (less ambiguous).
        'Price' is usually current LTP not avg buy price, but it's a far
        better approximation than using a total-cost column as per-share."""
        csv = b"Symbol,Qty,Price,Cost\nRELIANCE,10,2750,25000\n"
        portfolio = parse_portfolio_csv(csv)
        # 'price' alias comes before 'cost', so 'Price' column is used
        assert portfolio.holdings[0].avg_price == 2750.0

    def test_cost_total_auto_corrected(self):
        """When 'Cost' column has total values (only price column), auto-correct divides by qty."""
        csv = b"Symbol,Qty,Cost\nRELIANCE,10,25000\nTCS,5,17500\n"
        portfolio = parse_portfolio_csv(csv)
        assert portfolio.holdings[0].avg_price == 2500.0, (
            f"25000 (total) / 10 (qty) = 2500, got {portfolio.holdings[0].avg_price}"
        )
        assert portfolio.holdings[1].avg_price == 3500.0

    def test_cost_per_share_not_corrected(self):
        """When 'Cost' has reasonable per-share values, auto-correct doesn't trigger."""
        csv = b"Symbol,Qty,Cost\nRELIANCE,1,2500\nTCS,5,3500\n"
        portfolio = parse_portfolio_csv(csv)
        assert portfolio.holdings[0].avg_price == 2500.0  # qty=1, check bypassed
        assert portfolio.holdings[1].avg_price == 3500.0  # 3500 < 10000, bypassed

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

    # --- Broker format tests ---

    def test_groww_format(self):
        """Groww export: Symbol, Qty., Avg. Cost, LTP"""
        csv = b"Symbol,Qty.,Avg. Cost,LTP\nRELIANCE,10,2500.00,2750.00\nTCS,5,3500.00,4200.00\n"
        portfolio = parse_portfolio_csv(csv)
        assert portfolio.holdings[0].avg_price == 2500.0
        assert portfolio.holdings[1].avg_price == 3500.0

    def test_angel_one_format(self):
        """Angel One: Symbol, Quantity, Average Price, LTP"""
        csv = b"Symbol,Quantity,Average Price,LTP\nRELIANCE,10,2500.00,2750.00\n"
        portfolio = parse_portfolio_csv(csv)
        assert portfolio.holdings[0].avg_price == 2500.0

    def test_upstox_format(self):
        """Upstox: Symbol, Qty, Avg Price, LTP"""
        csv = b"Symbol,Qty,Avg Price,LTP\nRELIANCE,10,2500.00,2750.00\n"
        portfolio = parse_portfolio_csv(csv)
        assert portfolio.holdings[0].avg_price == 2500.0

    def test_icici_direct_format(self):
        """ICICI Direct: Scrip, Qty, Buy Price, LTP"""
        csv = b"Scrip,Qty,Buy Price,LTP\nRELIANCE,10,2500.00,2750.00\n"
        portfolio = parse_portfolio_csv(csv)
        assert portfolio.holdings[0].avg_price == 2500.0

    def test_semicolon_delimiter(self):
        """Semicolon-delimited CSV detected and parsed."""
        csv = b"Symbol;Qty;Avg Price\nRELIANCE;10;2500\nTCS;5;3500\n"
        portfolio = parse_portfolio_csv(csv)
        assert len(portfolio.holdings) == 2
        assert portfolio.holdings[0].avg_price == 2500.0

    def test_pipe_delimiter(self):
        """Pipe-delimited CSV detected and parsed."""
        csv = b"Symbol|Qty|Avg Price\nRELIANCE|10|2500\nTCS|5|3500\n"
        portfolio = parse_portfolio_csv(csv)
        assert len(portfolio.holdings) == 2
        assert portfolio.holdings[0].avg_price == 2500.0

    def test_percentage_sign_in_return(self):
        """Values like '+12.9%' are parsed correctly."""
        csv = b"Symbol,Qty,Avg Price,Return\nRELIANCE,10,2500,+12.9%\nTCS,5,3500,-2.5%\n"
        portfolio = parse_portfolio_csv(csv)
        assert len(portfolio.holdings) == 2
        assert portfolio.holdings[0].avg_price == 2500.0
        assert portfolio.holdings[1].avg_price == 3500.0

    def test_cost_within_reasonable_range(self):
        """Cost column with per-share values (< 10K) treated as per-share price."""
        csv = b"Symbol,Qty,Cost\nRELIANCE,10,2500\nTCS,5,3500\n"
        portfolio = parse_portfolio_csv(csv)
        assert portfolio.holdings[0].avg_price == 2500.0
        assert portfolio.holdings[1].avg_price == 3500.0

    def test_cost_high_value_not_corrected(self):
        """Cost column with high per-share values (e.g., MRF at 1.2L) is NOT auto-corrected."""
        csv = b"Symbol,Qty,Cost\nMRF,3,120000\n"
        portfolio = parse_portfolio_csv(csv)
        assert portfolio.holdings[0].avg_price == 120000.0

    def test_cost_total_auto_correct_with_samples(self):
        """Cost column with total values is auto-corrected by preprocessing sampling."""
        csv = b"Symbol,Qty,Cost\nRELIANCE,10,25000\nTCS,5,17500\n"
        portfolio = parse_portfolio_csv(csv)
        assert portfolio.holdings[0].avg_price == 2500.0
        assert portfolio.holdings[1].avg_price == 3500.0


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
            "holdings": [{"ticker": "RELIANCE", "name": "RIL", "quantity": 10, "avg_price": 2500}],
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
