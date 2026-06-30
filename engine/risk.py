"""
Risk metric computation.
All functions are PURE — they accept DataFrames/arrays and return dicts/dataclasses.
Zero side effects, zero IO, zero Streamlit imports.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import RiskMetrics


def compute_risk_metrics(
    prices: pd.DataFrame,
    weights: list[float],
    risk_free_rate: float = 0.065,
    benchmark_returns: pd.Series | None = None,
) -> RiskMetrics:
    """
    Compute all risk metrics for a portfolio.

    Args:
        prices: Daily closing prices DataFrame (columns = tickers, index = Date)
        weights: Portfolio weights (same order as price columns, must sum to ~1)
        risk_free_rate: Indian risk-free rate (default 6.5% for 10-year bond)
        benchmark_returns: Nifty 50 daily returns for beta computation

    Returns:
        RiskMetrics dataclass with all computed values
    """
    if prices.empty or len(weights) == 0:
        return _empty_risk_metrics()

    # Daily returns
    returns = prices.pct_change().dropna()
    if returns.empty:
        return _empty_risk_metrics()

    # Portfolio weighted returns
    weights_arr = np.array(weights)
    if abs(weights_arr.sum() - 1.0) > 0.01:
        weights_arr = weights_arr / weights_arr.sum()  # normalize

    portfolio_returns = returns.dot(weights_arr)

    # --- Volatility ---
    daily_vol = portfolio_returns.std()
    annual_vol = daily_vol * np.sqrt(252)

    # --- Value at Risk ---
    var_95 = np.percentile(portfolio_returns, 5) * 100
    var_99 = np.percentile(portfolio_returns, 1) * 100

    # --- Conditional VaR (Expected Shortfall) ---
    cvar_95 = portfolio_returns[portfolio_returns <= np.percentile(portfolio_returns, 5)].mean() * 100

    # --- Max Drawdown ---
    cum_returns = (1 + portfolio_returns).cumprod()
    running_max = cum_returns.cummax()
    drawdown = (cum_returns - running_max) / running_max
    max_dd = drawdown.min() * 100

    # Drawdown period
    dd_series = drawdown[drawdown == drawdown.min()]
    if not dd_series.empty:
        dd_end = dd_series.index[0]
        # Walk back to find start
        dd_start_idx = cum_returns[:dd_end][cum_returns[:dd_end] == cum_returns[:dd_end].max()].index
        dd_start = dd_start_idx[0] if len(dd_start_idx) > 0 else dd_end
    else:
        dd_start = prices.index[0]
        dd_end = prices.index[-1]

    # --- Sharpe Ratio ---
    daily_rf = risk_free_rate / 252
    excess_returns = portfolio_returns - daily_rf
    sharpe = np.sqrt(252) * excess_returns.mean() / daily_vol if daily_vol > 0 else 0.0

    # --- Sortino Ratio ---
    downside = portfolio_returns[portfolio_returns < 0]
    downside_vol = downside.std() * np.sqrt(252) if len(downside) > 0 else 1e-10
    annual_excess = (portfolio_returns.mean() - daily_rf) * 252
    sortino = annual_excess / downside_vol if downside_vol > 0 else 0.0

    # --- CAGR ---
    total_days = len(portfolio_returns)
    total_years = total_days / 252
    total_return_val = cum_returns.iloc[-1] - 1 if len(cum_returns) > 0 else 0
    cagr = ((1 + total_return_val) ** (1 / total_years) - 1) * 100 if total_years > 0 else 0.0

    # --- Beta & Correlation ---
    beta = 1.0
    corr = 0.0
    if benchmark_returns is not None and len(benchmark_returns) > 0:
        aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1, join="inner").dropna()
        if len(aligned) > 5:
            cov = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])
            var = aligned.iloc[:, 1].var()
            beta = cov / var if var > 0 else 1.0
            corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])

    return RiskMetrics(
        volatility_annual=round(annual_vol * 100, 2),
        var_95=round(var_95, 2),
        var_99=round(var_99, 2),
        cvar_95=round(cvar_95, 2),
        max_drawdown=round(max_dd, 2),
        max_drawdown_start=str(dd_start.date()) if hasattr(dd_start, "date") else str(dd_start),
        max_drawdown_end=str(dd_end.date()) if hasattr(dd_end, "date") else str(dd_end),
        beta=round(beta, 2),
        correlation_to_benchmark=round(corr, 3),
        sharpe=round(sharpe, 2),
        sortino=round(sortino, 2),
        cagr=round(cagr, 2),
        total_return=round(total_return_val * 100, 2),
    )


def compute_stock_risk(stock_returns: pd.Series) -> dict:
    """Compute risk metrics for a single stock (for the stock-level table)."""
    daily_vol = stock_returns.std()
    annual_vol = daily_vol * np.sqrt(252)
    var_95 = np.percentile(stock_returns.dropna(), 5)
    max_dd = ((1 + stock_returns).cumprod().div((1 + stock_returns).cumprod().cummax()).min() - 1) * 100

    return {
        "volatility": round(annual_vol * 100, 2),
        "var_95": round(var_95 * 100, 2),
        "max_drawdown": round(max_dd, 2),
    }


def compute_correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute the correlation matrix of all holdings."""
    return prices.pct_change().dropna().corr()


def rolling_volatility(returns: pd.Series, window: int = 21) -> pd.Series:
    """21-day rolling annualized volatility."""
    return returns.rolling(window).std() * np.sqrt(252) * 100


def _empty_risk_metrics() -> RiskMetrics:
    return RiskMetrics(
        volatility_annual=0.0,
        var_95=0.0,
        var_99=0.0,
        cvar_95=0.0,
        max_drawdown=0.0,
        max_drawdown_start="",
        max_drawdown_end="",
        beta=1.0,
        correlation_to_benchmark=0.0,
        sharpe=0.0,
        sortino=0.0,
        cagr=0.0,
        total_return=0.0,
    )
