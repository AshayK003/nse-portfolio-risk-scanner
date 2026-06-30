"""
Market regime detection using Hidden Markov Models.

Optional dependency: hmmlearn (pip install hmmlearn).
Gracefully falls back to None when not available.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class RegimeResult:
    """Market regime detection results."""

    n_states: int
    labels: list[str]  # e.g. ["Bull", "Neutral", "Bear"]
    state_sequence: list  # one per trading day (state label per day)
    transition_matrix: list[list[float]]
    stats: list[dict]  # per-regime: return, vol, count

try:
    from hmmlearn import hmm

    _HMMLEARN_AVAILABLE = True
except ImportError:
    _HMMLEARN_AVAILABLE = False


def detect_regimes(
    returns: pd.Series,
    n_states: int = 3,
    seed: int = 42,
) -> RegimeResult | None:
    """
    Detect market regimes using a Gaussian Hidden Markov Model.

    States are labeled by mean return (Bull = highest, Bear = lowest).

    Args:
        returns: Daily portfolio return series
        n_states: Number of hidden states (2-5 recommended)
        seed: Random seed for reproducibility

    Returns:
        RegimeResult if hmmlearn is available, None otherwise
    """
    if not _HMMLEARN_AVAILABLE:
        return None

    if returns.empty or len(returns) < 50:
        return None

    x = returns.values.reshape(-1, 1)

    model = hmm.GaussianHMM(
        n_components=n_states,
        covariance_type="diag",
        n_iter=200,
        random_state=seed,
        init_params="stmc",
        params="stmc",
    )
    model.fit(x)
    states = model.predict(x)

    # Label states by mean return (Bull > Neutral > Bear)
    state_means = {s: float(returns.iloc[np.where(states == s)[0]].mean()) for s in range(n_states)}
    sorted_states = sorted(state_means, key=lambda s: state_means[s], reverse=True)

    labels_map = {}
    n = len(sorted_states)
    if n == 2:
        labels_map = {sorted_states[0]: "Bull", sorted_states[1]: "Bear"}
    elif n == 3:
        labels_map = {sorted_states[0]: "Bull", sorted_states[1]: "Neutral", sorted_states[2]: "Bear"}
    elif n == 4:
        labels_map = {
            sorted_states[0]: "Strong Bull",
            sorted_states[1]: "Bull",
            sorted_states[2]: "Bear",
            sorted_states[3]: "Crisis",
        }
    else:
        labels_map = {s: f"State {s + 1}" for s in range(n_states)}

    labels = [labels_map[s] for s in sorted_states]
    state_seq = [labels_map[s] for s in states]

    # Per-regime stats
    stats = []
    for ls in labels:
        mask = [s == ls for s in state_seq]
        if any(mask):
            sub = returns.iloc[np.where(np.array(state_seq) == ls)[0]]
            stats.append(
                {
                    "label": ls,
                    "count": int(mask.sum()),
                    "pct": round(mask.sum() / len(mask) * 100, 1),
                    "mean_return": round(float(sub.mean()) * 100, 3),
                    "annual_vol": round(float(sub.std() * np.sqrt(252)) * 100, 2),
                    "cum_return": round((float((1 + sub).prod()) - 1) * 100, 2),
                }
            )

    # Transition matrix
    trans = model.transmat_.tolist()

    return RegimeResult(
        n_states=n_states,
        labels=labels,
        state_sequence=[labels_map[s] for s in states.tolist()],
        transition_matrix=trans,
        stats=stats,
    )
