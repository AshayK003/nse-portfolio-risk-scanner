"""
Price data acquisition with multi-tier caching.

Cache tiers:
  L1: @lru_cache (in-memory, per-process)
  L2: diskcache   (on-disk, cross-session)
  L3: nselib (primary) / yfinance (fallback)

NSE equities use nselib as the primary source (official NSE data).
Benchmark indices and tickers unavailable via nselib fall back to yfinance.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import lru_cache

import pandas as pd
from loguru import logger

from engine import Holding

_BATCH_SIZE = 10
_BATCH_DELAY = 1.0
_DEFAULT_PERIOD = "1y"

_L2_CACHE = None

# Attempt to import nselib — optional dependency (install via `pip install nse-risk-scanner[nse]`)
try:
    from nselib import capital_market

    _NSELIB_AVAILABLE = True
    logger.info("nselib available — using NSE data source for equities")
except ImportError:
    _NSELIB_AVAILABLE = False
    logger.info("nselib not installed — falling back to yfinance for all data")


def _get_l2_cache():
    global _L2_CACHE
    if _L2_CACHE is None:
        from data.cache import PriceCache

        _L2_CACHE = PriceCache(ttl_hours=24)
    return _L2_CACHE


def _fetch_via_nselib(ticker: str) -> pd.DataFrame | None:
    """Fetch historical prices from nselib for an NSE equity."""
    if not _NSELIB_AVAILABLE:
        return None
    try:
        clean = ticker.replace(".NS", "")
        raw = capital_market.price_volume_data(symbol=clean, period="1M")
        if raw is None or raw.empty:
            return None
        if "CLOSE_PRICE" not in raw.columns:
            return None
        raw = raw.copy()
        raw["DATE"] = pd.to_datetime(raw["DATE"])
        raw = raw.sort_values("DATE")
        df = raw[["DATE", "CLOSE_PRICE"]].rename(columns={"DATE": "Date", "CLOSE_PRICE": "Close"})
        df = df.set_index("Date")
        df.index.name = "Date"
        return df
    except Exception as exc:
        logger.debug("nselib fetch failed for {t}: {e}", t=ticker, e=exc)
        return None


@lru_cache(maxsize=64)
def _cached_fetch(ticker: str, period: str) -> pd.DataFrame | None:
    """
    Low-level cached fetch: L2 cache → nselib → yfinance.
    """
    l2 = _get_l2_cache()
    cached_series = l2.get(ticker)
    if cached_series is not None and len(cached_series) > 0:
        df = pd.DataFrame({"Close": cached_series})
        return df

    df = None
    if not ticker.startswith("^"):
        df = _fetch_via_nselib(ticker)

    if df is None:
        try:
            import yfinance as yf

            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            if hist is None or hist.empty:
                logger.warning("yfinance returned no data for {t}", t=ticker)
                return None
            df = hist
        except Exception as exc:
            logger.warning("yfinance fetch failed for {t}: {e}", t=ticker, e=exc)
            return None

    if "Close" in df.columns:
        l2.set(ticker, df["Close"])

    return df


def fetch_prices(
    holdings: list[Holding],
    period: str = _DEFAULT_PERIOD,
    force_refresh: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    """
    Fetch historical prices for all holdings.

    Args:
        holdings: List of Holding dataclasses with .ticker
        period: Period string ('1y', '6mo', '3mo', '1mo', 'ytd', 'max')
        force_refresh: If True, bypass all caches
        progress_callback: Optional fn(status_msg) for UI progress updates

    Returns:
        DataFrame with daily closing prices (columns=tickers, index=Date)

    Side effects:
        - Updates each holding's .current_price
        - Updates each holding's .change_pct
        - Populates L2 cache on first fetch
    """
    tickers = [h.ticker for h in holdings]
    if not tickers:
        logger.warning("fetch_prices called with no holdings")
        return pd.DataFrame()

    if force_refresh:
        _cached_fetch.cache_clear()
        _get_l2_cache().clear_all()
        logger.info("Cache cleared (forced refresh)")

    all_prices: dict[str, pd.Series] = {}
    errors: list[str] = []

    for i in range(0, len(tickers), _BATCH_SIZE):
        batch = tickers[i : i + _BATCH_SIZE]

        if progress_callback:
            progress_callback(
                f"Fetching prices: {i + 1}-{min(i + _BATCH_SIZE, len(tickers))} of {len(tickers)}"
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
        raise ValueError(f"Could not fetch prices for any holdings. Failed: {', '.join(errors[:5])}")

    prices = pd.DataFrame(all_prices)
    latest = prices.iloc[-1] if len(prices) > 0 else pd.Series(dtype=float)
    prev_close = prices.iloc[-2] if len(prices) > 1 else pd.Series(dtype=float)

    for h in holdings:
        if h.ticker in latest:
            h.current_price = round(latest[h.ticker], 2)
            if h.ticker in prev_close and prev_close[h.ticker] > 0:
                h.change_pct = round(
                    (latest[h.ticker] - prev_close[h.ticker]) / prev_close[h.ticker] * 100,
                    2,
                )

    return prices


def fetch_prices_refreshed(
    holdings: list[Holding],
    period: str = _DEFAULT_PERIOD,
    progress_callback: Callable[[str], None] | None = None,
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
    """Fetch a benchmark index price series (always uses yfinance for indices)."""
    df = None
    if _NSELIB_AVAILABLE and not ticker.startswith("^"):
        try:
            clean = ticker.replace(".NS", "")
            raw = capital_market.index_data(index=clean, period="1M")
            if raw is not None and not raw.empty and "CLOSE_PRICE" in raw.columns:
                raw = raw.copy()
                raw["DATE"] = pd.to_datetime(raw["DATE"])
                raw = raw.sort_values("DATE")
                df = raw[["DATE", "CLOSE_PRICE"]].rename(columns={"DATE": "Date", "CLOSE_PRICE": "Close"})
                df = df.set_index("Date")
        except Exception:
            pass

    if df is None:
        try:
            hist = _cached_fetch(ticker, period)
            if hist is not None:
                return hist["Close"]
        except Exception:
            pass
    elif not df.empty:
        l2 = _get_l2_cache()
        l2.set(ticker, df["Close"])
        return df["Close"]

    return pd.Series(dtype=float)


def get_stock_info(ticker: str) -> dict:
    """Get company info for a single ticker."""
    try:
        if _NSELIB_AVAILABLE:
            clean = ticker.replace(".NS", "")
            try:
                from nselib import capital_market as cm

                raw = cm.price_volume_data(symbol=clean, period="1d")
                if raw is not None and not raw.empty:
                    return {
                        "name": clean,
                        "sector": "",
                        "industry": "",
                        "market_cap": 0,
                        "pe_ratio": 0,
                        "dividend_yield": 0,
                    }
            except Exception:
                pass
    except Exception:
        pass

    try:
        import yfinance as yf

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
