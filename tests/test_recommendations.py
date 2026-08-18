"""
Tests for the recommendation engine.
"""

from engine.recommendations import (
    MarketData,
    PortfolioSnapshot,
    UserProfile,
    run_recommendation_engine,
)
from engine.recommendations.types import FiiDiiBias, RegimeContext


def _make_snapshot(cash_available=0):
    return PortfolioSnapshot(
        holdings=[
            {"ticker": "HDFCBANK.NS", "name": "HDFC Bank", "quantity": 24, "avg_price": 765.36, "current_price": 725.50},
            {"ticker": "NIFTYBEES.NS", "name": "Nifty 50 ETF", "quantity": 60, "avg_price": 257.11, "current_price": 276.35},
            {"ticker": "POWERGRID.NS", "name": "Power Grid", "quantity": 54, "avg_price": 276.61, "current_price": 267.20},
            {"ticker": "MIDCAPETF.NS", "name": "Midcap ETF", "quantity": 500, "avg_price": 20.51, "current_price": 23.94},
            {"ticker": "NEXT50IETF.NS", "name": "Next 50 ETF", "quantity": 150, "avg_price": 74.73, "current_price": 78.82},
            {"ticker": "ENERGY.NS", "name": "Energy ETF", "quantity": 279, "avg_price": 40.49, "current_price": 38.92},
            {"ticker": "GOLDBEES.NS", "name": "Gold ETF", "quantity": 65, "avg_price": 126.29, "current_price": 126.52},
            {"ticker": "MODEFENCE.NS", "name": "Defence ETF", "quantity": 70, "avg_price": 101.21, "current_price": 108.90},
            {"ticker": "MONIFTY500.NS", "name": "Nifty 500 ETF", "quantity": 280, "avg_price": 23.61, "current_price": 24.13},
            {"ticker": "MAKEINDIA.NS", "name": "Make India ETF", "quantity": 40, "avg_price": 161.49, "current_price": 168.85},
            {"ticker": "VEDL.NS", "name": "Vedanta", "quantity": 25, "avg_price": 276.40, "current_price": 267.85},
            {"ticker": "MASPTOP50.NS", "name": "S&P 500 ETF", "quantity": 64, "avg_price": 79.00, "current_price": 81.02},
            {"ticker": "CASTROLIND.NS", "name": "Castrol India", "quantity": 30, "avg_price": 192.50, "current_price": 187.49},
            {"ticker": "LIQUIDCASE.NS", "name": "Liquid Case", "quantity": 42, "avg_price": 114.80, "current_price": 115.52},
            {"ticker": "NMDC.NS", "name": "NMDC", "quantity": 50, "avg_price": 86.70, "current_price": 83.87},
            {"ticker": "COALINDIA.NS", "name": "Coal India", "quantity": 9, "avg_price": 430.85, "current_price": 409.25},
            {"ticker": "GROWW.NS", "name": "Groww", "quantity": 15, "avg_price": 192.10, "current_price": 195.25},
            {"ticker": "SILVERBEES.NS", "name": "Silver ETF", "quantity": 10, "avg_price": 208.92, "current_price": 222.31},
            {"ticker": "METAL.NS", "name": "Metal ETF", "quantity": 20, "avg_price": 13.64, "current_price": 13.18},
        ],
        total_value=145876,
        cash_available=cash_available,
        sector_weights={
            "Banking": 12.2, "Broad Market": 32.8, "Power": 10.1, "Energy": 7.6,
            "Gold": 5.8, "Defence": 5.4, "Metals": 7.8, "International": 6.5,
            "Manufacturing": 4.7, "Lubricants": 3.9, "Cash": 3.3, "Mining": 2.9,
            "Fintech": 2.1, "Small Cap": 1.6
        },
        asset_class_weights={"Equity": 100.0},
    )


