"""
India mutual fund data via mfapi.in (no API key required).

Endpoints:
  GET /mf/search?q={query}          -> [{"schemeCode": int, "schemeName": str}, ...]
  GET /mf/{scheme_code}             -> {"meta": {...}, "data": [{"date": "DD-MM-YYYY", "nav": "float"}, ...]}

NAV data is returned newest-first with full available history. This module
normalizes it to a tz-naive pd.Series (Date index, "Close" values) consistent
with the equity price series produced by data.prices, so downstream analytics
can consume either source through the same shape.

No third-party dependency: uses urllib from the standard library.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import pandas as pd

from engine._log import logger

_BASE_URL = "https://api.mfapi.in"
_TIMEOUT = 15  # seconds per request
_MAX_RETRIES = 3
_RETRY_BACKOFF = (0.5, 1.5, 3.0)  # seconds

# Period -> approximate calendar days used to slice full NAV history.
_PERIOD_DAYS = {
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 730,
    "max": 10 ** 8,
}

# Bounded in-memory cache: scheme_code -> pd.Series
_NAV_CACHE: dict[int, pd.Series] = {}
_NAV_CACHE_LOCK = threading.Lock()


class MutualFundError(ValueError):
    """Raised when a mutual fund fetch fails outright (bad code, network death)."""


def _http_get_json(path: str) -> dict | list:
    """Fetch a JSON resource from mfapi.in with retry + backoff.

    Raises MutualFundError on persistent failure.
    """
    url = f"{_BASE_URL}{path}"
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_exc = exc
            logger.debug("mfapi.in fetch attempt {a}/{m} failed for {p}: {e}",
                         a=attempt + 1, m=_MAX_RETRIES, p=path, e=exc)
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BACKOFF[attempt])
    raise MutualFundError(f"mfapi.in request failed after {_MAX_RETRIES} attempts: {url} ({last_exc})")


def search_schemes(query: str, limit: int = 10) -> list[tuple[int, str]]:
    """Search India mutual fund schemes by name.

    Args:
        query: Free-text scheme name fragment (e.g. "parag parikh flexi").
        limit: Max results to return.

    Returns:
        List of (scheme_code, scheme_name) tuples, newest-relevance-ordered.
        Returns [] on failure rather than raising.
    """
    if not query or not query.strip():
        return []
    try:
        raw = _http_get_json(f"/mf/search?q={urllib.parse.quote_plus(query.strip())}")
    except MutualFundError as exc:
        logger.warning("scheme search failed for {q}: {e}", q=query, e=exc)
        return []
    if not isinstance(raw, list):
        return []
    results = [(int(r["schemeCode"]), str(r["schemeName"])) for r in raw if "schemeCode" in r]
    return results[:limit]


def fetch_nav_history(scheme_code: int, period: str = "1y", force_refresh: bool = False) -> pd.Series:
    """Fetch NAV history for a scheme code as a tz-naive Date-indexed Series.

    Args:
        scheme_code: Numeric mfapi.in scheme code (e.g. 119551).
        period: One of 1mo/3mo/6mo/1y/2y/max. Slices full history by calendar days.
        force_refresh: Bypass the in-memory cache.

    Returns:
        pd.Series of NAV values indexed by Date (ascending), named by scheme_code.
        The series mirrors the equity "Close" shape from data.prices.

    Raises:
        MutualFundError: if the scheme code is invalid or the source is unreachable.
    """
    if not force_refresh:
        with _NAV_CACHE_LOCK:
            cached = _NAV_CACHE.get(scheme_code)
        if cached is not None:
            return _slice_period(cached, period)

    try:
        raw = _http_get_json(f"/mf/{int(scheme_code)}")
    except MutualFundError:
        raise

    if not isinstance(raw, dict) or "data" not in raw or not raw["data"]:
        raise MutualFundError(f"No NAV data for scheme {scheme_code}")

    dates: list[datetime] = []
    values: list[float] = []
    try:
        for row in raw["data"]:
            dates.append(datetime.strptime(row["date"], "%d-%m-%Y"))
            values.append(float(row["nav"]))
    except (KeyError, ValueError) as exc:
        raise MutualFundError(f"Malformed NAV row for scheme {scheme_code}: {exc}") from exc

    # API returns newest-first; sort ascending for time-series consistency.
    series = pd.Series(values, index=pd.DatetimeIndex(dates, name="Date"), name=str(scheme_code))
    series = series.sort_index()
    series.index.name = "Date"

    with _NAV_CACHE_LOCK:
        _NAV_CACHE[scheme_code] = series

    return _slice_period(series, period)


def _slice_period(series: pd.Series, period: str) -> pd.Series:
    """Return the trailing window of a NAV series for the requested period."""
    days = _PERIOD_DAYS.get(period.lower(), _PERIOD_DAYS["1y"])
    if days >= 10 ** 8:
        return series
    cutoff = series.index.max() - timedelta(days=days)
    return series[series.index >= cutoff]


def clear_cache(scheme_code: int | None = None) -> None:
    """Clear the in-memory NAV cache (all schemes, or one)."""
    with _NAV_CACHE_LOCK:
        if scheme_code is None:
            _NAV_CACHE.clear()
        else:
            _NAV_CACHE.pop(scheme_code, None)
