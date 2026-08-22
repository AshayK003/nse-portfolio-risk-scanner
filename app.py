"""
NSE Portfolio Risk Scanner — Streamlit app entry point.

Thin orchestration layer: reads input -> computes risk -> renders UI.
Engine has ZERO Streamlit imports. UI has ZERO business logic.
All computation lives in engine/compute.py; all rendering in ui/render.py.
"""

from __future__ import annotations

import streamlit as st

from engine import RISK_PROFILES, Portfolio
from engine.benchmark import BENCHMARK_TICKERS
from engine.compute import compute_all, compute_input_hash
from ui.icons import BAR_CHART_3, icon_html
from ui.render import render_all_tabs
from ui.styles import inject_css
from ui.upload import render_data_editor, render_sidebar, render_upload_tab


def _share_link(portfolio: Portfolio) -> None:
    """Render shareable base64 portfolio link."""
    with st.expander("Share Portfolio", expanded=False):
        from engine.portfolio import encode_portfolio_link

        encoded = encode_portfolio_link(portfolio)
        st.code(f"?p={encoded}", language="text")
        st.caption(
            "Append this to the app URL to share your portfolio. "
            "Example: `https://yourapp.streamlit.app/?p=...` "
            "No data is stored on any server."
        )


def main() -> None:
    # Page config
    st.set_page_config(
        page_title="NSE Portfolio Risk Scanner",
        page_icon=None,
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Inject premium dark theme CSS
    inject_css()

    # Title with Lucide icon
    st.markdown(
        f"<h1 style='display: flex; align-items: center; gap: 0.5rem;'>"
        f"{icon_html(BAR_CHART_3, size=28)} NSE Portfolio Risk Scanner"
        f"</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Upload a CSV or add stocks manually to analyze risk metrics, "
        "sector concentration, and benchmark comparison."
    )

    # ── Sidebar ──
    render_sidebar()

    # ── Session state initialization ──
    if "portfolio" not in st.session_state:
        st.session_state.portfolio = None
    if "report" not in st.session_state:
        st.session_state.report = None
    if "force_refresh_cb" not in st.session_state:
        st.session_state.force_refresh_cb = False
    if "force_refresh" not in st.session_state:
        st.session_state.force_refresh = False

    # ── Step 1: Upload or use existing portfolio ──
    portfolio = render_upload_tab()
    if portfolio is None:
        st.stop()

    # Don't persist an empty placeholder — it poisons later runs that
    # trust session_state.portfolio (e.g. after clicking Try Sample).
    if portfolio.holdings:
        st.session_state.portfolio = portfolio

    # Allow editing
    portfolio = render_data_editor(portfolio)

    _share_link(portfolio)

    # ── Step 2: Benchmark selection ──
    benchmark_options = {v: k for k, v in BENCHMARK_TICKERS.items()}
    default_benchmark = "^NSEI"
    # Force refresh toggle — inline with the benchmark selector
    bench_col, refresh_col = st.columns([3, 1])
    with bench_col:
        benchmark_choice = st.selectbox(
            "Benchmark Index",
            options=list(benchmark_options.keys()),
            format_func=lambda x: benchmark_options[x],
            index=list(benchmark_options.keys()).index(default_benchmark)
            if default_benchmark in benchmark_options
            else 0,
            key="benchmark_selector",
        )
    with refresh_col:
        force = st.checkbox("Force refresh prices", value=False, key="force_refresh_cb")
    st.session_state.force_refresh = bool(force)

    risk_free_rate = st.session_state.get("risk_free_rate", 6.5) / 100.0
    risk_profile_key = st.session_state.get("risk_profile", "moderate")
    _ = RISK_PROFILES[risk_profile_key]  # validate key exists

    # ── Input hash — skip recomputation when portfolio hasn't changed ──
    current_hash = compute_input_hash(portfolio, benchmark_choice, risk_profile_key, risk_free_rate)
    _needs_compute = (
        st.session_state.force_refresh or st.session_state.get("_last_input_hash") != current_hash
    )

    if _needs_compute:
        with st.spinner("Analyzing portfolio…"):
            try:
                report, ctx = compute_all(
                    portfolio=portfolio,
                    benchmark_choice=benchmark_choice,
                    risk_profile_key=risk_profile_key,
                    risk_free_rate=risk_free_rate,
                    force_refresh=st.session_state.force_refresh,
                )
                st.session_state.report = report
                st.session_state._ctx = ctx
                st.session_state._last_input_hash = current_hash
                st.session_state.force_refresh = False
            except ValueError as e:
                st.error(f"Could not analyze portfolio: {e}")
                st.stop()
            except Exception as e:  # noqa: BLE001
                st.error(f"An unexpected error occurred during analysis: {e}")
                st.stop()

        # Save analysis run to history (fresh computation only)
        try:
            from storage.db import save_analysis_run
            from storage.models import analysis_from_report

            save_analysis_run(
                analysis_from_report(report, benchmark_name=benchmark_options[benchmark_choice])
            )
        except Exception as e:  # noqa: BLE001
            from engine._log import logger

            logger.error("Failed to save analysis run: {e}", e=e)

    # ── Step 4: Render all tabs from cached context ──
    report = st.session_state.report
    ctx = st.session_state.get("_ctx")
    if report is None or ctx is None:
        st.error("Analysis not available. Please re-upload your portfolio.")
        st.stop()

    render_all_tabs(ctx, report)


if __name__ == "__main__":
    main()
