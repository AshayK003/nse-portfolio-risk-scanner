"""
Price data acquisition.
Wraps yfinance with multi-tier caching for speed and rate-limit safety.

Cache tiers:
  L1: @lru_cache (in-memory, per-process) — avoids repeat yfinance calls
  L2: SQLite     (on-disk, cross-session) — survives app restarts
  L3: yfinance   (source of truth)        — fallback when cache misses
"""
from __future__ import annotations
import time
from datetime import datetime, timedelta
from typing import Optional, Callable
from functools import lru_cache

import pandas as pd
import yfinance as yf

from engine import Holding

# Batch size to avoid yfinance rate limiting
_BATCH_SIZE = 10
_BATCH_DELAY = 1.0  # seconds between batches

# Max history requested
_DEFAULT_PERIOD = "1y"

# L2 cache — lazy import to avoid circular deps at module level
_L2_CACHE = None


def _get_l2_cache():
    """Get the L2 SQLite cache singleton."""
    global _L2_CACHE
    if _L2_CACHE is None:
        from data.cache import PriceCache
        _L2_CACHE = PriceCache(ttl_hours=24)
    return _L2_CACHE


@lru_cache(maxsize=64)
def _cached_fetch(ticker: str, period: str) -> pd.DataFrame | None:
    """
    Low-level cached yfinance fetch (L1: in-memory).

    Also populates the L2 (SQLite) cache on first fetch so future sessions
    can reuse without hitting yfinance again.
    """
    # First, check L2 cache
    l2 = _get_l2_cache()
    cached_series = l2.get(ticker)
    if cached_series is not None and len(cached_series) > 0:
        # Convert series back to DataFrame with 'Close' column
        df = pd.DataFrame({"Close": cached_series})
        return df

    # L2 miss — fetch from yfinance (L3)
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty:
            return None

        # Populate L2 cache for future sessions
        if "Close" in hist.columns:
            l2.set(ticker, hist["Close"])

        return hist
    except Exception:
        return None


def fetch_prices(
    holdings: list[Holding],
    period: str = _DEFAULT_PERIOD,
    force_refresh: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> pd.DataFrame:
    """
    Fetch historical prices for all holdings.

    Args:
        holdings: List of Holding dataclasses with .ticker
        period: yfinance period string ('1y', '6mo', '3mo', '1mo', 'ytd', 'max')
        force_refresh: If True, bypass both L1 and L2 caches
        progress_callback: Optional fn(status_msg) for UI progress updates

    Returns:
        DataFrame with daily closing prices (columns = tickers, index = Date)

    Side effects:
        - Updates each holding's .current_price
        - Updates each holding's .change_pct
        - Populates L2 (SQLite) cache on first fetch
    """
    tickers = [h.ticker for h in holdings]
    if not tickers:
        return pd.DataFrame()

    if force_refresh:
        # Clear all cache tiers
        _cached_fetch.cache_clear()
        _get_l2_cache().clear_all()

    all_prices: dict[str, pd.Series] = {}
    errors: list[str] = []

    # Fetch in batches
    for i in range(0, len(tickers), _BATCH_SIZE):
        batch = tickers[i:i + _BATCH_SIZE]

        if progress_callback:
            progress_callback(
                f"Fetching prices: {i+1}-{min(i+_BATCH_SIZE, len(tickers))} of {len(tickers)}"
            )

        for ticker in batch:
            try:
                hist = _cached_fetch(ticker, period)
                if hist is not None and not hist.empty:
                    all_prices[ticker] = hist["Close"]
                else:
                    errors.append(ticker)
            except Exception as e:
                errors.append(f"{ticker}: {e}")

        if i + _BATCH_SIZE < len(tickers):
            time.sleep(_BATCH_DELAY)

    if not all_prices:
        raise ValueError(
            f"Could not fetch prices for any holdings. "
            f"Failed: {', '.join(errors[:5])}"
        )

    # Build DataFrame
    prices = pd.DataFrame(all_prices)

    # Update current prices on holdings
    latest = prices.iloc[-1] if len(prices) > 0 else pd.Series(dtype=float)
    prev_close = prices.iloc[-2] if len(prices) > 1 else pd.Series(dtype=float)

    for h in holdings:
        if h.ticker in latest:
            h.current_price = round(latest[h.ticker], 2)
            if h.ticker in prev_close and prev_close[h.ticker] > 0:
                h.change_pct = round(
                    (latest[h.ticker] - prev_close[h.ticker]) / prev_close[h.ticker] * 100,
                    2
                )

    return prices


def fetch_prices_refreshed(
    holdings: list[Holding],
    period: str = _DEFAULT_PERIOD,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> pd.DataFrame:
    """Force-refresh all prices (bypass all caches)."""
    return fetch_prices(
        holdings=holdings,
        period=period,
        force_refresh=True,
        progress_callback=progress_callback,
    )


def fetch_benchmark(
    ticker: str = "^NSEI",
    period: str = _DEFAULT_PERIOD,
) -> pd.Series:
    """Fetch a benchmark index price series."""
    try:
        hist = _cached_fetch(ticker, period)
        if hist is not None:
            return hist["Close"]
    except Exception:
        pass
    return pd.Series(dtype=float)


def get_stock_info(ticker: str) -> dict:
    """Get company info for a single ticker."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "name": info.get("longName", info.get("shortName", ticker)),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", ""),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", 0),
            "dividend_yield": info.get("dividendYield", 0),
        }
    except Exception:
        return {"name": ticker, "sector": "Unknown"}


def list_available_benchmarks() -> dict[str, str]:
    """Return dict of {display_name: yfinance_ticker}."""
    from engine.benchmark import BENCHMARK_TICKERS
    return dict(BENCHMARK_TICKERS)


def get_cache_stats() -> dict:
    """Get cache usage statistics."""
    l1_info = _cached_fetch.cache_info()
    return {
        "l1_hits": l1_info.hits,
        "l1_misses": l1_info.misses,
        "l1_currsize": l1_info.currsize,
        "l1_maxsize": l1_info.maxsize,
    }
