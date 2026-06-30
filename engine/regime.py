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


def _label_map(n_states: int) -> dict[int, str]:
    """Build regime label map for given number of states."""
    if n_states == 2:
        return {0: "Bull", 1: "Bear"}
    if n_states == 3:
        return {0: "Bull", 1: "Neutral", 2: "Bear"}
    if n_states == 4:
        return {0: "Strong Bull", 1: "Bull", 2: "Bear", 3: "Crisis"}
    return {i: f"State {i + 1}" for i in range(n_states)}


def _compute_stats(
    returns: pd.Series, state_seq: list[str], labels: list[str]
) -> list[dict]:
    """Per-regime statistics from state sequence."""
    stats = []
    for ls in labels:
        count = state_seq.count(ls)
        if count > 0:
            sub = returns.iloc[np.where(np.array(state_seq) == ls)[0]]
            stats.append(
                {
                    "label": ls,
                    "count": count,
                    "pct": round(count / len(state_seq) * 100, 1),
                    "mean_return": round(float(sub.mean()) * 100, 3),
                    "annual_vol": round(float(sub.std() * np.sqrt(252)) * 100, 2),
                    "cum_return": round((float((1 + sub).prod()) - 1) * 100, 2),
                }
            )
    return stats


def _transition_matrix(state_seq: list[str], labels: list[str]) -> list[list[float]]:
    """Build transition probability matrix from state sequence."""
    n = len(labels)
    label_to_idx = {lbl: i for i, lbl in enumerate(labels)}
    counts = np.zeros((n, n), dtype=float)
    for i in range(len(state_seq) - 1):
        r, c = label_to_idx[state_seq[i]], label_to_idx[state_seq[i + 1]]
        counts[r, c] += 1.0
    row_sums = counts.sum(axis=1, keepdims=True)
    trans = np.divide(counts, row_sums, out=np.zeros_like(counts), where=row_sums > 0)
    return trans.tolist()


def _detect_statistical(returns: pd.Series, n_states: int) -> RegimeResult | None:
    """Regime detection via rolling return quantiles (no external deps)."""
    window = min(21, len(returns) // 4)
    rolling = returns.rolling(window=window, min_periods=window).mean()
    valid = rolling.dropna()
    if len(valid) < 10:
        return None

    # Assign regimes by quantile thresholds
    edges = np.linspace(0, 1, n_states + 1)[1:-1]
    thresholds = [valid.quantile(q) for q in edges]
    state_seq_raw = np.full(len(returns), n_states - 1, dtype=int)
    for i, t in enumerate(thresholds):
        state_seq_raw[rolling >= t] = i
    # fill early window with first valid state
    first_valid = int(rolling.notna().values.argmax()) if rolling.notna().any() else 0
    state_seq_raw[:first_valid] = state_seq_raw[first_valid]

    # Reorder: state 0 = highest return
    state_means = {s: float(returns.iloc[np.where(state_seq_raw == s)[0]].mean()) for s in range(n_states)}
    order = sorted(range(n_states), key=lambda s: state_means[s], reverse=True)
    remap = {old: new for new, old in enumerate(order)}
    state_seq_mapped = [remap[s] for s in state_seq_raw]

    labels_map = _label_map(n_states)
    labels = [labels_map[i] for i in range(n_states)]
    state_labels = [labels_map[s] for s in state_seq_mapped]

    stats = _compute_stats(returns, state_labels, labels)
    trans = _transition_matrix(state_labels, labels)

    return RegimeResult(
        n_states=n_states,
        labels=labels,
        state_sequence=state_labels,
        transition_matrix=trans,
        stats=stats,
    )


def _detect_hmm(returns: pd.Series, n_states: int, seed: int) -> RegimeResult | None:
    """Regime detection via Gaussian HMM."""
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
    labels_map = _label_map(n_states)
    labels = [labels_map[i] for i in range(n_states)]
    remap = {old: labels_map[new] for new, old in enumerate(sorted_states)}
    state_labels = [remap[s] for s in states.tolist()]

    stats = _compute_stats(returns, state_labels, labels)
    trans = model.transmat_.tolist()

    return RegimeResult(
        n_states=n_states,
        labels=labels,
        state_sequence=state_labels,
        transition_matrix=trans,
        stats=stats,
    )


def detect_regimes(
    returns: pd.Series,
    n_states: int = 3,
    seed: int = 42,
) -> RegimeResult | None:
    """
    Detect market regimes.

    Uses Gaussian HMM when hmmlearn is available, otherwise falls back
    to a statistical approach (rolling return quantiles).

    Args:
        returns: Daily portfolio return series
        n_states: Number of hidden states (2-5 recommended)
        seed: Random seed for reproducibility (HMM only)

    Returns:
        RegimeResult or None if insufficient data
    """
    if returns.empty or len(returns) < 50:
        return None

    if _HMMLEARN_AVAILABLE:
        return _detect_hmm(returns, n_states, seed)
    return _detect_statistical(returns, n_states)
