"""Tests for _LRUCache and _isnan in data/prices.py (#30)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.prices import _isnan, _LRUCache


def _df(value: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame({"Close": [value]})


class TestLRUCache:
    def test_set_get_roundtrip(self):
        cache = _LRUCache(maxsize=4)
        cache[("A", "1y")] = _df(5.0)
        assert ("A", "1y") in cache
        assert cache[("A", "1y")].equals(_df(5.0))

    def test_len_and_contains(self):
        cache = _LRUCache(maxsize=4)
        assert len(cache) == 0
        assert ("A", "1y") not in cache
        cache[("A", "1y")] = _df()
        assert len(cache) == 1

    def test_evicts_oldest_when_over_maxsize(self):
        cache = _LRUCache(maxsize=2)
        cache[("A", "1y")] = _df(1)
        cache[("B", "1y")] = _df(2)
        cache[("C", "1y")] = _df(3)  # A evicted (oldest)
        assert ("A", "1y") not in cache
        assert ("B", "1y") in cache
        assert ("C", "1y") in cache
        assert len(cache) == 2

    def test_get_refreshes_recency(self):
        cache = _LRUCache(maxsize=2)
        cache[("A", "1y")] = _df(1)
        cache[("B", "1y")] = _df(2)
        _ = cache[("A", "1y")]  # touch A -> B becomes oldest
        cache[("C", "1y")] = _df(3)
        assert ("A", "1y") in cache  # survived: recently used
        assert ("B", "1y") not in cache  # evicted instead

    def test_clear(self):
        cache = _LRUCache(maxsize=4)
        cache[("A", "1y")] = _df()
        cache.clear()
        assert len(cache) == 0
        assert ("A", "1y") not in cache

    def test_overwrite_same_key(self):
        cache = _LRUCache(maxsize=4)
        cache[("A", "1y")] = _df(1)
        cache[("A", "1y")] = _df(9)
        assert len(cache) == 1
        assert cache[("A", "1y")].equals(_df(9))


class TestIsnan:
    def test_float_nan_detected(self):
        assert _isnan(float("nan")) is True

    def test_np_nan_detected(self):
        assert _isnan(np.nan) is True

    def test_finite_values_pass(self):
        assert _isnan(0.0) is False
        assert _isnan(-1.5) is False
        assert _isnan(float("inf")) is False

    def test_non_numeric_returns_false(self):
        # TypeError path — strings/objects are not NaN
        assert _isnan("text") is False  # type: ignore[arg-type]
