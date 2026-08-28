"""Tests for data.mutual_funds (mfapi.in integration)."""

from __future__ import annotations

import pandas as pd

from data import mutual_funds as mf


def test_search_schemes_returns_tuples():
    results = mf.search_schemes("parag parikh flexi", limit=5)
    assert isinstance(results, list)
    assert results, "search returned nothing — network or API down"
    assert all(isinstance(code, int) and isinstance(name, str) for code, name in results)
    # Known scheme code for Parag Parikh Flexi Cap Fund should be discoverable.
    codes = [code for code, _ in results]
    assert 119551 in codes or any("Parag Parikh" in name for _, name in results)


def test_fetch_nav_history_shape_and_ascending():
    nav = mf.fetch_nav_history(119551, period="1y")
    assert isinstance(nav, pd.Series)
    assert not nav.empty
    assert nav.index.is_monotonic_increasing, "NAV series must be date-ascending"
    assert nav.index.tz is None, "NAV series must be tz-naive"
    assert (nav > 0).all(), "NAV values must be positive"
    # 1y window should be a strict subset of the full history.
    full = mf.fetch_nav_history(119551, period="max")
    assert len(nav) < len(full)


def test_fetch_nav_history_cache_hit():
    mf.clear_cache(119551)
    first = mf.fetch_nav_history(119551, period="1y")
    second = mf.fetch_nav_history(119551, period="1y")
    assert first.equals(second)


def test_search_schemes_empty_query():
    assert mf.search_schemes("") == []
    assert mf.search_schemes("   ") == []


def test_fetch_invalid_scheme_raises():
    mf.clear_cache(999999999)
    try:
        mf.fetch_nav_history(999999999, period="1mo")
        raise AssertionError("expected MutualFundError for bogus scheme code")
    except mf.MutualFundError:
        pass
