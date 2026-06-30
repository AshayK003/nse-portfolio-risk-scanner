"""Tests for the SQLite storage layer (db.py).

Uses isolated temp databases per test via the tmp_db fixture.
"""

from __future__ import annotations

import pytest

from storage.db import (
    clear_all_cache,
    clear_stale_cache,
    clear_ticker_cache,
    close_connection,
    delete_portfolio,
    get_cached_prices,
    get_connection,
    list_recent_analyses,
    list_saved_portfolios,
    load_portfolio,
    save_analysis_run,
    save_cached_prices,
    save_portfolio,
)
from storage.models import AnalysisRun, CachedPrice, SavedPortfolio


@pytest.fixture(autouse=True)
def _isolated_db(tmp_db):
    """Each test gets a fresh SQLite connection to a temp file."""
    close_connection()
    # Pre-create connection so CRUD functions (which call get_connection()
    # without a path) reuse this temp connection instead of the default DB.
    get_connection(tmp_db)
    yield tmp_db
    close_connection()


class TestSchemaCreation:
    def test_creates_schema_on_first_use(self, tmp_db):
        conn = get_connection(tmp_db)
        # schema_version table should exist
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        assert row is not None
        assert row["version"] == 1

    def test_tables_created(self, tmp_db):
        conn = get_connection(tmp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "saved_portfolios" in table_names
        assert "price_cache" in table_names
        assert "analysis_runs" in table_names
        assert "schema_version" in table_names

    def test_idempotent_schema(self, tmp_db):
        """Calling get_connection twice doesn't crash."""
        get_connection(tmp_db)
        get_connection(tmp_db)  # second call reuses connection


class TestPortfolioCRUD:
    def test_save_and_load(self, tmp_db):
        sp = SavedPortfolio(
            name="Test Fund",
            holdings_json='[{"ticker": "RELIANCE"}]',
            total_invested=25000,
            total_current=27000,
            total_pnl=2000,
        )
        p_id = save_portfolio(sp)
        assert p_id > 0

        loaded = load_portfolio(p_id)
        assert loaded is not None
        assert loaded.name == "Test Fund"
        assert loaded.total_invested == 25000

    def test_update_existing(self, tmp_db):
        sp = SavedPortfolio(
            name="Original",
            holdings_json="[]",
            total_invested=0,
            total_current=0,
            total_pnl=0,
        )
        p_id = save_portfolio(sp)

        sp.name = "Updated"
        sp.id = p_id
        save_portfolio(sp)

        loaded = load_portfolio(p_id)
        assert loaded.name == "Updated"

    def test_list_saved_portfolios(self, tmp_db):
        save_portfolio(SavedPortfolio(name="A", holdings_json="[]"))
        save_portfolio(SavedPortfolio(name="B", holdings_json="[]"))

        result = list_saved_portfolios()
        assert len(result) == 2
        # Newest first
        assert result[0].name == "B"

    def test_delete_portfolio(self, tmp_db):
        p_id = save_portfolio(SavedPortfolio(name="ToDelete", holdings_json="[]"))
        deleted = delete_portfolio(p_id)
        assert deleted is True
        assert load_portfolio(p_id) is None

    def test_delete_nonexistent(self, tmp_db):
        deleted = delete_portfolio(99999)
        assert deleted is False

    def test_load_nonexistent(self, tmp_db):
        assert load_portfolio(99999) is None


class TestAnalysisHistory:
    def test_save_and_list(self, tmp_db):
        run = AnalysisRun(
            portfolio_name="Test",
            holding_count=5,
            volatility=15.0,
            sharpe=1.2,
            cagr=12.0,
            created_at="2024-01-01T10:00:00",
        )
        run_id = save_analysis_run(run)
        assert run_id > 0

        runs = list_recent_analyses(limit=10)
        assert len(runs) == 1
        assert runs[0].portfolio_name == "Test"
        assert runs[0].volatility == 15.0

    def test_list_limit(self, tmp_db):
        for i in range(5):
            save_analysis_run(AnalysisRun(
                portfolio_name=f"Run {i}",
                created_at=f"2024-01-0{i}T10:00:00",
            ))

        runs = list_recent_analyses(limit=3)
        assert len(runs) == 3


class TestPriceCache:
    def test_save_and_get(self, tmp_db):
        prices = [
            CachedPrice(ticker="RELIANCE.NS", date="2024-01-01", close=2500.0),
            CachedPrice(ticker="RELIANCE.NS", date="2024-01-02", close=2510.0),
        ]
        save_cached_prices("RELIANCE.NS", prices)

        result = get_cached_prices("RELIANCE.NS", max_age_hours=24)
        assert result is not None
        assert len(result) == 2
        assert result[0].close == 2500.0

    def test_get_expired_returns_none(self, tmp_db):
        prices = [CachedPrice(ticker="OLD.NS", date="2024-01-01", close=100.0)]
        save_cached_prices("OLD.NS", prices)

        # max_age_hours=0 means everything is stale
        result = get_cached_prices("OLD.NS", max_age_hours=0)
        assert result is None

    def test_clear_ticker_cache(self, tmp_db):
        save_cached_prices("A.NS", [CachedPrice(ticker="A.NS", date="2024-01-01", close=100.0)])
        save_cached_prices("B.NS", [CachedPrice(ticker="B.NS", date="2024-01-01", close=200.0)])

        clear_ticker_cache("A.NS")

        assert get_cached_prices("A.NS") is None
        assert get_cached_prices("B.NS") is not None

    def test_clear_all_cache(self, tmp_db):
        save_cached_prices("A.NS", [CachedPrice(ticker="A.NS", date="2024-01-01", close=100.0)])
        save_cached_prices("B.NS", [CachedPrice(ticker="B.NS", date="2024-01-01", close=200.0)])

        clear_all_cache()

        assert get_cached_prices("A.NS") is None
        assert get_cached_prices("B.NS") is None

    def test_upsert_behavior(self, tmp_db):
        """Saving same ticker+date twice should upsert, not duplicate."""
        save_cached_prices("X.NS", [CachedPrice(ticker="X.NS", date="2024-01-01", close=100.0)])
        save_cached_prices("X.NS", [CachedPrice(ticker="X.NS", date="2024-01-01", close=150.0)])

        result = get_cached_prices("X.NS")
        assert result is not None
        assert len(result) == 1
        assert result[0].close == 150.0

    def test_clear_stale_cache(self, tmp_db):
        save_cached_prices("OLD.NS", [CachedPrice(ticker="OLD.NS", date="2024-01-01", close=100.0)])
        clear_stale_cache(max_age_hours=0)  # everything is stale
        assert get_cached_prices("OLD.NS") is None
