"""
VaR backtesting — Kupiec Proportion-of-Failures (POF) test.
Validates whether a VaR model correctly forecasts tail risk.
Pure numpy — no new dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log

import numpy as np


@dataclass
class KupiecResult:
    """Kupiec POF backtest result for a single confidence level."""

    confidence: float        # VaR confidence level (e.g. 0.95)
    exceptions: int          # Number of VaR breaches
    observations: int        # Total backtest observations
    expected_exceptions: float  # Expected breaches under correct model
    exception_rate: float    # Actual breach rate
    lr_stat: float           # Likelihood ratio statistic
    p_value: float           # p-value (reject if < 0.05)
    passed: bool             # True if p_value >= 0.05 (fail to reject)


def kupiec_pof(var_forecasts: np.ndarray, realized_returns: np.ndarray,
               confidence: float = 0.95) -> KupiecResult:
    """Run Kupiec POF backtest on aligned VaR forecasts and realized returns.

    Parameters
    ----------
    var_forecasts : np.ndarray
        VaR forecasts as positive numbers (e.g. 0.02 for 2% VaR).
        Must be the same length as realized_returns.
    realized_returns : np.ndarray
        Actual daily returns (e.g. -0.015 for -1.5%).
    confidence : float
        VaR confidence level (default 0.95).

    Returns
    -------
    KupiecResult
    """
    var_forecasts = np.asarray(var_forecasts, dtype=float)
    realized_returns = np.asarray(realized_returns, dtype=float)

    # VaR is a threshold: loss exceeds VaR when return < -VaR
    p = 1.0 - confidence
    exceptions = np.sum(realized_returns < -var_forecasts)
    n = len(var_forecasts)
    x = int(exceptions)
    expected = n * p

    if n == 0:
        return KupiecResult(confidence=confidence, exceptions=0, observations=0,
                            expected_exceptions=0, exception_rate=0.0,
                            lr_stat=0.0, p_value=1.0, passed=True)

    actual_rate = x / n

    # Kupiec LR: -2 * ln(L_null / L_alt)
    # L_null: binomial with p = 1 - confidence
    # L_alt:  binomial with p = actual_rate
    if x == 0:
        lr = -2.0 * (n * log(1.0 - p) - 0.0)
    elif x == n:
        lr = -2.0 * (n * log(p) - 0.0)
    else:
        lr_null = x * log(p) + (n - x) * log(1.0 - p)
        lr_alt = x * log(actual_rate) + (n - x) * log(1.0 - actual_rate)
        lr = -2.0 * (lr_null - lr_alt)

    from scipy.stats import chi2
    p_value = 1.0 - chi2.cdf(lr, 1)

    return KupiecResult(
        confidence=confidence,
        exceptions=x,
        observations=n,
        expected_exceptions=expected,
        exception_rate=actual_rate,
        lr_stat=round(lr, 4),
        p_value=round(p_value, 4),
        passed=p_value >= 0.05,
    )


def backtest_var(var_forecasts: np.ndarray, realized_returns: np.ndarray,
                 confidences: list[float] | None = None) -> list[KupiecResult]:
    """Run Kupiec backtest at multiple confidence levels."""
    if confidences is None:
        confidences = [0.95, 0.99]
    return [kupiec_pof(var_forecasts, realized_returns, c) for c in confidences]
