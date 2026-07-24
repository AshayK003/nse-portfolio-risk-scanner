"""
PELVE — Probability Equivalent Level of VaR and Expected Shortfall.

Answers: "If I replace VaR with ES in my risk model, by how much does my
capital requirement change?"  A PELVE > 2.5 means ES at 97.5% gives a
higher risk estimate than VaR at 99% (Basel III scenario).

Pure numpy — no new dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


@dataclass
class PelveResult:
    """PELVE analysis result."""

    pelve: float  # The PELVE ratio
    epsilon: float  # The tail probability used (typically 0.01)
    interpretation: str  # Plain-English explanation


def compute_pelve(returns: np.ndarray, epsilon: float = 0.01) -> PelveResult | None:
    """Compute PELVE using the parametric normal method.

    Parameters
    ----------
    returns : np.ndarray
        Historical portfolio returns.
    epsilon : float
        Tail probability (default 0.01, corresponding to 99% VaR).

    Returns
    -------
    PelveResult | None
        None if insufficient data.
    """
    returns = np.asarray(returns, dtype=float)
    n = len(returns)
    if n < 10:
        return None

    mu = float(np.mean(returns))
    sigma = float(np.std(returns, ddof=1))

    if sigma <= 0:
        return None

    # VaR at confidence 1 - epsilon (positive loss number)
    # Formula: VaR_α = -μ + σ * Φ⁻¹(α)  where α is confidence level
    var_eps = -mu + sigma * norm.ppf(1 - epsilon)

    # ES at confidence 1 - epsilon (normal, positive loss number)
    # Formula: ES_α = -μ + σ * φ(Φ⁻¹(α)) / (1-α)
    z = norm.ppf(1 - epsilon)
    es_eps = -mu + sigma * norm.pdf(z) / epsilon

    if var_eps <= 0:
        return None

    # PELVE is the multiplier c such that ES_{1 - c*ε}(X) = VaR_{1 - ε}(X)
    # We solve for c in: ES(1 - c*ε) = VaR(1 - ε)
    # Under normal:  ES(α) = -μ + σ * φ(Φ⁻¹(α)) / (1-α)
    #   where α = 1 - c*ε

    def _es(c: float) -> float:
        alpha = 1.0 - c * epsilon
        if alpha <= 0 or alpha >= 1:
            return 1e12
        z_c = norm.ppf(alpha)
        return -mu + sigma * norm.pdf(z_c) / (1.0 - alpha)

    target = var_eps

    try:
        pelve = brentq(lambda c: _es(c) - target, 0.5, 10.0)
    except (ValueError, RuntimeError):
        pelve = es_eps / var_eps

    # Interpretation
    if pelve > 2.5:
        interp = (
            f"PELVE of {pelve:.2f} is above 2.5 — switching from VaR to ES "
            f"at standard risk weights would INCREASE capital requirements. "
            f"Tail risk is heavier than normal."
        )
    elif pelve < 2.5:
        interp = (
            f"PELVE of {pelve:.2f} is below 2.5 — switching from VaR to ES "
            f"would DECREASE capital requirements. "
            f"Tail risk is lighter than normal."
        )
    else:
        interp = f"PELVE of {pelve:.2f} is exactly at the Basel benchmark of 2.5."

    return PelveResult(pelve=round(pelve, 4), epsilon=epsilon, interpretation=interp)
