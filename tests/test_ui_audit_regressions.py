"""Regression tests for UI audit fixes (Aug 2026).

Covers:
1. Try Sample Portfolio button must load the 7-holding sample, not an
   empty portfolio (empty-Portfolio sentinel was poisoning session state).
2. Health interpretation bands must agree with gauge labels
   (score_interpretation said LOW RISK while gauge read Moderate).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def _fake_prices(tickers: list[str], days: int = 260) -> pd.DataFrame:
    """Deterministic price frame so compute_all runs without network."""
    idx = pd.bdate_range("2025-08-01", periods=days)
    data = {}
    for i, t in enumerate(tickers):
        drift = 1.0 + 0.0002 * ((i % 3) - 1)
        data[t] = [100.0 * (drift**k) + i for k in range(days)]
    return pd.DataFrame(data, index=idx)


@pytest.fixture
def patched_fetch(monkeypatch):
    """Patch both import sites of the price fetchers."""
    import engine.compute as compute_mod

    tickers_seen: list[list[str]] = []

    def fake_fetch(holdings, period="1y", force_refresh=False, progress_callback=None):
        ts = [h.ticker for h in holdings]
        tickers_seen.append(ts)
        for h in holdings:
            h.current_price = 105.0
            h.change_pct = 0.5
        return _fake_prices(ts)

    monkeypatch.setattr(compute_mod, "fetch_prices", fake_fetch)
    monkeypatch.setattr(
        compute_mod,
        "fetch_benchmark",
        lambda choice, period="1y": _fake_prices(["^NSEI"])["^NSEI"],
    )
    # fetch_prices_refreshed is imported into compute too
    monkeypatch.setattr(compute_mod, "fetch_prices_refreshed", fake_fetch)
    return tickers_seen


def _run_app(at: AppTest) -> None:
    at.run()


class TestSamplePortfolioButton:
    def test_sample_button_loads_holdings(self, patched_fetch):
        """Clicking 'Try Sample Portfolio' must produce a non-empty portfolio."""
        at = AppTest.from_file(APP_PATH, default_timeout=300)
        at.run()
        assert not at.exception

        sample_btns = [b for b in at.button if "Try Sample" in b.label]
        assert sample_btns, "Try Sample Portfolio button should be visible"
        sample_btns[0].click()
        at.run()

        assert not at.exception
        errors = [str(e.value) for e in at.error]
        assert not any("failed to fetch" in e for e in errors), f"error shown: {errors}"

        portfolio = at.session_state["portfolio"]
        assert portfolio is not None
        assert len(portfolio.holdings) >= 5, f"sample should have ~7 holdings, got {len(portfolio.holdings)}"

    def test_empty_state_not_stored_as_portfolio(self, patched_fetch):
        """First run with no input must not persist the empty sentinel into state."""
        at = AppTest.from_file(APP_PATH, default_timeout=300)
        at.run()
        if "portfolio" in at.session_state:
            portfolio = at.session_state["portfolio"]
            assert portfolio is None or len(portfolio.holdings) > 0, (
                "empty sentinel must not be persisted into session state"
            )


class TestHealthInterpretationBands:
    def _interpret(self, overall: float) -> str:
        from engine.scoring import _interpret_scores

        return _interpret_scores(overall, conviction=50.0, stress=10.0, hidden_corr=10.0, tail=10.0)

    @pytest.mark.parametrize(
        "overall,expected_prefix",
        [
            (80.0, "HIGH RISK"),
            (50.0, "MODERATE RISK"),
            (20.0, "LOW RISK"),
        ],
    )
    def test_band_labels(self, overall, expected_prefix):
        text = self._interpret(overall)
        assert text.startswith(expected_prefix)

    def test_gauge_label_matches_interpretation(self):
        """Gauge label and interpretation text must use consistent bands.

        Gauge: health = 100 - overall; >=70 Good, >=40 Moderate, else High Risk.
        Interpretation must map to the same three buckets.
        """
        from engine.scoring import _interpret_scores

        # health = 100 - overall: 25->Good/LOW, 35->Moderate/MODERATE, 65->High Risk/HIGH
        cases = [(25.0, "Good"), (35.0, "Moderate"), (65.0, "High Risk")]
        for overall, gauge_label in cases:
            text = _interpret_scores(overall, 50.0, 10.0, 10.0, 10.0)
            if gauge_label == "Good":
                assert text.startswith("LOW RISK"), f"overall={overall}: {text}"
            elif gauge_label == "Moderate":
                assert text.startswith("MODERATE RISK"), f"overall={overall}: {text}"
            else:
                assert text.startswith("HIGH RISK"), f"overall={overall}: {text}"
