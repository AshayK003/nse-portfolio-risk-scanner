"""
Fundamentals display section.

Fetches valuation, profitability, and growth metrics for each holding via
yfinance.info and renders a comparison table + per-stock detail. Results are
cached in Streamlit's session state so re-renders don't re-hit the network.

Only shows metrics that actually came back from the API — no fabricated values.
If data is unavailable for a ticker, that row is marked "N/A".
"""

from __future__ import annotations

import streamlit as st

from engine import Portfolio
from ui.icons import LINE_CHART, icon_html

# Fields we want, mapped to a display label + formatting hint
# yfinance info keys are used; derived metrics (PEG, etc.) are computed in _enrich
_FUNDAMENTAL_FIELDS = [
    ("trailingPE", "P/E (TTM)", "x"),
    ("forwardPE", "Forward P/E", "x"),
    ("pegRatio", "PEG Ratio", "x"),        # computed: trailingPE / earningsGrowth
    ("priceToBook", "P/B", "x"),
    ("dividendYield", "Dividend Yield", "%"),
    ("marketCap", "Market Cap", "cr"),
    ("returnOnEquity", "ROE", "%"),
    ("returnOnAssets", "ROA", "%"),
    ("profitMargins", "Profit Margin", "%"),
    ("operatingMargins", "Operating Margin", "%"),
    ("revenueGrowth", "Revenue Growth", "%"),
    ("earningsGrowth", "EPS Growth", "%"),
    ("debtToEquity", "Debt/Equity", "x"),
    ("freeCashflow", "Free Cash Flow", "cr"),
]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fundamentals(ticker: str) -> dict:
    """Fetch fundamental metrics for one ticker. Returns a flat dict.

    Keys mirror yfinance info keys. Missing keys are simply absent.
    Also adds computed fields: pegRatio (if trailingPE + earningsGrowth exist).
    """
    try:
        import yfinance as yf

        stock = yf.Ticker(f"{ticker}.NS")
        info = stock.info or {}
        raw = {k: info.get(k) for k, _, _ in _FUNDAMENTAL_FIELDS if k != "pegRatio" and info.get(k) is not None}

        # Compute PEG: trailingPE / earningsGrowth (both must exist, growth > 0)
        pe = info.get("trailingPE")
        eps_growth = info.get("earningsGrowth")
        if pe is not None and eps_growth is not None:
            try:
                peg = float(pe) / float(eps_growth)
                if eps_growth > 0:
                    raw["pegRatio"] = peg
            except (TypeError, ValueError, ZeroDivisionError):
                pass

        return raw
    except Exception:
        return {}


def _format(value, unit: str) -> str:
    """Format a raw yfinance value for display."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if unit == "%":
        return f"{v * 100:,.1f}%"
    if unit == "x":
        return f"{v:,.1f}x"
    if unit == "cr":
        # marketCap / freeCashflow come in absolute rupees → convert to crores
        return f"Rs {v / 1e7:,.0f} Cr"
    return f"{v:,.1f}"


def render_fundamentals_section(portfolio: Portfolio):
    """Render the Fundamentals tab content."""
    st.subheader("Fundamentals at a Glance")
    st.caption(
        "Valuation, profitability, and growth metrics per holding. "
        "Data sourced from Yahoo Finance; 'N/A' means the field was not reported. "
        "PEG = P/E ÷ EPS Growth (computed)."
    )

    holdings = portfolio.holdings
    if not holdings:
        st.info("Add holdings to see fundamentals.")
        return

    # Build table
    rows = []
    for h in holdings:
        data = fetch_fundamentals(h.ticker.replace(".NS", ""))
        row = {"Stock": h.ticker.replace(".NS", "")}
        for key, label, unit in _FUNDAMENTAL_FIELDS:
            row[label] = _format(data.get(key), unit)
        rows.append(row)

    st.dataframe(
        rows,
        width='stretch',
        hide_index=True,
    )

    # Per-stock detail in expanders
    st.divider()
    st.subheader("Per-Stock Detail")
    for h in holdings:
        with st.expander(f"{h.ticker.replace('.NS', '')} — {h.name}", expanded=False):
            data = fetch_fundamentals(h.ticker.replace(".NS", ""))
            if not data:
                st.caption("No fundamental data available for this ticker.")
                continue
            # Two columns of metric/value pairs
            cols = st.columns(2)
            items = list(_FUNDAMENTAL_FIELDS)
            for i, (key, label, unit) in enumerate(items):
                val = _format(data.get(key), unit)
                with cols[i % 2]:
                    st.metric(label, val)