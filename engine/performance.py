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
