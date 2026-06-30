"""
Portfolio parsing, validation, and normalization.

This module is the entry point for user data. It handles:
- CSV parsing (Zerodha/Groww/Angel/Upstox/ICICI/Kotak/HDFC export format)
- Smart column detection (name aliases + value-based heuristics)
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

# Currency suffixes to strip from column names before matching
_CURRENCY_SUFFIXES = ["(₹)", "(rs)", "(inr)", "($)", "(rs.)"]

# Comprehensive column aliases for every known Indian broker format.
# Order matters: more specific/variants listed first within each role.
_COLUMN_ALIASES = {
    "ticker": [
        "ticker", "symbol", "stock", "scrip", "isin",
        "tradingsymbol", "trading symbol", "instrument",
        "security", "code",
    ],
    "quantity": [
        "quantity", "qty", "qty.", "shares", "holdings",
        "units", "netqty", "net qty", "nos", "pos", "size",
    ],
    "avg_price": [
        "avg_price",
        "avg price",
        "average price",
        "avg cost",
        "average cost",
        "avg. cost",
        "avg.cost",
        "buy_price",
        "buy price",
        "buyprice",
        "buying price",
        "purchase price",
        "entry price",
        "unit cost",
        "cost per share",
        "atp",
        "average traded price",
    ],
    "current_price": [
        "ltp",
        "last price",
        "last_price",
        "last traded price",
        "mkt price",
        "market price",
        "current price",
        "current_price",
        "cmp",
        "close",
        "closing price",
        "price",
    ],
    "total_cost": [
        "total cost",
        "total_cost",
        "cost value",
        "cost_value",
        "invested amount",
        "invested amt",
        "invested value",
        "invested_value",
        "investment",
        "total investment",
        "total invested",
        "invested",
        "cost",
    ],
    "total_value": [
        "total value",
        "total_value",
        "current value",
        "current_value",
        "market value",
        "market_value",
        "portfolio value",
        "value",
        "total amount",
        "amount",
        "total",
    ],
    "pnl": [
        "pnl", "p&l", "profit & loss", "profit and loss",
        "profit/loss", "unrealized pnl", "unrealised pnl",
        "day pnl", "total pnl", "mtm",
    ],
    "name": [
        "name", "company", "company name", "security name",
        "securityname", "description",
    ],
}

# Column roles that represent price-per-share
_PRICE_ROLES = {"avg_price", "current_price"}

# Column roles that represent total-value (not per-share)
_TOTAL_ROLES = {"total_cost", "total_value", "pnl"}


def parse_portfolio_csv(
    csv_bytes: bytes,
    portfolio_name: str = "My Portfolio",
) -> Portfolio:
    """
    Parse a CSV portfolio file into a Portfolio dataclass.

    Handles:
      - Comma, semicolon, pipe, and tab delimiters
      - BOM encoding (Windows Excel exports)
      - Indian number format (1,23,456.78)
      - 10+ broker export formats (Zerodha, Groww, Angel, Upstox, ICICI, etc.)
      - Auto-correction of total-cost columns mistaken for per-share price

    Returns a validated Portfolio or raises ValueError.
    """
    if len(csv_bytes) > _MAX_CSV_BYTES:
        raise ValueError(f"CSV file exceeds maximum size of {_MAX_CSV_BYTES // (1024*1024)}MB")

    content = csv_bytes.decode("utf-8-sig")
    delim = _detect_delimiter(content)
    reader = csv.DictReader(io.StringIO(content), delimiter=delim)

    if not reader.fieldnames:
        raise ValueError("CSV file is empty or has no header row")

    # Phase 1: Preprocessing — sample rows + analyze columns
    samples = _sample_rows(reader, _CSV_SAMPLE_SIZE)
    col_map, pre_warnings = _resolve_column_map(reader.fieldnames, samples)
    price_role = col_map.pop("_price_role", "fallback")

    # Phase 2: Full parse with a fresh reader
    reader = csv.DictReader(io.StringIO(content), delimiter=delim)

    holdings: list[Holding] = []
    errors: list[str] = []
    seen_tickers: set[str] = set()

    for row_idx, row in enumerate(reader, start=2):
        try:
            ticker_raw = row.get(col_map["ticker"], "").strip()
            if not ticker_raw:
                continue

            ticker = normalize_ticker(ticker_raw)

            qty_str = row.get(col_map["quantity"], "0").strip()
            qty = _parse_float(qty_str)
            if qty <= 0:
                errors.append(f"Row {row_idx}: invalid quantity '{qty_str}'")
                continue

            price_str = row.get(col_map["price"], "0").strip()
            price = _parse_float(price_str)
            if price <= 0:
                errors.append(f"Row {row_idx}: invalid avg price '{price_str}'")
                continue

            # Auto-correct: when the price column is a total-cost/value column,
            # divide by quantity to recover per-share price.
            if price_role in ("total_cost", "total_value") and qty > 1 and price > 10000:
                per_share = price / qty
                if per_share < 10000:
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
        return warnings

    if portfolio.holding_count > 50:
        warnings.append(
            f"Portfolio has {portfolio.holding_count} holdings — "
            f"yfinance rate limits may slow data fetching"
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

    # Sanity: detect if avg_price might still be a total cost (per-share > 1L)
    for h in portfolio.holdings:
        if h.avg_price > 100_000 and h.quantity > 1:
            per_share = h.avg_price / h.quantity
            if per_share < h.avg_price * 0.01 and per_share < 100_000:
                warnings.append(
                    f"'{h.ticker}' has avg_price Rs {h.avg_price:,.0f} with qty {h.quantity} — "
                    f"this looks like total cost. Expected per-share price ≈ Rs {per_share:,.0f}."
                )

    return warnings


_CSV_SAMPLE_SIZE = 5


def _detect_delimiter(content: str) -> str:
    """Auto-detect CSV delimiter by scoring each candidate on first 5 lines."""
    lines = [l for l in content.split("\n")[:5] if l.strip()]
    if not lines:
        return ","
    candidates = {",": 0, ";": 0, "|": 0, "\t": 0}
    for delim in candidates:
        scores = [l.count(delim) for l in lines]
        if scores and sum(scores) > 0:
            consistent = 1.0 if max(scores) == min(scores) and scores[0] > 0 else 0.5
            candidates[delim] = sum(scores) * consistent
    return max(candidates, key=candidates.get)


def _clean_col_name(name: str) -> str:
    """Strip common currency suffixes for alias matching."""
    name = name.lower().strip()
    for suffix in _CURRENCY_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
            break
    return name


def _sample_rows(
    reader: csv.DictReader, n: int = _CSV_SAMPLE_SIZE,
) -> list[dict[str, str]]:
    """Consume up to n rows from a reader for value analysis."""
    return [row for _, row in zip(range(n), reader)]


def _analyze_values(
    fieldnames: list[str], samples: list[dict[str, str]],
) -> dict[str, dict]:
    """Classify each column by its sampled numeric values."""
    analysis: dict[str, dict] = {}
    for f in fieldnames:
        nums = []
        for row in samples:
            raw = row.get(f, "").strip()
            if raw:
                try:
                    nums.append(_parse_float(raw))
                except (ValueError, TypeError):
                    pass
        if not nums:
            continue
        min_v, max_v = min(nums), max(nums)
        avg_v = sum(nums) / len(nums)
        all_pos = all(v > 0 for v in nums)
        has_neg = any(v < 0 for v in nums)
        magnitude = max(abs(min_v), abs(max_v))
        analysis[f] = {
            "avg": avg_v,
            "min": min_v,
            "max": max_v,
            "magnitude": magnitude,
            "all_positive": all_pos,
            "has_negative": has_neg,
            "sample_count": len(nums),
        }
    return analysis


def _match_by_name(
    fieldnames: list[str],
) -> dict[str, str]:
    """Match columns to roles using alias vocabulary (name-based only)."""
    normalized = {f.lower().strip(): f for f in fieldnames}
    clean = {_clean_col_name(f): f for f in fieldnames}
    matched: dict[str, str] = {}
    for role, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                matched[role] = normalized[alias]
                break
            if alias in clean:
                matched[role] = clean[alias]
                break
    return matched


def _resolve_column_map(
    fieldnames: list[str],
    samples: list[dict[str, str]],
) -> tuple[dict[str, str], list[str]]:
    """Smart column resolution: name matching + value-based disambiguation.

    Returns (col_map, warnings) where col_map has keys
    'ticker', 'quantity', 'price', and optionally 'name'.
    """
    warnings: list[str] = []
    name_match = _match_by_name(fieldnames)
    value_analysis = _analyze_values(fieldnames, samples)

    # --- Ticker ---
    ticker_col = name_match.get("ticker")

    # --- Quantity ---
    qty_col = name_match.get("quantity")

    # --- Price (avg buy price) ---
    avg_col = name_match.get("avg_price")
    cur_col = name_match.get("current_price")
    cost_col = name_match.get("total_cost")
    val_col = name_match.get("total_value")

    # Strategy: pick the best column for avg_price using priority + heuristics.
    # Priority 1: unambiguous avg_price alias exists -> use it directly.
    # Priority 2: only current_price exists -> use it (it's a reasonable approx).
    # Priority 3: only total_cost exists -> use value heuristic to decide
    #             if it's total (per-share) or per-share (total).
    # Priority 4: positional fallback.

    price_col: str | None = None

    if avg_col:
        price_col = avg_col
    elif cur_col:
        price_col = cur_col
        # Only warn if we also have a more-specific avg_price candidate column
        # (like "cost") that we chose NOT to use because it looks like total.
    elif cost_col:
        # "Cost" is ambiguous. Use value analysis to decide.
        if value_analysis.get(cost_col, {}).get("magnitude", 0) > 50000:
            val_avg = value_analysis[cost_col]["avg"]
            if qty_col and qty_col in value_analysis:
                qty_avg = value_analysis[qty_col]["avg"]
                if qty_avg > 1 and val_avg / qty_avg < 10000:
                    # Cost is total, not per-share. Use it but divide later.
                    price_col = cost_col
                    warnings.append(
                        f"Column '{cost_col}' appears to hold total cost (not per-share). "
                        f"Values will be divided by quantity."
                    )
                else:
                    # Cost might be per-share price (e.g., MRF at 120K)
                    price_col = cost_col
            else:
                price_col = cost_col
        else:
            price_col = cost_col
    elif val_col:
        price_col = val_col

    # --- Name ---
    name_col = name_match.get("name")

    # --- Fallback: first 3 columns ---
    missing = []
    if not ticker_col:
        missing.append("ticker")
    if not qty_col:
        missing.append("quantity")
    if not price_col:
        missing.append("price")

    if missing:
        if len(fieldnames) >= 3:
            ticker_col = ticker_col or fieldnames[0]
            qty_col = qty_col or fieldnames[1]
            price_col = price_col or fieldnames[2]
        else:
            raise ValueError(
                f"Could not find columns: {missing}. "
                f"Expected columns like: ticker, quantity, price. "
                f"Got: {fieldnames}"
            )

    col_map: dict[str, str] = {
        "ticker": ticker_col,
        "quantity": qty_col,
        "price": price_col,
    }
    if name_col:
        col_map["name"] = name_col

    # --- Column origin info for downstream auto-correct ---
    col_map["_price_role"] = (
        "total_cost" if cost_col == price_col else
        "total_value" if val_col == price_col else
        "avg_price" if avg_col == price_col else
        "current_price" if cur_col == price_col else
        "fallback"
    )

    return col_map, warnings


def _build_column_map(fieldnames: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Legacy alias: kept for backward compatibility.

    Returns (col_map, matched_alias) — matched_alias is now a stub
    since resolution is handled by _resolve_column_map.
    """
    col_map, _ = _resolve_column_map(fieldnames, [])
    # Stub matched_alias for backward compat (callers don't use it)
    return col_map, {}


def _parse_float(s: str) -> float:
    """Parse a float from a string, handling Indian number format and common symbols."""
    s = s.strip().lstrip("+")
    if not s:
        return 0.0
    # Handle Indian format: 1,23,456.78 -> 123456.78
    s = s.replace(",", "")
    # Strip currency symbols, percentage signs, and whitespace
    for sym in ("₹", "Rs.", "Rs", "%", "`", "'", '"'):
        s = s.replace(sym, "")
    s = s.strip()
    return float(s) if s else 0.0


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
