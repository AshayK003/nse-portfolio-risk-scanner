"""
Altman Z-Score bankruptcy prediction.
Pure functions computing credit/fundamental risk from balance sheet data.
No new dependencies — uses yfinance (already installed).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ZScoreResult:
    """Altman Z-Score analysis for a single ticker."""

    ticker: str
    company_name: str
    zscore: float
    zone: str  # "Safe", "Grey Zone", "Distress"
    model: str  # "Original" (manufacturing) or "Modified" (non-manufacturing)


# Zone thresholds from Altman (1968 / 2000)
_ORIGINAL_THRESHOLDS = (1.8, 3.0)
_MODIFIED_THRESHOLDS = (1.1, 2.6)


def _classify_zone(zscore: float, model: str) -> str:
    lo, hi = _ORIGINAL_THRESHOLDS if model == "Original" else _MODIFIED_THRESHOLDS
    if zscore >= hi:
        return "Safe"
    if zscore >= lo:
        return "Grey Zone"
    return "Distress"


def compute_zscore(ticker: str) -> ZScoreResult | None:
    """Fetch financials and compute Altman Z-Score for a ticker.

    Returns None if financial data is unavailable (e.g., ticker delisted,
    not found on yfinance, or has no balance sheet data).

    Uses the Original Z-Score formula for manufacturers and Modified
    for non-manufacturers / emerging markets.
    """
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        bs = stock.balance_sheet
        if bs is None or bs.empty:
            return None

        # Most recent annual data
        bs = bs.loc[:, bs.columns[0]]
    except Exception:
        return None

    total_assets = _get(bs, "Total Assets")
    if total_assets is None or total_assets == 0:
        return None

    current_assets = _get(bs, "Total Current Assets") or _get(bs, "Current Assets")
    current_liab = _get(bs, "Total Current Liabilities") or _get(bs, "Current Liabilities")
    total_liab = _get(bs, "Total Liabilities Net Minority Interest") or _get(bs, "Total Liabilities")
    retained_earnings = _get(bs, "Retained Earnings") or _get(bs, "Retained Earnings Total")
    ebit = _get(bs, "EBIT") or _get(bs, "Operating Income")
    sales = _get(bs, "Total Revenue") or _get(bs, "Revenue")
    market_cap = info.get("marketCap") or info.get("market_cap", 0)

    if any(v is None for v in [current_assets, current_liab, total_liab,
                                retained_earnings, sales]):
        return None

    company_name = info.get("longName") or info.get("shortName") or ticker

    working_capital = current_assets - current_liab

    # Detect manufacturing vs non-manufacturing via sector
    sector = (info.get("sector") or "").lower()
    is_mfg = any(kw in sector for kw in ["industrials", "technology", "energy",
                                          "materials", "consumer cyclical"])
    model = "Original" if is_mfg else "Modified"

    X1 = working_capital / total_assets  # noqa: N806
    X2 = retained_earnings / total_assets  # noqa: N806
    X3 = (ebit or 0) / total_assets  # noqa: N806
    X4 = market_cap / total_liab if total_liab != 0 else 0  # noqa: N806
    X5 = sales / total_assets  # noqa: N806

    if model == "Original":
        z = 1.2 * X1 + 1.4 * X2 + 3.3 * X3 + 0.6 * X4 + 1.0 * X5
    else:
        z = 6.56 * X1 + 3.26 * X2 + 6.72 * X3 + 1.05 * X4

    zone = _classify_zone(z, model)
    return ZScoreResult(ticker=ticker, company_name=company_name,
                        zscore=round(z, 2), zone=zone, model=model)


def compute_all_zscores(tickers: list[str]) -> list[ZScoreResult]:
    """Compute Z-Scores for a list of tickers. Skips failures silently."""
    results = []
    for t in tickers:
        r = compute_zscore(t)
        if r is not None:
            results.append(r)
    return results


def _get(bs_row, key: str) -> float | None:
    """Safely extract a value from a balance sheet row."""
    val = bs_row.get(key)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return float(val)
