"""
Risk metric computation.
All functions are PURE — they accept DataFrames/arrays and return dicts/dataclasses.
Zero side effects, zero IO, zero Streamlit imports.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import MonteCarloResult, RiskMetrics


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


# ── Monte Carlo Simulation ──


def monte_carlo_simulation(
    returns: pd.Series,
    n_simulations: int = 10000,
    horizon_days: int = 252,
    seed: int = 42,
) -> MonteCarloResult:
    """
    Forward-looking Monte Carlo simulation using Geometric Brownian Motion.

    Args:
        returns: Historical portfolio daily returns
        n_simulations: Number of simulated paths
        horizon_days: Trading days to project forward
        seed: Random seed for reproducibility

    Returns:
        MonteCarloResult with distribution statistics
    """
    if returns.empty:
        return MonteCarloResult(
            n_simulations=n_simulations,
            horizon_days=horizon_days,
            expected_return=0.0,
            median_return=0.0,
            var_95=0.0,
            var_99=0.0,
            cvar_95=0.0,
            prob_profit=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
        )

    mu = returns.mean()
    sigma = returns.std()

    rng = np.random.default_rng(seed)
    dt = 1.0
    # GBM: S_t = S_0 * exp((mu - 0.5*sigma^2)*t + sigma * sqrt(t) * Z)
    drift = (mu - 0.5 * sigma**2) * dt
    shock = sigma * np.sqrt(dt) * rng.normal(0, 1, (horizon_days, n_simulations))

    # Cumulative returns for each path
    cum_returns = np.exp(np.cumsum(drift + shock, axis=0))

    # Final period returns (relative to start = 1.0)
    final = cum_returns[-1, :] - 1.0

    expected = float(np.mean(final)) * 100
    median_r = float(np.median(final)) * 100
    var_95 = float(np.percentile(final, 5)) * 100
    var_99 = float(np.percentile(final, 1)) * 100
    cvar_95 = float(np.mean(final[final <= np.percentile(final, 5)])) * 100
    prob_profit = float(np.mean(final > 0)) * 100
    ci_lower = float(np.percentile(final, 5)) * 100
    ci_upper = float(np.percentile(final, 95)) * 100

    return MonteCarloResult(
        n_simulations=n_simulations,
        horizon_days=horizon_days,
        expected_return=round(expected, 2),
        median_return=round(median_r, 2),
        var_95=round(var_95, 2),
        var_99=round(var_99, 2),
        cvar_95=round(cvar_95, 2),
        prob_profit=round(prob_profit, 1),
        ci_lower=round(ci_lower, 2),
        ci_upper=round(ci_upper, 2),
    )


def monte_carlo_paths(
    returns: pd.Series,
    n_simulations: int = 1000,
    horizon_days: int = 252,
    seed: int = 42,
) -> np.ndarray:
    """Return raw simulation paths for charting (shape: horizon_days x n_simulations)."""
    mu = returns.mean()
    sigma = returns.std()
    rng = np.random.default_rng(seed)
    drift = (mu - 0.5 * sigma**2)
    shocks = sigma * rng.normal(0, 1, (horizon_days, n_simulations))
    return np.exp(np.cumsum(drift + shocks, axis=0)) * 100


# ── Correlation Denoising (Marchenko-Pastur) ──


def _marchenko_pastur_bound(n_features: int, n_samples: int, q: float | None = None) -> float:
    """Upper bound of Marchenko-Pastur distribution for noisy eigenvalues."""
    if q is None:
        q = n_features / n_samples if n_samples > 0 else 1.0
    q = max(q, 1e-6)
    return (1 + np.sqrt(q)) ** 2


def denoise_correlation(corr: pd.DataFrame, n_samples: int) -> pd.DataFrame:
    """
    Denoise correlation matrix using Marchenko-Pastur eigenvalue clipping.

    Eigenvalues above the MP bound are retained; those below are averaged
    to reduce noise while preserving signal.

    Args:
        corr: Empirical correlation matrix
        n_samples: Number of observations used to estimate the matrix

    Returns:
        Denoised correlation matrix
    """
    if corr.empty or corr.shape[0] < 2:
        return corr

    n = corr.shape[0]
    values, vectors = np.linalg.eigh(corr.values)
    mp_bound = _marchenko_pastur_bound(n, n_samples)

    # Keep eigenvalues above MP bound, replace noise with mean of noise eigenvalues
    noise_mask = values <= mp_bound
    noise_mean = values[noise_mask].mean() if noise_mask.any() else 0.0

    denoised_values = np.where(noise_mask, noise_mean, values)

    # Reconstruct
    denoised = vectors @ np.diag(denoised_values) @ vectors.T

    # Re-normalize to correlation matrix (unit diagonal)
    d = np.sqrt(np.diag(denoised))
    d[d == 0] = 1.0
    denoised = denoised / np.outer(d, d)
    denoised = np.clip(denoised, -1, 1)

    return pd.DataFrame(denoised, index=corr.index, columns=corr.columns)
