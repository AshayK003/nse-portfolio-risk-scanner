"""
Portfolio optimization — HRP and mean-variance.

All functions are PURE — they accept return DataFrames and return weights.
Zero side effects, zero IO, zero Streamlit imports.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform


@dataclass
class OptimizationResult:
    """Optimal portfolio weights from optimization."""

    method: str  # "hrp", "min_volatility", "max_sharpe"
    weights: dict[str, float]  # ticker -> weight
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe: float = 0.0


def optimize_hrp(returns: pd.DataFrame) -> OptimizationResult:
    """
    Hierarchical Risk Parity (Lopez de Prado 2016).

    No covariance matrix inversion — numerically stable even with
    highly correlated assets. Uses scipy hierarchical clustering.
    """
    if returns.empty or returns.shape[1] < 2:
        _weights = {returns.columns[0]: 1.0} if returns.shape[1] == 1 else {}
        return OptimizationResult(method="hrp", weights=_weights)

    # 1. Correlation -> distance matrix
    corr = returns.corr().values
    dist = np.sqrt(2 * (1 - np.clip(corr, -1, 1)))

    # 2. Hierarchical clustering (ward linkage)
    link = linkage(squareform(dist), method="ward")

    # 3. Quasi-diagonalization: reorder by cluster tree
    _order = _get_quasi_diag(link)
    ordered_tickers = [returns.columns[i] for i in _order]

    # 4. Recursive bisection: inverse-variance allocation
    ordered = returns.values[:, _order]
    cov = np.cov(ordered, rowvar=False)
    weights = _recursive_bisection(cov)

    result = dict(zip(ordered_tickers, weights, strict=False))
    return OptimizationResult(method="hrp", weights=result)


def _get_quasi_diag(link: np.ndarray) -> list[int]:
    """Reorder assets by hierarchical clustering order (quasi-diagonalization)."""
    from scipy.cluster.hierarchy import leaves_list
    return leaves_list(link).tolist()


def _recursive_bisection(cov: np.ndarray) -> list[float]:
    """Recursive bisection: split cluster, assign inverse-variance weights."""
    n = cov.shape[0]
    if n == 1:
        return [1.0]

    # Split into two clusters (first half / second half)
    mid = n // 2
    idx1 = list(range(mid))
    idx2 = list(range(mid, n))

    def cluster_var(indices: list[int]) -> float:
        sub_cov = cov[np.ix_(indices, indices)]
        w = _inverse_variance(sub_cov)
        return float(w @ sub_cov @ w)

    var1 = cluster_var(idx1)
    var2 = cluster_var(idx2)

    # Weight each cluster proportional to inverse variance
    alpha = 1 - var1 / (var1 + var2)
    alpha = np.clip(alpha, 0.0, 1.0)

    w1 = _recursive_bisection(cov[np.ix_(idx1, idx1)])
    w2 = _recursive_bisection(cov[np.ix_(idx2, idx2)])

    return [alpha * w for w in w1] + [(1 - alpha) * w for w in w2]


def _inverse_variance(cov: np.ndarray) -> np.ndarray:
    """Inverse-variance weights (diagonal of covariance)."""
    inv_diag = 1.0 / np.diag(cov)
    return inv_diag / inv_diag.sum()


def optimize_min_volatility(returns: pd.DataFrame, risk_free_rate: float = 0.065) -> OptimizationResult:
    """Minimum volatility portfolio (SciPy constrained optimization)."""
    from scipy.optimize import minimize

    if returns.empty or returns.shape[1] < 2:
        w = {returns.columns[0]: 1.0} if returns.shape[1] == 1 else {}
        return OptimizationResult(method="min_volatility", weights=w)

    n = returns.shape[1]
    cov = returns.cov().values * 252

    def portfolio_vol(w):
        return np.sqrt(w @ cov @ w)

    constraints = {"type": "eq", "fun": lambda w: w.sum() - 1.0}
    bounds = [(0.0, 1.0)] * n
    result = minimize(portfolio_vol, np.ones(n) / n, method="SLSQP", bounds=bounds, constraints=constraints)

    w = np.ones(n) / n if not result.success else result.x
    w = w / w.sum()
    port_ret = w @ (returns.mean().values * 252)
    port_vol = portfolio_vol(w)
    sharpe = (port_ret - risk_free_rate) / port_vol if port_vol > 0 else 0.0

    return OptimizationResult(
        method="min_volatility",
        weights=dict(zip(returns.columns, w, strict=False)),
        expected_return=round(port_ret * 100, 2),
        expected_volatility=round(port_vol * 100, 2),
        sharpe=round(sharpe, 2),
    )


def optimize_max_sharpe(returns: pd.DataFrame, risk_free_rate: float = 0.065) -> OptimizationResult:
    """Maximum Sharpe ratio portfolio."""
    from scipy.optimize import minimize

    if returns.empty or returns.shape[1] < 2:
        w = {returns.columns[0]: 1.0} if returns.shape[1] == 1 else {}
        return OptimizationResult(method="max_sharpe", weights=w)

    n = returns.shape[1]
    cov = returns.cov().values * 252
    mu = returns.mean().values * 252
    rf = risk_free_rate

    def neg_sharpe(w):
        port_ret = w @ mu
        port_vol = np.sqrt(w @ cov @ w)
        return -(port_ret - rf) / port_vol if port_vol > 0 else 0.0

    constraints = {"type": "eq", "fun": lambda w: w.sum() - 1.0}
    bounds = [(0.0, 1.0)] * n
    result = minimize(neg_sharpe, np.ones(n) / n, method="SLSQP", bounds=bounds, constraints=constraints)

    w = np.ones(n) / n if not result.success else result.x
    w = w / w.sum()
    port_ret = w @ mu
    port_vol = np.sqrt(w @ cov @ w)
    sharpe = (port_ret - rf) / port_vol if port_vol > 0 else 0.0

    return OptimizationResult(
        method="max_sharpe",
        weights=dict(zip(returns.columns, w, strict=False)),
        expected_return=round(port_ret * 100, 2),
        expected_volatility=round(port_vol * 100, 2),
        sharpe=round(sharpe, 2),
    )
