"""
Performance metric computation.
Pure functions for Sharpe, Sortino, CAGR, and return analysis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import Holding


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


def compute_cagr(portfolio_returns: pd.Series) -> float:
    """Compound Annual Growth Rate as a percentage."""
    cum = (1 + portfolio_returns).cumprod()
    total_return = cum.iloc[-1] - 1 if len(cum) > 0 else 0
    years = len(portfolio_returns) / 252
    if years <= 0:
        return 0.0
    return ((1 + total_return) ** (1 / years) - 1) * 100


def compute_total_return(portfolio_returns: pd.Series) -> dict:
    """Total return over various periods as percentage."""
    cum = (1 + portfolio_returns).cumprod()
    latest = cum.iloc[-1] - 1 if len(cum) > 0 else 0

    returns = {"total": round((latest) * 100, 2)}

    # Period-based returns
    if len(portfolio_returns) >= 21:
        month_ago = cum.iloc[-22] if len(cum) > 22 else cum.iloc[0]
        returns["1m"] = round((cum.iloc[-1] / month_ago - 1) * 100, 2)
    if len(portfolio_returns) >= 63:
        three_months_ago = cum.iloc[-64] if len(cum) > 64 else cum.iloc[0]
        returns["3m"] = round((cum.iloc[-1] / three_months_ago - 1) * 100, 2)
    if len(portfolio_returns) >= 126:
        six_months_ago = cum.iloc[-127] if len(cum) > 127 else cum.iloc[0]
        returns["6m"] = round((cum.iloc[-1] / six_months_ago - 1) * 100, 2)
    if len(portfolio_returns) >= 252:
        year_ago = cum.iloc[-253] if len(cum) > 253 else cum.iloc[0]
        returns["1y"] = round((cum.iloc[-1] / year_ago - 1) * 100, 2)

    return returns


def compute_sharpe_ratio(
    portfolio_returns: pd.Series,
    risk_free_rate: float = 0.065,
) -> float:
    """Annualized Sharpe ratio."""
    daily_rf = risk_free_rate / 252
    excess = portfolio_returns - daily_rf
    daily_vol = portfolio_returns.std()
    if daily_vol <= 0:
        return 0.0
    return round(np.sqrt(252) * excess.mean() / daily_vol, 2)


def compute_sortino_ratio(
    portfolio_returns: pd.Series,
    risk_free_rate: float = 0.065,
) -> float:
    """Annualized Sortino ratio (uses downside deviation)."""
    daily_rf = risk_free_rate / 252
    excess_mean = portfolio_returns.mean() - daily_rf
    downside = np.minimum(0, portfolio_returns - daily_rf)
    downside_vol = np.sqrt(np.mean(downside**2)) * np.sqrt(252) if len(downside) > 0 else 1e-10
    return round((excess_mean * 252) / downside_vol, 2)


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
        start = cum[:end][cum[:end] == cum[:end].max()].index[0]
    else:
        start = cum.index[0]
        end = cum.index[-1]

    return {
        "max_drawdown": round(max_dd, 2),
        "start": str(start.date()) if hasattr(start, "date") else str(start),
        "end": str(end.date()) if hasattr(end, "date") else str(end),
    }


def compute_win_rate(portfolio_returns: pd.Series) -> dict:
    """Percentage of positive, negative, and zero daily returns."""
    positive = (portfolio_returns > 0).sum()
    negative = (portfolio_returns < 0).sum()
    zero = (portfolio_returns == 0).sum()
    total = positive + negative + zero
    if total == 0:
        return {"win_rate": 0, "loss_rate": 0, "total_days": 0}
    return {
        "win_rate": round(positive / total * 100, 1),
        "loss_rate": round(negative / total * 100, 1),
        "total_days": total,
    }


def compute_holding_returns(holdings: list[Holding]) -> pd.DataFrame:
    """Create a DataFrame with individual holding P&L for display."""
    rows = []
    for h in holdings:
        rows.append(
            {
                "ticker": h.ticker.replace(".NS", ""),
                "name": h.name,
                "sector": h.sector,
                "quantity": h.quantity,
                "avg_price": h.avg_price,
                "current_price": round(h.current_price, 2),
                "invested": round(h.invested_value, 2),
                "current_value": round(h.current_value, 2),
                "pnl": round(h.pnl, 2),
                "pnl_pct": round(h.pnl_pct, 2),
                "weight_pct": 0.0,  # filled after normalization
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if df["current_value"].sum() > 0:
        df["weight_pct"] = round(df["current_value"] / df["current_value"].sum() * 100, 1)
    return df.sort_values("pnl_pct", ascending=False).reset_index(drop=True)
