"""Regression test: sidebar risk profile must flow into recommendation rules."""

from __future__ import annotations

import pytest

from engine import RISK_PROFILES, Holding, Portfolio
from engine.recommendations.engine import generate_recommendations


def _portfolio() -> Portfolio:
    return Portfolio(
        holdings=[
            Holding(ticker="RELIANCE.NS", name="Reliance", quantity=10, avg_price=1100),
            Holding(ticker="TCS.NS", name="TCS", quantity=5, avg_price=1700),
            Holding(ticker="INFY.NS", name="Infosys", quantity=20, avg_price=850),
            Holding(ticker="ITC.NS", name="ITC", quantity=50, avg_price=240),
            Holding(ticker="ICICIBANK.NS", name="ICICI Bank", quantity=30, avg_price=1150),
            Holding(ticker="HDFCBANK.NS", name="HDFC Bank", quantity=15, avg_price=1650),
            Holding(ticker="NIFTYBEES.NS", name="Nifty BeES", quantity=100, avg_price=240),
        ],
        name="t",
    )


class _FakeSector:
    sector_allocation = {"Banking": 37.8, "IT": 24.0, "Energy": 15.0, "ETF": 19.5}


class _FakeRisk:
    sharpe = 0.0
    volatility_annual = 13.4
    max_drawdown = -18.6
    var_95 = -1.36
    cvar_95 = -1.85


@pytest.mark.parametrize("key,expected_cap", [
    ("conservative", "25.0%"),
    ("moderate", "35.0%"),
])
def test_recommendations_respect_risk_profile(key, expected_cap):
    """Concentration cap in recommendation reasons must come from the selected profile."""
    report = generate_recommendations(
        risk=_FakeRisk(),
        sector=_FakeSector(),
        benchmark=None,
        portfolio=_portfolio(),
        profile=RISK_PROFILES[key],
    )
    assert report is not None
    reasons = " | ".join(c.reason for c in report.cards)
    assert expected_cap in reasons, f"{key}: cap {expected_cap} not in reasons: {reasons}"


def test_aggressive_profile_relaxes_concentration():
    """Aggressive 50% cap should not trigger for a 30% single-name position."""
    report = generate_recommendations(
        risk=_FakeRisk(),
        sector=_FakeSector(),
        benchmark=None,
        portfolio=_portfolio(),
        profile=RISK_PROFILES["aggressive"],
    )
    assert report is not None
    concentration_cards = [
        c for c in report.cards if "cap" in c.reason and "ICICIBANK" in c.reason
    ]
    assert not concentration_cards, "aggressive profile should tolerate 30% single-name"
