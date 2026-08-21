"""Black-box test of the Streamlit app via streamlit.testing.v1.AppTest.

Runs the REAL app headlessly, drives the actual widgets, and verifies the
end-to-end flow works — including the M1 regression (mutating a widget's
session_state key after instantiation used to crash the whole app).

The sample portfolio is injected through the `?p=` share-link query param,
which also exercises L2 (urlsafe base64 decode) and the H1 package import path.
"""

import os

from streamlit.testing.v1 import AppTest

from engine import Holding, Portfolio
from engine.portfolio import encode_portfolio_link

_APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


SAMPLE = Portfolio(
    holdings=[
        Holding(ticker="RELIANCE", name="Reliance Industries", quantity=10, avg_price=2500.0),
        Holding(ticker="TCS", name="Tata Consultancy Services", quantity=5, avg_price=3500.0),
        Holding(ticker="HDFCBANK", name="HDFC Bank", quantity=20, avg_price=1600.0),
    ],
    name="Sample Blackbox Portfolio",
)


def _launch_with_sample() -> AppTest:
    token = encode_portfolio_link(SAMPLE)  # L2 urlsafe round-trip exercised on decode
    at = AppTest.from_file(_APP_PATH, default_timeout=30)
    at.query_params["p"] = token  # injected before first run; exercises L2 decode path
    at.run()
    return at


def test_app_loads_and_renders_without_crash():
    """The app boots, loads the shared portfolio, and renders analysis tabs."""
    at = _launch_with_sample()
    assert not at.exception, f"App raised: {at.exception}"
    # A force-refresh checkbox must exist (the widget whose key M1 used to clobber)
    assert any(w.label == "Force refresh prices" for w in at.checkbox), "force-refresh checkbox missing"
    assert any(w.label == "Benchmark Index" for w in at.selectbox), "benchmark selector missing"


def test_m1_force_refresh_rerun_does_not_crash():
    """REGRESSION: toggling force_refresh + rerun must not raise the
    'cannot be modified after the widget ... is instantiated' error."""
    at = _launch_with_sample()
    # Toggle the checkbox to True and rerun (this previously wrote back to
    # st.session_state.force_refresh_cb and crashed on the next rerun).
    at.checkbox[0].set_value(True).run()
    assert not at.exception, f"M1 regression: app raised after force-refresh rerun: {at.exception}"
    # Second rerun with the checkbox still True must also be clean.
    at.run()
    assert not at.exception, f"M1 regression on 2nd rerun: {at.exception}"


def test_benchmark_selection_change_reruns_cleanly():
    """Changing the benchmark selector triggers a recompute; must not crash."""
    at = _launch_with_sample()
    bench = next(w for w in at.selectbox if w.label == "Benchmark Index")
    bench.set_value("^NSEBANK").run()
    assert not at.exception, f"Bench change crashed: {at.exception}"
