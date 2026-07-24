"""
NSE delivery analysis — tracks delivery volume patterns.

Uses nselib's bhavcopy data to compute delivery percentage and trend.
Optional dependency: nselib (pip install nse-risk-scanner[nse]).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

try:
    from nselib import capital_market

    _NSELIB_AVAILABLE = True
except ImportError:
    _NSELIB_AVAILABLE = False


@dataclass
class DeliveryInfo:
    ticker: str
    delivery_pct: float
    delivery_trend: str  # "rising", "falling", "stable"
    avg_delivery: float


def _fetch_bhavcopy_single(ticker: str, period: str = "1M") -> pd.DataFrame | None:
    """Fetch delivery data from nselib bhavcopy for a single ticker."""
    if not _NSELIB_AVAILABLE:
        return None
    try:
        raw = capital_market.bhav_copy_with_delivery(period=period)
        if raw is None or raw.empty:
            return None
        if "SYMBOL" not in raw.columns:
            return None
        ticker_data = raw[raw["SYMBOL"] == ticker.replace(".NS", "")].copy()
        if ticker_data.empty:
            return None
        ticker_data["DATE"] = pd.to_datetime(ticker_data["DATE"])
        ticker_data = ticker_data.sort_values("DATE")
        return ticker_data
    except Exception:
        return None


def _compute_delivery(delivery_data: pd.DataFrame) -> DeliveryInfo | None:
    """Compute delivery metrics from bhavcopy data."""
    required = ["DELIV_QTY", "TOTTRDQTY"]
    if not all(c in delivery_data.columns for c in required):
        return None

    # Need at least 2 data points for meaningful delivery analysis
    if len(delivery_data) < 2:
        return None

    total_qty = delivery_data["TOTTRDQTY"].sum()
    if total_qty == 0:
        return None

    del_qty = delivery_data["DELIV_QTY"].sum()
    delivery_pct = round(del_qty / total_qty * 100, 1)

    # Trend analysis: last 10 days vs prior period
    if len(delivery_data) >= 15:
        recent = delivery_data.tail(10)
        earlier = delivery_data.tail(20).head(10)
        recent_avg = (
            recent["DELIV_QTY"].sum() / recent["TOTTRDQTY"].sum() * 100
            if recent["TOTTRDQTY"].sum() > 0
            else 0
        )
        earlier_avg = (
            earlier["DELIV_QTY"].sum() / earlier["TOTTRDQTY"].sum() * 100
            if earlier["TOTTRDQTY"].sum() > 0
            else 0
        )
        diff = recent_avg - earlier_avg
        trend = "rising" if diff > 3 else ("falling" if diff < -3 else "stable")
    else:
        trend = "stable"

    return DeliveryInfo(
        ticker=delivery_data["SYMBOL"].iloc[0],
        delivery_pct=delivery_pct,
        delivery_trend=trend,
        avg_delivery=delivery_pct,
    )


def fetch_delivery_for_holdings(tickers: list[str], period: str = "1M") -> dict[str, DeliveryInfo]:
    """
    Fetch delivery data for a list of tickers.

    Returns dict of {ticker: DeliveryInfo}. Only tickers with
    available bhavcopy data are included.
    """
    if not _NSELIB_AVAILABLE:
        return {}

    results: dict[str, DeliveryInfo] = {}
    for ticker in tickers:
        try:
            data = _fetch_bhavcopy_single(ticker, period)
            if data is not None:
                info = _compute_delivery(data)
                if info is not None:
                    results[ticker] = info
        except Exception:
            continue
    return results