def _make_snapshot_positive_bias(cash_available=60000):
    """Portfolio with mostly winners for FII/DII test"""
    return PortfolioSnapshot(
        holdings=[
            {"ticker": "HDFCBANK.NS", "name": "HDFC Bank", "quantity": 24, "avg_price": 700.00, "current_price": 800.00},
            {"ticker": "NIFTYBEES.NS", "name": "Nifty 50 ETF", "quantity": 60, "avg_price": 250.00, "current_price": 280.00},
            {"ticker": "POWERGRID.NS", "name": "Power Grid", "quantity": 54, "avg_price": 250.00, "current_price": 280.00},
            {"ticker": "NIFTYBEES.NS", "name": "Nifty 50 ETF", "quantity": 60, "avg_price": 250.00, "current_price": 280.00},
            {"ticker": "MONIFTY500.NS", "name": "Nifty 500 ETF", "quantity": 280, "avg_price": 22.00, "current_price": 25.00},
            {"ticker": "NEXT50IETF.NS", "name": "Next 50 ETF", "quantity": 150, "avg_price": 70.00, "current_price": 80.00},
        ],
        total_value=150000,
        cash_available=cash_available,
        sector_weights={"Banking": 20.0, "Broad Market": 50.0, "Power": 15.0},
        asset_class_weights={"Equity": 100.0},
    )


def _make_market_data(regime=RegimeContext.BULL, vix=13.5, adx=25.0, breadth=1.2, fii_dii=FiiDiiBias.NEUTRAL, expiry=False):
    return MarketData(
        vix=vix,
        adx=adx,
        nifty_ma200_dist_pct=5.2,
        breadth_ad_ratio=breadth,
        fii_dii_bias=fii_dii,
        is_expiry_week=expiry,
        regime=regime,
    )


def _make_user_profile(cash_floor=50000):
    return UserProfile(
        max_stcg_budget=100000,
        max_ltcg_budget=500000,
        max_single_trade_pct=10.0,
        max_sector_weight=20.0,
        max_single_name_weight=15.0,
        min_cash_floor=cash_floor,
        tax_loss_harvest_enabled=True,
        horizon_years=5,
    )


def test_recommendation_engine_basic():
    """Basic integration test - engine runs without errors"""
    snapshot = _make_snapshot()
    market = _make_market_data()
    profile = _make_user_profile()

    cards, report = run_recommendation_engine(snapshot, market, profile)

    assert isinstance(cards, list)
    assert len(cards) > 0
    for card in cards:
        assert hasattr(card, "title")
        assert hasattr(card, "action")
        assert hasattr(card, "confidence")
        assert 0 <= card.confidence <= 1


def test_sector_concentration_flagged():
    """Broad Market at 32.8% > 20% cap should trigger trim"""
    cards, report = run_recommendation_engine(_make_snapshot(), _make_market_data(), _make_user_profile())

    broad_market_cards = [c for c in cards if "Broad Market" in c.reason or "concentration" in c.reason.lower()]
    assert len(broad_market_cards) > 0, "Should flag Broad Market concentration"


def test_etf_overlap_flagged():
    """Nifty 50 ETFs (NIFTYBEES, MONIFTY500, NEXT50IETF) should trigger overlap"""
    cards, report = run_recommendation_engine(_make_snapshot(), _make_market_data(), _make_user_profile())

    overlap_cards = [c for c in cards if "overlap" in c.reason.lower()]
    assert len(overlap_cards) >= 2, "Should flag Nifty 50 ETF overlap (NIFTYBEES, MONIFTY500, NEXT50IETF)"


def test_vix_spike_blocks_shorts():
    """VIX > 28 should block shorts and reduce longs"""
    cards, report = run_recommendation_engine(_make_snapshot(), _make_market_data(vix=30), _make_user_profile())

    immediate_cards = [c for c in cards if c.urgency.value == "immediate"]
    assert len(immediate_cards) > 0, "VIX spike should generate immediate actions"


def test_adx_doldrums_blocks_breakouts():
    """ADX < 15 should produce BLOCK verdict (governance rule)"""
    snapshot = _make_snapshot(cash_available=60000)  # Avoid cash floor dominating
    market = _make_market_data(adx=10)
    profile = _make_user_profile(cash_floor=50000)

    cards, report = run_recommendation_engine(snapshot, market, profile)

    # Check rule_verdicts for BLOCK action from ADX rule
    adx_blocks = []
    for card in cards:
        for verdict in card.rule_verdicts:
            if verdict.rule_name == "regime_adx_doldrums" and verdict.action.value == "block":
                adx_blocks.append(verdict)

    assert len(adx_blocks) > 0, "ADX < 15 should produce BLOCK verdict in rule_verdicts"


