"""
SQLite-backed price cache (L2 tier).

Sits between the in-memory LRU cache (L1) and yfinance.
Provides cross-session persistence so repeated portfolio analyses
don't re-fetch the same data from Yahoo Finance.

Cache hierarchy:
  L1: @lru_cache (in-memory, per-process)  — data/prices.py
  L2: SQLite     (on-disk, cross-session)  — this module
  L3: yfinance   (source of truth)          — fallback

Usage:
    from data.cache import PriceCache
    cache = PriceCache()
    prices = cache.get("RELIANCE.NS")  # None if stale/missing
    cache.set("RELIANCE.NS", close_prices_series)
    cache.clear("RELIANCE.NS")  # force refresh for a ticker
    cache.clear_all()           # full refresh
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from storage.db import (
    get_cached_prices,
    save_cached_prices,
    clear_ticker_cache,
    clear_all_cache,
    clear_stale_cache,
)
from storage.models import CachedPrice


class PriceCache:
    """SQLite-backed L2 price cache with configurable TTL."""

    def __init__(self, ttl_hours: int = 24):
        """
        Args:
            ttl_hours: Max age of cached data before it's considered stale.
                       Default 24h — one trading day.
        """
        self.ttl_hours = ttl_hours

    def get(self, ticker: str) -> Optional[pd.Series]:
        """
        Retrieve cached Close prices for a ticker.

        Returns a pandas Series (index=Date, values=Close) if valid cache hit,
        or None if stale/missing.
        """
        cached = get_cached_prices(ticker, max_age_hours=self.ttl_hours)
        if cached is None or len(cached) == 0:
            return None

        dates = [c.date for c in cached]
        closes = [c.close for c in cached]
        series = pd.Series(closes, index=pd.to_datetime(dates), name=ticker)
        series.index.name = "Date"
        return series

    def set(self, ticker: str, close_series: pd.Series):
        """
        Store Close prices for a ticker in the SQLite cache.

        Args:
            ticker: The yfinance ticker (e.g. "RELIANCE.NS")
            close_series: Series with DateTime index and Close values
        """
        if close_series is None or close_series.empty:
            return

        now = datetime.now()
        prices = []
        for date, close in close_series.items():
            # Handle both Timestamp and string dates
            if hasattr(date, "strftime"):
                date_str = date.strftime("%Y-%m-%d")
            else:
                date_str = str(date)[:10]
            prices.append(CachedPrice(
                ticker=ticker,
                date=date_str,
                close=round(float(close), 2),
            ))

        save_cached_prices(ticker, prices)

    def has(self, ticker: str) -> bool:
        """Check if valid cached data exists for a ticker."""
        return self.get(ticker) is not None

    def clear(self, ticker: str):
        """Remove cached data for a specific ticker (force refresh)."""
        clear_ticker_cache(ticker)

    def clear_all(self):
        """Clear ALL cached price data."""
        clear_all_cache()

    def evict_stale(self):
        """Remove stale entries older than TTL."""
        clear_stale_cache(max_age_hours=self.ttl_hours)
