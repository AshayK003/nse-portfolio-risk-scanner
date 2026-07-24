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
    dates = pd.date_range(end=datetime(2024, 1, 1), periods=252, freq="B")
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


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary SQLite database path and clean up connections after."""
    import storage.db as db_mod

    db_path = str(tmp_path / "test.db")
    # Patch the module's _DB_PATH to use our temp database
    original_db_path = db_mod._DB_PATH
    db_mod._DB_PATH = db_path
    # Reset thread-local so each test gets a fresh connection
    db_mod._local.conn = None
    yield db_path
    # Restore original
    db_mod._DB_PATH = original_db_path
    db_mod._local.conn = None


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Provide a temporary directory for diskcache."""
    return str(tmp_path / "cache")


@pytest.fixture
def sample_risk_metrics():
    """A minimal RiskMetrics for building AnalysisReport fixtures."""
    from engine import RiskMetrics

    return RiskMetrics(
        volatility_annual=15.0,
        var_95=-2.5,
        var_99=-4.0,
        cvar_95=-3.2,
        max_drawdown=-18.5,
        max_drawdown_start="2024-03-01",
        max_drawdown_end="2024-06-15",
        beta=0.85,
        correlation_to_benchmark=0.92,
        sharpe=1.2,
        sortino=1.8,
        cagr=12.5,
        total_return=25.0,
    )


@pytest.fixture
def sample_sector_exposure(sample_holdings):
    """A minimal SectorExposure for building AnalysisReport fixtures."""
    from engine import SectorExposure

    return SectorExposure(
        holdings=sample_holdings,
        sector_allocation={"Banking": 50.0, "IT": 30.0, "Oil & Gas": 20.0},
        concentrated_sectors=["Banking"],
        diversification_score=65.0,
        herfindahl_index=0.38,
    )


@pytest.fixture
def sample_benchmark_comparison():
    """A minimal BenchmarkComparison for building AnalysisReport fixtures."""
    from engine import BenchmarkComparison

    return BenchmarkComparison(
        portfolio_return=25.0,
        benchmark_return=18.0,
        alpha=7.0,
        tracking_error=5.5,
        information_ratio=1.27,
        beta=0.85,
        correlation=0.92,
        rolling_alpha_6m=8.0,
        outperformance_months=8,
        total_months=12,
    )
