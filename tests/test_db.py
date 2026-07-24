"""Tests for the database module."""

from __future__ import annotations

from storage.db import (
    delete_portfolio,
    list_recent_analyses,
    list_saved_portfolios,
    load_portfolio,
    save_analysis_run,
    save_portfolio,
)
from storage.models import AnalysisRun, SavedPortfolio


def test_save_and_load_portfolio(tmp_db):
    portfolio = SavedPortfolio(
        name="Test Portfolio",
        holdings_json='[{"ticker": "RELIANCE.NS", "quantity": 10, "avg_price": 2500}]',
        total_invested=25000,
        total_current=26000,
        total_pnl=1000,
    )
    pid = save_portfolio(portfolio)

    assert pid is not None
    assert isinstance(pid, int)

    loaded = load_portfolio(pid)
    assert loaded is not None
    assert loaded.name == "Test Portfolio"
    assert loaded.holdings_json == portfolio.holdings_json
    assert loaded.total_invested == 25000


def test_update_portfolio(tmp_db):
    portfolio = SavedPortfolio(name="Original", holdings_json="[]")
    p_id = save_portfolio(portfolio)

    sp = load_portfolio(p_id)
    sp.name = "Updated"
    sp.id = p_id
    save_portfolio(sp)

    loaded = load_portfolio(p_id)
    assert loaded.name == "Updated"


def test_list_saved_portfolios(tmp_db):
    save_portfolio(SavedPortfolio(name="A", holdings_json="[]"))
    save_portfolio(SavedPortfolio(name="B", holdings_json="[]"))

    result = list_saved_portfolios()
    assert len(result) == 2
    # Newest first (by updated_at) — both created in quick succession, check both present
    names = {p.name for p in result}
    assert names == {"A", "B"}


def test_delete_portfolio(tmp_db):
    p_id = save_portfolio(SavedPortfolio(name="ToDelete", holdings_json="[]"))
    deleted = delete_portfolio(p_id)
    assert deleted is True
    assert load_portfolio(p_id) is None


def test_delete_nonexistent(tmp_db):
    deleted = delete_portfolio(99999)
    assert deleted is False


def test_load_nonexistent(tmp_db):
    assert load_portfolio(99999) is None


def test_save_analysis_run(tmp_db):
    run = AnalysisRun(
        portfolio_name="Test",
        holding_count=3,
        volatility=15.0,
        var_95=-2.5,
        max_drawdown=-10.0,
        sharpe=1.2,
        cagr=18.0,
        beta=0.9,
        diversification_score=65.0,
        benchmark_name="NIFTY 50",
        created_at="2024-01-01T12:00:00",
    )
    rid = save_analysis_run(run)

    assert rid is not None
    assert isinstance(rid, int)

    recent = list_recent_analyses(limit=5)
    assert len(recent) >= 1
    assert recent[0].portfolio_name == "Test"
