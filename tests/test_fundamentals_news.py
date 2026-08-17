"""Tests for the Fundamentals and News UI modules."""

import pandas as pd
import pytest

from engine import Holding, Portfolio
from ui.fundamentals import _format, fetch_fundamentals
from ui.news import fetch_news


class TestFundamentalsFormat:
    def test_format_percent(self):
        assert _format(0.1234, "%") == "12.3%"

    def test_format_x(self):
        assert _format(15.5, "x") == "15.5x"

    def test_format_cr(self):
        # 1e9 rupees = 100 crore
        assert _format(1e9, "cr") == "Rs 100 Cr"

    def test_format_none(self):
        assert _format(None, "%") == "N/A"

    def test_format_unparseable(self):
        assert _format("not-a-number", "%") == "N/A"


class TestFetchFundamentals:
    def test_returns_dict(self):
        # Known liquid large-cap; may be empty if offline but must be a dict
        result = fetch_fundamentals("RELIANCE")
        assert isinstance(result, dict)

    def test_unknown_ticker_safe(self):
        result = fetch_fundamentals("NONEXISTENTXYZ")
        assert isinstance(result, dict)


class TestFetchNews:
    def test_returns_list(self):
        items = fetch_news("RELIANCE")
        assert isinstance(items, list)

    def test_items_have_keys(self):
        items = fetch_news("TCS")
        for it in items[:3]:
            assert "title" in it
            assert "link" in it


class TestPortfolioRenderInputs:
    def test_portfolio_with_holdings(self):
        pf = Portfolio(
            holdings=[
                Holding(ticker="RELIANCE.NS", name="Reliance Industries", quantity=10, avg_price=100.0),
                Holding(ticker="TCS.NS", name="Tata Consultancy Services", quantity=5, avg_price=200.0),
            ]
        )
        assert pf.holding_count == 2
