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


# Minimum annualized volatility to be considered "investable" by the optimizer.
# Excludes cash-like instruments (e.g. LIQUIDBEES, money market funds) that
# have near-zero volatility — they'd otherwise dominate risk-parity allocation.
_MIN_ANNUAL_VOL = 0.02


def _cap_max_weight(weights: list[float], max_single: float = 0.35) -> list[float]:
    """Cap individual weights at max_single and redistribute excess proportionally."""
    n = len(weights)
    if n == 0:
        return weights
    total_surplus = 0.0
    result = list(weights)
    for i in range(n):
        if result[i] > max_single:
            total_surplus += result[i] - max_single
            result[i] = max_single
    if total_surplus > 1e-12:
        uncapped = [i for i in range(n) if result[i] < max_single]
        if uncapped:
            base = sum(result[i] for i in uncapped)
            if base > 1e-12:
                for i in uncapped:
                    result[i] += total_surplus * (result[i] / base)
            else:
                for i in uncapped:
                    result[i] += total_surplus / len(uncapped)
    return result


def _ledoit_wolf_cov(values: np.ndarray) -> np.ndarray:
    """
    Ledoit-Wolf shrinkage covariance estimator (constant-correlation target).

    Shrinks the sample covariance matrix toward a constant-correlation target
    to reduce estimation error — especially important when the number of
    observations is close to the number of assets.

    Args:
        values: (n_obs, n_assets) return array

    Returns:
        Shrunk covariance matrix (n_assets x n_assets)
    """
    n, p = values.shape
    if n < 2 or p < 2:
        return np.cov(values, rowvar=False) if p < 2 else np.atleast_2d(np.var(values, ddof=1))

    sample = np.cov(values, rowvar=False)
    mean = np.mean(values, axis=0)
    centered = values - mean

    # Constant-correlation target: F_ij = r_bar * s_i * s_j,  F_ii = s_ii
    var = np.diag(sample)
    std = np.sqrt(var)
    if (std == 0).any():
        return sample
    corr = sample / np.outer(std, std)
    avg_r = (corr.sum() - p) / max(p * (p - 1), 1)
    avg_r = np.clip(avg_r, -1.0, 1.0)
    target = avg_r * np.outer(std, std)
    np.fill_diagonal(target, var)

    # π̂ = (1/n) * Σ_i ||(x_i - x̄)(x_i - x̄)' - S||²_F
    pi_mat = np.zeros((p, p))
    for i in range(n):
        yy = np.outer(centered[i], centered[i])
        diff = yy - sample
        pi_mat += diff * diff
    pi_hat = pi_mat.sum() / n

    # γ̂ = ||S - F||²_F
    gamma_hat = ((sample - target) ** 2).sum()

    # δ = max(0, min(1, (π̂ - ĉ) / (n * γ̂)))
    c_hat = np.trace(pi_mat) / p
    delta = (pi_hat - c_hat) / (n * gamma_hat) if gamma_hat > 1e-10 else 0.0
    delta = np.clip(delta, 0.0, 1.0)

    return delta * target + (1.0 - delta) * sample


