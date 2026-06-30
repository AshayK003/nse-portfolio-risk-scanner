"""
Portfolio parsing, validation, and normalization.

This module is the entry point for user data. It handles:
- CSV parsing (Zerodha/Groww/Upstox/kite export format)
- Validation (duplicate tickers, negative quantities)
- Normalization (ticker casing, whitespace, .NS suffix)
"""

from __future__ import annotations

import csv
import io
import re

from . import Holding, Portfolio

# Common NSE ticker suffixes to strip
_TICKER_CLEANUP = re.compile(r"[\.\-–—\s]+(NS|NSE|BSE|EQ|LTD)$", re.IGNORECASE)

# Max holdings to prevent resource exhaustion
_MAX_HOLDINGS = 200

# Known ticker corrections for common user input mistakes
_TICKER_ALIASES = {
    "NIFTY": "^NSEI",
    "NIFTY50": "^NSEI",
    "SENSEX": "^BSESN",
}


_MAX_CSV_BYTES = 10 * 1024 * 1024  # 10 MB


def parse_portfolio_csv(
    csv_bytes: bytes,
    portfolio_name: str = "My Portfolio",
) -> Portfolio:
    """
    Parse a CSV portfolio file into a Portfolio dataclass.

    Accepted column headers (case-insensitive):
      - ticker, symbol, stock, name
      - quantity, shares, qty
      - price, avg_price, buy_price, average_price

    Returns a validated Portfolio or raises ValueError.
    """
    if len(csv_bytes) > _MAX_CSV_BYTES:
        raise ValueError(f"CSV file exceeds maximum size of {_MAX_CSV_BYTES // (1024*1024)}MB")
    content = csv_bytes.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(content))

    if not reader.fieldnames:
        raise ValueError("CSV file is empty or has no header row")

    # Map column names (case-insensitive, flexible matching)
    col_map, matched_alias = _build_column_map(reader.fieldnames)

    holdings: list[Holding] = []
    errors: list[str] = []
    seen_tickers: set[str] = set()

    # Detect if the "price" column is ambiguous (could be total cost, not per-share)
    price_col = col_map.get("price", "")
    price_col_lower = price_col.lower().strip() if price_col else ""
    _AMBIGUOUS_PRICE_TERMS = ["cost", "total"]
    is_ambiguous_price_col = any(w in price_col_lower for w in _AMBIGUOUS_PRICE_TERMS)

    for row_idx, row in enumerate(reader, start=2):  # 1-indexed, skip header
        try:
            ticker_raw = row.get(col_map.get("ticker", ""), "").strip()
            if not ticker_raw:
                continue  # skip empty rows

            ticker = normalize_ticker(ticker_raw)

            qty_str = row.get(col_map.get("quantity", ""), "0").strip()
            qty = _parse_float(qty_str)
            if qty <= 0:
                errors.append(f"Row {row_idx}: invalid quantity '{qty_str}'")
                continue

            price_str = row.get(col_map.get("price", ""), "0").strip()
            price = _parse_float(price_str)
            if price <= 0:
                errors.append(f"Row {row_idx}: invalid avg price '{price_str}'")
                continue

            # Auto-correct: if the price column is ambiguous ("cost", "total")
            # and avg_price looks like a total value (not per-share), divide by qty.
            # Heuristic: if price > 10K (too high for a typical per-share price when qty>1)
            # and price/qty gives a reasonable per-share price (< 10K), it's a total column.
            if is_ambiguous_price_col and qty > 1 and price > 10000:
                per_share = price / qty
                if per_share < 10000:  # reasonable per-share price for most NSE stocks
                    price = per_share

            name = row.get(col_map.get("name", ""), ticker).strip()

            if ticker in seen_tickers:
                errors.append(f"Row {row_idx}: duplicate ticker '{ticker}'")
                continue
            seen_tickers.add(ticker)

            holdings.append(
                Holding(
                    ticker=ticker,
                    name=name,
                    quantity=int(qty),
                    avg_price=round(price, 2),
                )
            )
        except (ValueError, KeyError) as e:
            errors.append(f"Row {row_idx}: {e}")

    if len(holdings) > _MAX_HOLDINGS:
        raise ValueError(f"Portfolio exceeds max holdings ({_MAX_HOLDINGS}). Found {len(holdings)} rows.")

    if not holdings:
        msg = "No valid holdings found in CSV."
        if errors:
            msg += " Errors:\n" + "\n".join(errors[:5])
        raise ValueError(msg)

    return Portfolio(holdings=holdings, name=portfolio_name)


