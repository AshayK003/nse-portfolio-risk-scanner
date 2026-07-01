"""
GARCH(1,1) with Student-t innovations — time-varying VaR.
Handles volatility clustering that static VaR models miss.
Optional dependency: pip install arch.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    from arch import arch_model
    ARCH_AVAILABLE = True
except ImportError:
    ARCH_AVAILABLE = False


@dataclass
class GarchVaRResult:
    """GARCH(1,1)-t VaR forecast."""

    method: str            # "GARCH-t" or "Static Normal (arch missing)"
    var_95: float          # One-day VaR at 95%
    var_99: float          # One-day VaR at 99%
    conditional_vol: float  # Last predicted conditional volatility (annualized)
    converged: bool        # Whether GARCH model converged
    details: str | None    # Warning if arch not installed


@dataclass
class GarchVaRSeries:
    """Full GARCH(1,1)-t VaR series for backtesting."""

    method: str
    var_95_series: np.ndarray   # Daily 95% VaR forecasts
    var_99_series: np.ndarray   # Daily 99% VaR forecasts
    cond_vol_series: np.ndarray  # Conditional volatility forecasts
    n_observations: int


def estimate_garch_var(returns: np.ndarray, confidence: float = 0.95) -> GarchVaRResult:
    """Fit GARCH(1,1)-t and return the latest one-day VaR.

    Falls back to static normal VaR when arch is not installed.
    """
    returns = np.asarray(returns, dtype=float)
    n = len(returns)
    if n < 30:
        return GarchVaRResult(method="Insufficient data", var_95=0.0, var_99=0.0,
                              conditional_vol=0.0, converged=False,
                              details=f"Need >=30 observations, got {n}")

    if not ARCH_AVAILABLE:
        return _fallback_var(returns, confidence)

    try:
        am = arch_model(returns * 100, vol="Garch", p=1, q=1, dist="students-t",
                        rescale=False)
        res = am.fit(update_freq=0, disp="off")
        forecast = res.forecast(horizon=1)
        cond_vol_pct = np.sqrt(forecast.variance.iloc[-1, 0])  # daily vol in %
        mu_pct = float(np.mean(returns * 100))  # mean return in %

        from scipy.stats import t as t_dist
        dof = res.params.get("nu", 5)
        t_95 = t_dist.ppf(0.95, dof)
        t_99 = t_dist.ppf(0.99, dof)

        # VaR = -μ + σ * q_α  (positive loss number)
        var_95 = (-mu_pct + cond_vol_pct * t_95) / 100
        var_99 = (-mu_pct + cond_vol_pct * t_99) / 100
        cond_vol_annual = cond_vol_pct * np.sqrt(252)

        return GarchVaRResult(method="GARCH-t", var_95=round(var_95, 4),
                              var_99=round(var_99, 4),
                              conditional_vol=round(cond_vol_annual, 2),
                              converged=True, details=None)
    except Exception as e:
        return _fallback_var(returns, confidence,
                             details=f"GARCH failed: {e}")


def _fallback_var(returns: np.ndarray, confidence: float,
                  details: str | None = None) -> GarchVaRResult:
    """Static normal VaR fallback (positive loss number)."""
    mu = float(np.mean(returns))
    sigma = float(np.std(returns, ddof=1))
    from scipy.stats import norm
    var_95 = -mu + sigma * norm.ppf(0.95)
    var_99 = -mu + sigma * norm.ppf(0.99)
    cond_vol = sigma * np.sqrt(252)
    return GarchVaRResult(method="Static Normal (arch missing)",
                          var_95=round(var_95, 4), var_99=round(var_99, 4),
                          conditional_vol=round(cond_vol, 2),
                          converged=False, details=details)


def _has_arch() -> bool:
    return ARCH_AVAILABLE