def test_cash_floor_triggers_sells():
    """Cash below floor should trigger sells to raise cash"""
    cards, report = run_recommendation_engine(_make_snapshot(), _make_market_data(), _make_user_profile(cash_floor=50000))

    sell_cards = [c for c in cards if c.action.value == "sell"]
    assert len(sell_cards) > 0, "Cash floor should trigger sells"


def test_regime_bull_no_vix_spike():
    """Bull market with normal VIX should not trigger panic rules"""
    cards, report = run_recommendation_engine(_make_snapshot(cash_available=60000), _make_market_data(vix=12), _make_user_profile(cash_floor=50000))

    vix_cards = [c for c in cards if "VIX" in c.reason]
    assert len(vix_cards) == 0, "Normal VIX should not trigger VIX spike rule"


def test_expiry_week_reduces_positions():
    """Expiry week should reduce all position sizes"""
    cards, report = run_recommendation_engine(_make_snapshot(cash_available=60000), _make_market_data(expiry=True), _make_user_profile(cash_floor=50000))

    trim_cards = [c for c in cards if c.action.value == "trim" and "Expiry week" in c.reason]
    assert len(trim_cards) > 0, "Expiry week should generate trim recommendations"


def test_breadth_confirmation():
    """A/D ratio misaligned with portfolio bias should reduce"""
    cards, report = run_recommendation_engine(_make_snapshot(cash_available=60000), _make_market_data(breadth=0.5), _make_user_profile(cash_floor=50000))

    breadth_cards = [c for c in cards if "breadth" in c.reason.lower() or "A/D" in c.reason]
    assert len(breadth_cards) > 0, "Breadth misalignment should trigger reduction"


def test_fii_dii_confluence():
    """FII/DII bearish with long portfolio (positive bias) should reduce longs"""
    cards, report = run_recommendation_engine(_make_snapshot_positive_bias(), _make_market_data(fii_dii=FiiDiiBias.BEARISH), _make_user_profile(cash_floor=50000))

    # Check if FII/DII rule fired in any card's rule_verdicts
    fii_verdicts = []
    for card in cards:
        for verdict in card.rule_verdicts:
            if verdict.rule_name == "fii_dii_confluence":
                fii_verdicts.append(verdict)

    assert len(fii_verdicts) > 0, "FII/DII bearish should trigger trim in rule_verdicts"


def test_recommendation_cards_have_required_fields():
    """Every card should have all required fields for frontend"""
    cards, report = run_recommendation_engine(_make_snapshot(cash_available=60000), _make_market_data(), _make_user_profile(cash_floor=50000))

    for card in cards:
        assert card.id
        assert card.title
        assert card.priority >= 1
        assert card.urgency.value in ("immediate", "near_term", "routine")
        assert card.action.value in ("buy", "sell", "trim", "hold", "block")
        assert card.reason
        assert card.regime_context.value in ("bull", "neutral", "bear", "crisis")
        assert isinstance(card.rule_verdicts, list)
        assert isinstance(card.tax_breakdown, dict)
        assert isinstance(card.impact_breakdown, dict)
        assert isinstance(card.net_risk_reduction_bps, int)
        assert 0 <= card.confidence <= 1
        assert isinstance(card.guardrails, list)
        assert isinstance(card.alternatives, list)


def test_no_duplicate_cards_for_same_ticker_action():
    """Deduplication should prevent multiple cards for same ticker+action"""
    cards, report = run_recommendation_engine(_make_snapshot(), _make_market_data(), _make_user_profile(cash_floor=50000))

    seen = set()
    for card in cards:
        if card.action.value != "block":
            key = (card.action.value, tuple(card.tickers))
            assert key not in seen, f"Duplicate card for {key}"
            seen.add(key)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
