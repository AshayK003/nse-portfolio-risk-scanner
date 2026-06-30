"""
SQLite-backed price cache (L2 tier) via diskcache.

Sits between the in-memory LRU cache (L1) and the data source (yfinance/nselib).
Provides cross-session persistence so repeated portfolio analyses
don't re-fetch the same data.

Cache hierarchy:
  L1: @lru_cache (in-memory, per-process)  — data/prices.py
  L2: diskcache (on-disk, cross-session)   — this module
  L3: yfinance / nselib (source of truth)  — fallback

Usage:
    from data.cache import PriceCache
    cache = PriceCache()
    prices = cache.get("RELIANCE.NS")  # None if stale/missing
    cache.set("RELIANCE.NS", close_prices_series)
    cache.clear("RELIANCE.NS")  # force refresh for a ticker
    cache.clear_all()           # full refresh
"""

from __future__ import annotations

import pandas as pd

try:
    from diskcache import Cache as _Cache
except ImportError:
    _Cache = None

_CACHE_DIR = "data/.price_cache"


class PriceCache:
    """Diskcache-backed L2 price cache with configurable TTL."""

    def __init__(self, ttl_hours: int = 24, directory: str = _CACHE_DIR):
        self.ttl_hours = ttl_hours
        if _Cache is not None:
            self._cache = _Cache(directory)
        else:
            self._cache = None

    def get(self, ticker: str) -> pd.Series | None:
        if self._cache is None:
            return None
        raw = self._cache.get(ticker)
        if raw is None:
            return None
        series = pd.Series(raw["values"], index=pd.to_datetime(raw["dates"]), name=ticker)
        series.index.name = "Date"
        return series

    def set(self, ticker: str, close_series: pd.Series):
        if self._cache is None or close_series is None or close_series.empty:
            return
        dates = [
            d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10] for d in close_series.index
        ]
        values = [round(float(v), 2) for v in close_series.values]
        self._cache.set(ticker, {"dates": dates, "values": values}, expire=self.ttl_hours * 3600)

    def has(self, ticker: str) -> bool:
        return False if self._cache is None else ticker in self._cache

    def clear(self, ticker: str):
        if self._cache is not None:
            del self._cache[ticker]

    def clear_all(self):
        if self._cache is not None:
            self._cache.clear()

    def evict_stale(self):
        if self._cache is not None:
            self._cache.expire()
