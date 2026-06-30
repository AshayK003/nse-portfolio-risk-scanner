"""Tests for the PriceCache (diskcache-backed L2 cache)."""

from __future__ import annotations

import pandas as pd

from data.cache import PriceCache


def _make_series(values: list[float] | None = None, name: str = "TEST.NS") -> pd.Series:
    if values is None:
        values = [100.0, 101.5, 102.0]
    dates = pd.bdate_range(end="2024-01-01", periods=len(values))
    s = pd.Series(values, index=dates, name=name)
    s.index.name = "Date"
    return s


class TestPriceCacheRoundTrip:
    def test_set_then_get(self, tmp_cache_dir):
        cache = PriceCache(ttl_hours=24, directory=tmp_cache_dir)
        series = _make_series()

        cache.set("RELIANCE.NS", series)
        result = cache.get("RELIANCE.NS")

        assert result is not None
        assert len(result) == 3
        assert result.name == "RELIANCE.NS"
        assert result.index.name == "Date"
        # Values and dates match (ignore freq metadata lost in serialization)
        assert list(result.values) == list(series.values)
        assert list(result.index) == list(series.index)

    def test_get_missing_ticker(self, tmp_cache_dir):
        cache = PriceCache(ttl_hours=24, directory=tmp_cache_dir)
        assert cache.get("NONEXISTENT.NS") is None

    def test_has_ticker(self, tmp_cache_dir):
        cache = PriceCache(ttl_hours=24, directory=tmp_cache_dir)
        assert not cache.has("RELIANCE.NS")

        cache.set("RELIANCE.NS", _make_series())
        assert cache.has("RELIANCE.NS")

    def test_overwrite_existing(self, tmp_cache_dir):
        cache = PriceCache(ttl_hours=24, directory=tmp_cache_dir)
        cache.set("RELIANCE.NS", _make_series([100.0]))
        cache.set("RELIANCE.NS", _make_series([200.0, 201.0]))

        result = cache.get("RELIANCE.NS")
        assert result is not None
        assert len(result) == 2
        assert result.iloc[0] == 200.0


class TestPriceCacheClear:
    def test_clear_single_ticker(self, tmp_cache_dir):
        cache = PriceCache(ttl_hours=24, directory=tmp_cache_dir)
        cache.set("A.NS", _make_series(name="A.NS"))
        cache.set("B.NS", _make_series(name="B.NS"))

        cache.clear("A.NS")

        assert cache.get("A.NS") is None
        assert cache.get("B.NS") is not None

    def test_clear_all(self, tmp_cache_dir):
        cache = PriceCache(ttl_hours=24, directory=tmp_cache_dir)
        cache.set("A.NS", _make_series(name="A.NS"))
        cache.set("B.NS", _make_series(name="B.NS"))

        cache.clear_all()

        assert cache.get("A.NS") is None
        assert cache.get("B.NS") is None


class TestPriceCacheEdgeCases:
    def test_set_empty_series_is_noop(self, tmp_cache_dir):
        cache = PriceCache(ttl_hours=24, directory=tmp_cache_dir)
        cache.set("EMPTY.NS", pd.Series(dtype=float))
        assert cache.get("EMPTY.NS") is None

    def test_set_none_is_noop(self, tmp_cache_dir):
        cache = PriceCache(ttl_hours=24, directory=tmp_cache_dir)
        cache.set("NONE.NS", None)
        assert cache.get("NONE.NS") is None

    def test_has_when_cache_disabled(self, tmp_cache_dir):
        """PriceCache works even when diskcache is unavailable (_Cache=None)."""
        cache = PriceCache(ttl_hours=24, directory=tmp_cache_dir)
        # Force _cache to None to simulate missing dependency
        cache._cache = None
        assert cache.has("X.NS") is False
        assert cache.get("X.NS") is None
        cache.clear("X.NS")  # should not raise
        cache.clear_all()  # should not raise

    def test_evict_stale(self, tmp_cache_dir):
        cache = PriceCache(ttl_hours=24, directory=tmp_cache_dir)
        cache.set("STALE.NS", _make_series())
        cache.evict_stale()  # should not raise

    def test_large_series_round_trip(self, tmp_cache_dir):
        cache = PriceCache(ttl_hours=24, directory=tmp_cache_dir)
        values = list(range(1000))
        series = pd.Series(
            [float(v) for v in values],
            index=pd.bdate_range(end="2024-01-01", periods=1000),
            name="BIG.NS",
        )
        series.index.name = "Date"
        cache.set("BIG.NS", series)
        result = cache.get("BIG.NS")
        assert result is not None
        assert len(result) == 1000
