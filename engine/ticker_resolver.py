"""
Robust NSE ticker resolution for the Portfolio Risk Scanner.

Loads the ticker map + alias engine from data/tickers.json (lazy, cached).
Ports the proven resolution engine from the NSE Sentiment Analyzer
(316 stock/ETF entries + 465 company-name aliases). Resolution order:

  1. Exact ticker match (offline, instant)
  2. Exact alias match (company name → ticker)
  3. Company-name reverse lookup (exact + partial contains)
  4. Ticker prefix match
  5. Live Yahoo Finance search fallback (network, cached)

This keeps ticker ↔ name in sync reliably: every resolution returns both the
normalized ticker AND the canonical company name, so the UI never shows a
ticker with a stale or mismatched name.
"""

from __future__ import annotations

import functools
import json
import os
import threading

_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tickers.json")


@functools.lru_cache(maxsize=1)
def _load_ticker_data() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Load ticker map + aliases from JSON. Returns (NSE_TICKERS, ALIASES, ALIAS_LOOKUP)."""
    with open(_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    tickers = data["tickers"]
    aliases = data["aliases"]
    alias_lookup = {}
    for ak, at in aliases.items():
        au = ak.strip().upper()
        if au not in alias_lookup:
            alias_lookup[au] = at
    return tickers, aliases, alias_lookup


def _get_tickers() -> dict[str, str]:
    return _load_ticker_data()[0]


def _get_alias_lookup() -> dict[str, str]:
    return _load_ticker_data()[2]


# Module-level lazy accessors (backward-compatible with code/tests importing these names)
def __getattr__(name: str):
    if name == "NSE_TICKERS":
        return _get_tickers()
    if name == "ALIASES":
        return _load_ticker_data()[1]
    raise AttributeError(f"module 'engine.ticker_resolver' has no attribute {name!r}")


# In-memory cache for online lookups (avoids repeated network calls)
_online_ticker_cache: dict[str, tuple[str | None, str | None]] = {}
_online_cache_lock = threading.Lock()
_MAX_ONLINE_CACHE = 500


def _search_yahoo_finance(query: str) -> tuple[str | None, str | None]:
    """Search Yahoo Finance REST API for NSE ticker. Fast (~200ms)."""
    try:
        import requests

        url = (
            "https://query2.finance.yahoo.com/v1/finance/search?q="
            f"{requests.utils.quote(query)}&quotesCount=10&newsCount=0"
        )
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
        if r.status_code != 200:
            return None, None
        data = r.json()
        quotes = data.get("quotes", [])
        for q_item in quotes:
            sym = q_item.get("symbol", "")
            exch = q_item.get("exchange", "")
            if exch == "NSI" and sym.endswith(".NS"):
                return sym.replace(".NS", ""), q_item.get("shortname", query)
        for q_item in quotes:
            sym = q_item.get("symbol", "")
            if sym.endswith(".NS"):
                return sym.replace(".NS", ""), q_item.get("shortname", query)
    except (requests.RequestException, json.JSONDecodeError, KeyError, AttributeError):
        pass
    return None, None


def _search_ticker_online(query: str) -> tuple[str | None, str | None]:
    """Search for NSE ticker by company name using Yahoo Finance REST API.

    Returns (ticker, name) or (None, None). Cached in-memory.
    """
    q = query.strip()
    if not q or len(q) < 2:
        return None, None
    q_upper = q.upper()
    with _online_cache_lock:
        cached = _online_ticker_cache.get(q_upper)
        if cached is not None:
            return cached
    result = _search_yahoo_finance(q)
    with _online_cache_lock:
        if len(_online_ticker_cache) < _MAX_ONLINE_CACHE:
            _online_ticker_cache[q_upper] = result
    return result


def resolve_ticker(raw_input: str) -> tuple[str | None, str | None]:
    """Resolve user input to a valid NSE ticker symbol + company name.

    Handles tickers, company names, aliases, and partial matches.
    Returns (ticker, company_name) or (None, None) if unresolved.

    Resolution order (fast → slow):
      1. Exact ticker match
      2. Exact alias match (e.g. "HDFC BANK" → "HDFCBANK")
      3. Company name reverse lookup (exact + partial contains)
      4. Ticker prefix match
      5. Yahoo Finance search fallback (network, ~200ms, cached)
    """
    NSE_TICKERS = _get_tickers()  # noqa: N806
    _ALIAS_LOOKUP = _get_alias_lookup()  # noqa: N806

    if not raw_input or not raw_input.strip():
        return None, None
    q = raw_input.strip().upper().replace(".NS", "").replace(".BO", "")
    # 1. Exact ticker symbol match
    if q in NSE_TICKERS:
        return q, NSE_TICKERS[q]
    # 2. Exact alias match
    if q in _ALIAS_LOOKUP:
        ticker = _ALIAS_LOOKUP[q]
        return ticker, NSE_TICKERS.get(ticker, ticker)
    # 3. Company name reverse lookup — exact then partial
    for sym, name in NSE_TICKERS.items():
        if name.upper() == q:
            return sym, name
    for sym, name in NSE_TICKERS.items():
        if q in name.upper():
            return sym, name
    # 4. Ticker prefix match
    for sym, name in NSE_TICKERS.items():
        if sym.startswith(q):
            return sym, name
    # 5. Online fallback — Yahoo Finance search
    online_result = _search_ticker_online(raw_input.strip())
    if online_result and online_result[0]:
        ticker, name = online_result
        if ticker in NSE_TICKERS:
            return ticker, NSE_TICKERS[ticker]
        return ticker, name
    return None, None


def get_company_name(ticker: str) -> str:
    """Return the canonical company name for a ticker.

    Resolution: offline map → live Yahoo lookup → raw ticker.
    Never returns an empty string.
    """
    NSE_TICKERS = _get_tickers()  # noqa: N806
    clean = ticker.replace(".NS", "").strip().upper()
    if clean in NSE_TICKERS:
        return NSE_TICKERS[clean]
    # Live fallback
    result = _search_ticker_online(clean)
    if result and result[0]:
        return result[1] or clean
    return clean


def build_ticker_options() -> list[str]:
    """Build sorted 'TICKER — Company Name' options for autocomplete UI."""
    NSE_TICKERS = _get_tickers()  # noqa: N806
    return sorted(f"{t} — {n}" for t, n in NSE_TICKERS.items())


def parse_ticker_option(option: str) -> str:
    """Extract the raw ticker from a 'TICKER — Name' autocomplete option."""
    return option.split(" — ")[0].strip()
