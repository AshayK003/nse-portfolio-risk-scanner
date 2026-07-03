"""Performance metric computation.
Pure functions for return analysis and max drawdown.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_portfolio_returns(
    prices: pd.DataFrame,
    weights: list[float],
) -> pd.Series:
    """Compute daily weighted portfolio returns from price history."""
    returns = prices.pct_change().dropna()
    weights_arr = np.array(weights)
    if abs(weights_arr.sum() - 1.0) > 0.01:
        weights_arr = weights_arr / weights_arr.sum()
    return returns.dot(weights_arr)


def compute_max_drawdown(prices: pd.Series | pd.DataFrame) -> dict:
    """
    Compute maximum drawdown and its period.

    Args:
        prices: Single stock price series or portfolio cumulative returns

    Returns:
        dict with max_drawdown (%), start, end
    """
    cum = prices.iloc[:, 0] if isinstance(prices, pd.DataFrame) else prices

    if cum.empty:
        return {"max_drawdown": 0.0, "start": "N/A", "end": "N/A"}

    running_max = cum.cummax()
    drawdown = (cum - running_max) / running_max * 100
    max_dd = drawdown.min()

    dd_series = drawdown[drawdown == max_dd]
    if not dd_series.empty:
        end = dd_series.index[0]
        peak = cum[:end]
        start = peak[peak == peak.max()].index[0] if not peak.empty else cum.index[0]
    else:
        start = cum.index[0]
        end = cum.index[-1]

    return {
        "max_drawdown": round(max_dd, 2),
        "start": str(start.date()) if hasattr(start, "date") else str(start),
        "end": str(end.date()) if hasattr(end, "date") else str(end),
    }