def normalize_ticker(raw: str) -> str:
    """Clean and normalize a ticker symbol for yfinance."""
    ticker = raw.strip().upper()

    # Check aliases
    if ticker in _TICKER_ALIASES:
        return _TICKER_ALIASES[ticker]

    # Strip common suffixes: RELIANCE.NS -> RELIANCE
    ticker = _TICKER_CLEANUP.sub("", ticker).strip()

    # For NSE stocks, yfinance needs the .NS suffix
    # Skip suffixes for indices
    if not ticker.startswith("^"):
        ticker = f"{ticker}.NS"

    return ticker


def validate_portfolio(portfolio: Portfolio) -> list[str]:
    """Validate a portfolio and return list of warnings."""
    warnings: list[str] = []

    if portfolio.holding_count == 0:
        warnings.append("Portfolio is empty")

    if portfolio.holding_count > 50:
        warnings.append(
            f"Portfolio has {portfolio.holding_count} holdings — yfinance rate limits may slow data fetching"
        )

    # Check for extreme concentration
    weights = portfolio.weight
    if weights:
        max_weight = max(weights)
        if max_weight > 0.5:
            idx = weights.index(max_weight)
            warnings.append(
                f"'{portfolio.holdings[idx].ticker}' is {max_weight * 100:.0f}% "
                f"of portfolio — high concentration risk"
            )

    return warnings


# Common currency suffixes to strip from column names before matching
_CURRENCY_SUFFIXES = ["(₹)", "(rs)", "(inr)", "($)", "(rs.)"]


def _clean_col_name(name: str) -> str:
    """Strip common currency suffixes for alias matching."""
    name = name.lower().strip()
    for suffix in _CURRENCY_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
            break
    return name


def _build_column_map(fieldnames: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Build a case-insensitive column name mapping.

    Matches in order: exact match (lowercase+stripped) first,
    then currency-suffix-stripped match, then positional fallback.

    Returns (col_map, matched_alias) where matched_alias records which
    alias was used for each key (for downstream disambiguation).
    """
    candidates = {
        "ticker": ["ticker", "symbol", "stock", "scrip", "isin"],
        "quantity": ["quantity", "qty", "shares", "holdings"],
        "price": [
            "avg_price",
            "avg price",
            "average price",
            "average cost",
            "avg cost",
            "buy_price",
            "buy price",
            "atp",
            "price",
            "cost",
        ],
        "name": ["name", "company", "company name", "security"],
    }

    col_map: dict[str, str] = {}
    matched_alias: dict[str, str] = {}
    normalized_fields = {f.lower().strip(): f for f in fieldnames}
    clean_fields = {_clean_col_name(f): f for f in fieldnames}

    for key, aliases in candidates.items():
        for alias in aliases:
            if alias in normalized_fields:
                col_map[key] = normalized_fields[alias]
                matched_alias[key] = alias
                break
            if alias in clean_fields:
                col_map[key] = clean_fields[alias]
                matched_alias[key] = alias
                break

    required = ["ticker", "quantity", "price"]
    missing = [r for r in required if r not in col_map]
    if missing:
        if len(fieldnames) >= 3:
            col_map["ticker"] = fieldnames[0]
            col_map["quantity"] = fieldnames[1]
            col_map["price"] = fieldnames[2]
        else:
            raise ValueError(
                f"Could not find columns: {missing}. "
                f"Expected columns like: ticker, quantity, avg_price. "
                f"Got: {fieldnames}"
            )

    return col_map, matched_alias


def _parse_float(s: str) -> float:
    """Parse a float from a string, handling Indian number format."""
    s = s.strip()
    if not s:
        return 0.0
    # Handle Indian format: 1,23,456.78 -> 123456.78
    # First check if comma is thousands separator or decimal
    s = s.replace(",", "")
    s = s.replace("₹", "").replace("Rs.", "").strip()
    return float(s)


def portfolio_from_dict(data: dict) -> Portfolio:
    """Create a Portfolio from a dict (useful for testing / API)."""
    holdings = [
        Holding(
            ticker=normalize_ticker(h.get("ticker", "")),
            name=h.get("name", h.get("ticker", "")),
            quantity=int(h.get("quantity", 0)),
            avg_price=float(h.get("avg_price", 0)),
        )
        for h in data.get("holdings", [])
    ]
    return Portfolio(
        holdings=holdings,
        name=data.get("name", "My Portfolio"),
    )
