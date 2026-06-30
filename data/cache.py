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

from datetime import timedelta

import pandas as pd
from diskcache import Cache

_CACHE_DIR = "data/.price_cache"


class PriceCache:
    """Diskcache-backed L2 price cache with configurable TTL."""

    def __init__(self, ttl_hours: int = 24, directory: str = _CACHE_DIR):
        self.ttl_hours = ttl_hours
        self._cache = Cache(directory)

    def get(self, ticker: str) -> pd.Series | None:
        raw = self._cache.get(ticker)
        if raw is None:
            return None
        series = pd.Series(raw["values"], index=pd.to_datetime(raw["dates"]), name=ticker)
        series.index.name = "Date"
        return series

    def set(self, ticker: str, close_series: pd.Series):
        if close_series is None or close_series.empty:
            return
        dates = [
            d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10] for d in close_series.index
        ]
        values = [round(float(v), 2) for v in close_series.values]
        self._cache.set(ticker, {"dates": dates, "values": values}, expire=timedelta(hours=self.ttl_hours))

    def has(self, ticker: str) -> bool:
        return ticker in self._cache

    def clear(self, ticker: str):
        del self._cache[ticker]

    def clear_all(self):
        self._cache.clear()

    def evict_stale(self):
        self._cache.expire()