def optimize_hrp(returns: pd.DataFrame) -> OptimizationResult:
    """
    Hierarchical Risk Parity (Lopez de Prado 2016).

    No covariance matrix inversion — numerically stable even with
    highly correlated assets. Uses scipy hierarchical clustering.

    Uses Ledoit-Wolf shrinkage covariance for the allocation step
    to reduce noise in the covariance estimate. Drops any columns
    with zero variance (stale/halted tickers).
    """
    if returns.empty or returns.shape[1] < 2:
        if returns.shape[1] == 1:
            return OptimizationResult(method="hrp", weights={returns.columns[0]: 1.0})
        return OptimizationResult(method="hrp", weights={})

    # Drop zero-variance columns (stale/halted tickers)
    std = returns.std()
    good_cols = std[std > 1e-12].index
    if len(good_cols) == 0:
        return OptimizationResult(method="hrp", weights={})
    if len(good_cols) == 1:
        return OptimizationResult(method="hrp", weights={good_cols[0]: 1.0})

    # Exclude cash-like instruments (annualized vol < 2%) that would
    # dominate risk-parity allocation and produce misleading results
    annual_vol = std[good_cols] * np.sqrt(252)
    investable = good_cols[annual_vol >= _MIN_ANNUAL_VOL]
    if len(investable) == 0:
        # All holdings are cash-like; can't optimize meaningfully
        return OptimizationResult(method="hrp", weights={})
    if len(investable) == 1:
        _weights = {investable[0]: 1.0}
        return OptimizationResult(method="hrp", weights=_weights)
    returns = returns[investable]

    # 1. Correlation -> distance matrix
    corr = returns.corr().values
    dist = np.sqrt(2 * (1 - np.clip(corr, -1, 1)))

    # 2. Hierarchical clustering (ward linkage)
    link = linkage(squareform(dist), method="ward")

    # 3. Quasi-diagonalization: reorder by cluster tree
    _order = _get_quasi_diag(link)
    ordered_tickers = [returns.columns[i] for i in _order]

    # 4. Recursive bisection: inverse-variance allocation
    #    Use shrinkage covariance for numerical stability
    ordered = returns.values[:, _order]
    cov = _ledoit_wolf_cov(ordered)
    weights = _recursive_bisection(cov)
    weights = _cap_max_weight(weights)

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
    alpha = 1 - var1 / (var1 + var2) if (var1 + var2) > 1e-12 else 0.5
    alpha = np.clip(alpha, 0.0, 1.0)

    w1 = _recursive_bisection(cov[np.ix_(idx1, idx1)])
    w2 = _recursive_bisection(cov[np.ix_(idx2, idx2)])

    return [alpha * w for w in w1] + [(1 - alpha) * w for w in w2]


def _inverse_variance(cov: np.ndarray) -> np.ndarray:
    """Inverse-variance weights (diagonal of covariance)."""
    diag = np.diag(cov)
    inv_diag = np.where(diag > 1e-12, 1.0 / diag, 0.0)
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
    w = _cap_max_weight(w.tolist())
    w = np.array(w) / sum(w)
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
    w = _cap_max_weight(w.tolist())
    w = np.array(w) / sum(w)
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


@dataclass
class RebalanceSuggestion:
    target_method: str
    trades: list[dict]
    total_drift_pct: float


def suggest_rebalance(
    holdings: list,
    target_method: str = "equal_weight",
    custom_targets: dict[str, float] | None = None,
) -> RebalanceSuggestion:
    """
    Suggest trades to reach target allocation.

    target_method: "equal_weight" splits evenly, "current_cap" keeps current weights.
    custom_targets: mapping of ticker -> target weight fraction.
    """
    total_value = sum(h.current_value for h in holdings)
    if total_value <= 0:
        return RebalanceSuggestion(target_method=target_method, trades=[], total_drift_pct=0.0)

    if custom_targets:
        target_weights = custom_targets
    elif target_method == "equal_weight":
        target_weights = {h.ticker: 1.0 / len(holdings) for h in holdings}
    else:
        target_weights = {h.ticker: h.current_value / total_value for h in holdings}

    total_target = sum(target_weights.values())
    if total_target > 0:
        target_weights = {t: w / total_target for t, w in target_weights.items()}

    trades = []
    total_abs_drift = 0.0
    for h in holdings:
        current_w = h.current_value / total_value
        target_w = target_weights.get(h.ticker, 0.0)
        drift = target_w - current_w
        total_abs_drift += abs(drift)
        trades.append({
            "ticker": h.ticker.replace(".NS", ""),
            "name": h.name,
            "current_w_pct": round(current_w * 100, 1),
            "target_w_pct": round(target_w * 100, 1),
            "drift_pct": round(drift * 100, 1),
            "action": "buy" if drift > 0.005 else ("sell" if drift < -0.005 else "hold"),
            "change_rs": round(drift * total_value, 0),
        })

    return RebalanceSuggestion(
        target_method=target_method,
        trades=[t for t in trades if abs(t["drift_pct"]) > 0.1],
        total_drift_pct=round(total_abs_drift * 100, 1),
    )
