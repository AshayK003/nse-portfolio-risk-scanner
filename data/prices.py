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

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

import pandas as pd
try:
    from loguru import logger
except ImportError:
    import logging
    import functools

    _FALLBACK_LOGGER = logging.getLogger("nse_risk_scanner")

    def _loguru_compat(level):
        """Wrapper to handle loguru-style {var} kwargs in stdlib logging."""

        def wrapper(msg, *args, **kwargs):
            if kwargs:
                msg = msg.format(**kwargs)
            _FALLBACK_LOGGER.log(level, msg, *args)

        return wrapper

    logger = logging.getLogger("nse_risk_scanner")
    logger.info = _loguru_compat(logging.INFO)
    logger.warning = _loguru_compat(logging.WARNING)
    logger.debug = _loguru_compat(logging.DEBUG)
    logger.error = _loguru_compat(logging.ERROR)

from engine import Holding


def _isnan(v: float) -> bool:
    """Check if a value is NaN — works with both float('nan') and np.nan."""
    try:
        return v != v
    except TypeError:
        return False


_DEFAULT_PERIOD = "1y"

_L2_CACHE = None
_L2_CACHE_LOCK = threading.Lock()

# Max concurrent network requests to yfinance/nselib — prevents rate limiting
# while keeping enough parallelism for fast portfolio loads
_FETCH_SEMAPHORE = threading.Semaphore(5)

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
        with _L2_CACHE_LOCK:
            if _L2_CACHE is None:
                from data.cache import PriceCache

                _L2_CACHE = PriceCache(ttl_hours=24)
    return _L2_CACHE


def _fetch_via_nselib(ticker: str, period: str = "1Y") -> pd.DataFrame | None:
    """Fetch historical prices from nselib for an NSE equity."""
    if not _NSELIB_AVAILABLE:
        return None
    try:
        clean = ticker.replace(".NS", "")
        raw = capital_market.price_volume_data(symbol=clean, period=period)
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


_MAX_RETRIES = 3
_RETRY_BACKOFF = [0.5, 1.5, 3.0]  # seconds between attempts


def _fetch_with_retry(ticker: str, period: str) -> tuple[str, pd.DataFrame | None]:
    """Fetch a single ticker with retry + exponential backoff.

    Returns (ticker, DataFrame | None) so callers can identify which ticker succeeded/failed.
    """
    for attempt in range(_MAX_RETRIES):
        try:
            df = _cached_fetch(ticker, period)
            if df is not None and not df.empty:
                return ticker, df
        except Exception as exc:
            logger.debug(
                "Attempt {a}/{m} failed for {t}: {e}",
                a=attempt + 1,
                m=_MAX_RETRIES,
                t=ticker,
                e=exc,
            )

        if attempt < _MAX_RETRIES - 1:
            time.sleep(_RETRY_BACKOFF[attempt])

    return ticker, None


@lru_cache(maxsize=64)
def _cached_fetch(ticker: str, period: str) -> pd.DataFrame | None:
    """
    Low-level cached fetch: L2 cache → nselib → yfinance.
    """
    l2 = _get_l2_cache()
    cached_series = l2.get(ticker)
    if cached_series is not None and len(cached_series) > 0:
        min_points = {"1mo": 10, "3mo": 40, "6mo": 80, "1y": 180, "2y": 360}
        if len(cached_series) >= min_points.get(period, 20):
            df = pd.DataFrame({"Close": cached_series})
            return df
        logger.debug(
            "Cached data too short ({n} pts) for period {p} — refetching", n=len(cached_series), p=period
        )

    df = None
    if not ticker.startswith("^"):
        with _FETCH_SEMAPHORE:
            df = _fetch_via_nselib(ticker, period)

    if df is None:
        with _FETCH_SEMAPHORE:
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

    Uses parallel fetching with retry for speed and resilience.

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
    completed = 0

    max_workers = min(len(tickers), 8)

    if progress_callback:
        progress_callback(f"Fetching prices for {len(tickers)} stocks...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_with_retry, ticker, period): ticker for ticker in tickers}

        for future in as_completed(futures):
            ticker = futures[future]
            completed += 1

            try:
                t, hist = future.result(timeout=120)
                if hist is not None and "Close" in hist.columns:
                    series = hist["Close"]
                    if series.index.tz is not None:
                        series = series.tz_localize(None)
                    all_prices[t] = series
                else:
                    errors.append(t)
            except TimeoutError:
                errors.append(f"{ticker}: timeout (>120s)")
            except Exception as e:
                errors.append(f"{ticker}: {e}")

            if progress_callback and completed % 5 == 0:
                progress_callback(f"Fetched {completed}/{len(tickers)} stocks...")

    if progress_callback:
        progress_callback("Processing prices...")

    if not all_prices:
        raise ValueError(f"Could not fetch prices for any holdings. Failed: {', '.join(errors[:5])}")

    if errors:
        logger.warning(
            "Failed to fetch {n} tickers: {e}",
            n=len(errors),
            e=", ".join(errors[:10]),
        )

    prices = pd.DataFrame(all_prices)
    # Forward-fill so tickers with shorter histories still get their latest price
    latest = prices.ffill().iloc[-1] if len(prices) > 0 else pd.Series(dtype=float)

    for h in holdings:
        if h.ticker in latest and not _isnan(latest[h.ticker]):
            h.current_price = round(latest[h.ticker], 2)
            if h.avg_price > 0:
                h.change_pct = round((h.current_price - h.avg_price) / h.avg_price * 100, 2)

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
            raw = capital_market.index_data(index=clean, period=period)
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
