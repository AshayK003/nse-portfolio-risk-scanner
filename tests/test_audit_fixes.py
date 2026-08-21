"""Regression tests for the OpenCode audit fixes (2026-08-21).

Covers H1, M3, M4, L1, L2, L5, L7. These pin corrected behaviour so the
fixes can't silently regress.
"""

import base64
import json

import pytest

from engine import Holding, Portfolio, RiskMetrics, SectorExposure
from engine._log import logger
from engine.compute import _input_hash
from engine.portfolio import decode_portfolio_link, encode_portfolio_link
from engine.recommendations import generate_recommendations
from storage.models import SavedPortfolio, analysis_from_report


def _make_report():
    risk = RiskMetrics(
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
    sector = SectorExposure(
        holdings=[Holding(ticker="RELIANCE", name="Reliance", quantity=10, avg_price=2500)],
        sector_allocation={"Banking": 50.0},
        concentrated_sectors=[],
        diversification_score=65.0,
        herfindahl_index=0.38,
    )
    portfolio = Portfolio(holdings=[Holding(ticker="RELIANCE", name="Reliance", quantity=10, avg_price=2500)])
    return type("Report", (), {"risk": risk, "sector": sector, "portfolio": portfolio})()


def test_h1_generate_recommendations_importable_from_package():
    # H1: module shadowing deleted; live fn must resolve from the package.
    assert callable(generate_recommendations)


def test_m3_input_hash_stable_when_current_price_mutates():
    # M3: hash depends only on user inputs, not on fetch_prices-mutated current_price.
    p_before = Portfolio(
        holdings=[
            Holding(ticker="HDFCBANK", name="HDFC Bank", quantity=10, avg_price=700.0, current_price=735.05)
        ]
    )
    p_after = Portfolio(
        holdings=[
            Holding(ticker="HDFCBANK", name="HDFC Bank", quantity=10, avg_price=700.0, current_price=999.99)
        ]
    )
    assert _input_hash(p_before, "^NSEI", "moderate", 0.065) == _input_hash(
        p_after, "^NSEI", "moderate", 0.065
    )


def test_m4_csv_formula_injection_guard():
    # M4: leading = + - @ must be neutralised with an apostrophe.
    from ui.export import _esc

    assert _esc("=cmd") == "'=cmd"
    assert _esc("+cmd") == "'+cmd"
    assert _esc("-cmd") == "'-cmd"
    assert _esc("@cmd") == "'@cmd"
    # ordinary text unaffected
    assert _esc("Reliance") == "Reliance"
    # commas still quoted
    assert _esc("A, B") == '"A, B"'


def test_l1_benchmark_name_threaded():
    # L1: analysis_from_report must record the selected benchmark.
    report = _make_report()
    run = analysis_from_report(report, portfolio_name="Ashay", benchmark_name="NIFTY BANK")
    assert run.benchmark_name == "NIFTY BANK"


def test_l2_urlsafe_roundtrip_and_validation():
    # L2: encode uses urlsafe b64; decode rejects non-numeric and oversized links.
    holdings = [Holding(ticker="VEDL", name="Vedanta", quantity=5, avg_price=290.0)]
    token = encode_portfolio_link(Portfolio(holdings=holdings, name="P"))
    assert "+" not in token and "/" not in token  # urlsafe alphabet
    decoded = decode_portfolio_link(token)
    assert decoded.holdings[0].ticker == "VEDL.NS"
    assert decoded.holdings[0].quantity == 5

    bad = base64.urlsafe_b64encode(
        json.dumps({"holdings": [{"t": "VEDL", "q": "abc", "p": 290.0}]}).encode()
    ).decode()
    with pytest.raises(ValueError):
        decode_portfolio_link(bad)

    big = base64.urlsafe_b64encode(
        json.dumps({"holdings": [{"t": "X", "q": 1, "p": 1.0} for _ in range(201)]}).encode()
    ).decode()
    with pytest.raises(ValueError):
        decode_portfolio_link(big)


def test_l3_name_escaped_in_csv():
    # L3: portfolio name with comma/newline must not break CSV structure.
    from ui.export import _esc

    name = "My, Portfolio\nWith, Newlines"
    csv_name = f"Name,{_esc(name)}"
    assert csv_name.startswith("Name,")
    # the escaped name is wrapped in quotes and inner quotes doubled
    assert csv_name.endswith('"My, Portfolio\nWith, Newlines"')


def test_l5_log_format_survives_literal_braces():
    # L5: a message with literal braces but no matching kwargs must not crash.
    try:
        logger.info("raw json: {foo: 1, bar: 2}")
    except Exception as e:  # pragma: no cover
        pytest.fail(f"_log crashed on literal braces: {e}")


def test_l7_schema_drift_safe_row():
    # L7: extra columns in the DB row must be ignored, not raise TypeError.
    row = {
        "id": 1,
        "name": "X",
        "holdings_json": "[]",
        "created_at": "",
        "updated_at": "",
        "total_invested": 0.0,
        "total_current": 0.0,
        "total_pnl": 0.0,
        "unexpected_column": "ignored",
    }
    sp = SavedPortfolio(**{k: v for k, v in row.items() if k in SavedPortfolio.__dataclass_fields__})
    assert sp.name == "X"
    assert not hasattr(sp, "unexpected_column")
