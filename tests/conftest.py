"""Test fixtures for the NSE Portfolio Risk Scanner."""

import os
import sys

# Ensure project root is on sys.path for direct pytest invocation
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from datetime import datetime  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from engine import Holding, Portfolio  # noqa: E402


@pytest.fixture
def sample_holdings():
    return [
        Holding(ticker="RELIANCE", name="Reliance Industries", quantity=10, avg_price=2500),
        Holding(ticker="TCS", name="Tata Consultancy Services", quantity=5, avg_price=3500),
        Holding(ticker="HDFCBANK", name="HDFC Bank", quantity=20, avg_price=1600),
    ]


@pytest.fixture
def sample_portfolio(sample_holdings):
    return Portfolio(holdings=sample_holdings, name="Test Portfolio")


@pytest.fixture
def sample_prices():
    """Generate 252 days of synthetic price data for 3 stocks."""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=252, freq="B")
    n_stocks = 3

    # Random walk with drift
    returns = np.random.normal(0.001, 0.02, (252, n_stocks))
    prices = 100 * np.cumprod(1 + returns, axis=0)

    df = pd.DataFrame(
        prices,
        index=dates,
        columns=["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"],
    )
    return df


@pytest.fixture
def sample_csv():
    """A realistic portfolio CSV as bytes."""
    return b"""ticker,quantity,avg_price
RELIANCE,10,2500.00
TCS,5,3500.00
HDFCBANK,20,1600.00
"""


@pytest.fixture
def zerodha_csv():
    """Zerodha-style export format."""
    return b"""Symbol,Qty,Avg Price
RELIANCE,10,2500.00
TCS,5,3500.00
HDFCBANK,20,1600.00
"""
