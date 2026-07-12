"""
CSV upload, manual stock entry, portfolio data editor, and saved-portfolio management.
Thin Streamlit presentation — no business logic.
Uses Lucide SVG icons instead of emojis (markdown-only, not in button/expander labels).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from engine import Holding, Portfolio
from engine.__init__ import RISK_PROFILES
from engine.portfolio import parse_portfolio_csv
from ui.icons import (
    UPLOAD,
    icon_html,
)


def render_sidebar():
    """Render the sidebar with saved portfolio management."""
    st.sidebar.subheader("Saved Portfolios")

    try:
        from storage.db import delete_portfolio, list_saved_portfolios
        from storage.models import saved_to_portfolio

        saved = list_saved_portfolios()
        if saved:
            options = {f"{p.name} (Rs {p.total_invested:,.0f})": p.id for p in saved}
            selected = st.sidebar.selectbox(
                "Load a saved portfolio",
                options=["— Select —"] + list(options.keys()),
            )
            if selected != "— Select —":
                p_id = options[selected]
                sp = [p for p in saved if p.id == p_id][0]
                loaded = saved_to_portfolio(sp)
                st.sidebar.success(f"Loaded: {sp.name}")
                st.session_state.portfolio = loaded
                st.session_state.selected_portfolio_id = sp.id
                st.rerun()

            # Delete
            delete_name = st.sidebar.selectbox(
                "Delete portfolio",
                options=["— Select —"] + list(options.keys()),
                key="delete_portfolio",
            )
            if delete_name != "— Select —" and st.sidebar.button("Delete", use_container_width=True):
                p_id = options[delete_name]
                delete_portfolio(p_id)
                st.sidebar.success("Portfolio deleted.")
                st.rerun()
        else:
            st.sidebar.info("No saved portfolios yet.")
    except ImportError:
        st.sidebar.caption("Storage module not available")
    except Exception as e:
        st.sidebar.error(f"Could not load portfolios: {e}")

    # ── Risk-free Rate ──
    st.sidebar.divider()
    st.sidebar.subheader("Assumptions")
    stored_rf = st.session_state.get("risk_free_rate", 6.5)
    st.session_state.risk_free_rate = st.sidebar.slider(
        "Risk-free Rate (%)",
        min_value=3.0, max_value=10.0, value=stored_rf, step=0.25,
        help="Indian risk-free rate (10-year bond yield ~6.5%). Affects Sharpe, Sortino, and alpha.",
    )

    # ── Risk Profile Selector ──
    st.sidebar.divider()
    st.sidebar.subheader("Risk Profile")
    profile_options = {p.name: p.name.lower() for p in RISK_PROFILES.values()}
    if "risk_profile" not in st.session_state:
        st.session_state.risk_profile = "moderate"
    current_idx = list(profile_options.values()).index(st.session_state.risk_profile)
    selected_label = st.sidebar.selectbox(
        "Select your risk appetite",
        options=list(profile_options.keys()),
        index=current_idx,
        key="risk_profile_selector",
    )
    new_key = profile_options[selected_label]
    if new_key != st.session_state.risk_profile:
        st.session_state.risk_profile = new_key
        st.rerun()
    profile = RISK_PROFILES[st.session_state.risk_profile]
    st.sidebar.caption(
        f"**{profile.name}** → {profile.method.replace('_', ' ').title()}, "
        f"Max {profile.max_single_weight * 100:.0f}% per stock"
    )


def render_manual_entry() -> list[Holding]:
    """Render manual stock entry form. Returns list of holdings entered so far."""
    st.subheader("Add Stocks Manually")

    # Initialize manual holdings in session state
    if "manual_holdings" not in st.session_state:
        st.session_state.manual_holdings = []

    # Form
    with st.form("manual_entry_form", clear_on_submit=True):
        cols = st.columns([2, 1, 1])
        with cols[0]:
            ticker = (
                st.text_input(
                    "Ticker",
                    placeholder="e.g. RELIANCE",
                )
                .strip()
                .upper()
            )
        with cols[1]:
            qty = st.number_input("Quantity", min_value=1, step=1, placeholder="e.g. 10")
        with cols[2]:
            price = st.number_input(
                "Avg Price (Rs)",
                min_value=0.01,
                step=1.0,
                format="%.2f",
                placeholder="e.g. 2500.00",
            )
        submitted = st.form_submit_button("Add Stock", use_container_width=True)

        if submitted:
            if not ticker:
                st.warning("Enter a ticker symbol.")
            else:
                from engine.portfolio import normalize_ticker

                normalized = normalize_ticker(ticker)
                new_holding = Holding(
                    ticker=normalized,
                    name=ticker.strip().upper().replace(".NS", ""),
                    quantity=int(qty),
                    avg_price=round(price, 2),
                )
                st.session_state.manual_holdings.append(new_holding)

    # Show entered stocks with remove button
    manual = st.session_state.manual_holdings
    if manual:
        st.caption(f"{len(manual)} stock(s) added")
        for i, h in enumerate(manual):
            col_a, col_b, col_c = st.columns([2, 1, 1])
            with col_a:
                st.markdown(f"**{h.ticker.replace('.NS', '')}**")
            with col_b:
                st.text(f"{h.quantity} shares")
            with col_c:
                if st.button("Remove", key=f"remove_manual_{i}", help=f"Remove {h.ticker}", use_container_width=True):
                    st.session_state.manual_holdings.pop(i)
                    st.rerun()

    return manual


def render_upload_tab() -> Portfolio | None:
    """Render the CSV upload + manual entry section. Returns a Portfolio if loaded."""
    # ── Load from shared link (query params) ──
    query_params = st.query_params
    if "p" in query_params and st.session_state.get("portfolio") is None:
        try:
            import base64
            import json

            decoded = base64.b64decode(query_params["p"]).decode()
            data = json.loads(decoded)
            
            # Validate required fields
            if not isinstance(data, dict) or "holdings" not in data:
                raise ValueError("Invalid portfolio data: missing 'holdings'")
            if not isinstance(data["holdings"], list):
                raise ValueError("Invalid portfolio data: 'holdings' must be a list")
            
            holdings = []
            for item in data["holdings"]:
                # Validate required fields
                if not isinstance(item, dict) or "t" not in item or "q" not in item or "p" not in item:
                    raise ValueError("Invalid holding: missing required fields (t, q, p)")
                from engine.portfolio import normalize_ticker
                holdings.append(Holding(
                    ticker=normalize_ticker(item["t"]),
                    name=item.get("n", item["t"]),
                    quantity=int(item["q"]),
                    avg_price=float(item["p"]),
                ))
            portfolio = Portfolio(holdings=holdings, name="Shared Portfolio")
            st.success("Loaded portfolio from shared link.")
            return portfolio
        except Exception:
            st.warning("Could not decode shared portfolio link. The link may be invalid or expired.")

    # ── CSV Upload Section ──
    st.subheader("Upload Portfolio CSV")

    uploaded = st.file_uploader(
        "Upload portfolio CSV",
        type="csv",
        help="Upload a CSV exported from Zerodha, Groww, or any broker. "
        "Expected columns: ticker/symbol, quantity/qty, avg_price/price. "
        "Max file size: 10MB.",
    )

    csv_portfolio = None
    if uploaded is not None:
        csv_bytes = uploaded.getvalue()
        if len(csv_bytes) > 10 * 1024 * 1024:
            st.error("File too large (max 10MB). Please upload a smaller CSV.")
            st.stop()

        try:
            csv_portfolio = parse_portfolio_csv(csv_bytes, portfolio_name=uploaded.name)
            st.success(f"Loaded {csv_portfolio.holding_count} holdings from {uploaded.name}.")
        except ValueError as e:
            st.error(f"Could not parse CSV: {e}")

    # ── Manual Entry Section ──
    st.divider()
    manual_holdings = render_manual_entry()

    # ── Check for any data before proceeding ──
    if csv_portfolio is None and not manual_holdings:
        if st.session_state.get("portfolio") is not None:
            return st.session_state.portfolio

        # Empty state
        st.markdown(
            f"""<div class="empty-state">
                <div class="empty-state-icon">{icon_html(UPLOAD, size=48)}</div>
                <div class="empty-state-title">Get started</div>
                <div class="empty-state-desc">
                    Upload a CSV exported from your broker, or add stocks manually above.
                    You'll see risk metrics, sector breakdown, and benchmark comparison.
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

        # Quick-launch sample portfolio (auto-analyzed on click)
        if st.button("Try Sample Portfolio", use_container_width=True, type="primary"):
            portfolio = Portfolio(
                holdings=[
                    Holding(ticker="RELIANCE.NS", name="RELIANCE", quantity=10, avg_price=1100.00),
                    Holding(ticker="TCS.NS", name="TCS", quantity=5, avg_price=1700.00),
                    Holding(ticker="INFY.NS", name="INFY", quantity=20, avg_price=850.00),
                    Holding(ticker="ITC.NS", name="ITC", quantity=50, avg_price=240.00),
                    Holding(ticker="ICICIBANK.NS", name="ICICIBANK", quantity=30, avg_price=1150.00),
                    Holding(ticker="BANKBEES.NS", name="BANKBEES", quantity=50, avg_price=500.00),
                    Holding(ticker="CPSEETF.NS", name="CPSEETF", quantity=100, avg_price=80.00),
                ],
                name="Sample Portfolio",
            )
            st.session_state.portfolio = portfolio
            st.rerun()

        return None

    portfolio = csv_portfolio or Portfolio(name="My Portfolio")
    if csv_portfolio and manual_holdings:
        seen = {h.ticker for h in csv_portfolio.holdings}
        for h in manual_holdings:
            if h.ticker not in seen:
                portfolio.holdings.append(h)
                seen.add(h.ticker)
        portfolio.name = f"{csv_portfolio.name} + Manual"
    elif manual_holdings:
        portfolio.holdings = manual_holdings

    return portfolio


def render_data_editor(portfolio: Portfolio) -> Portfolio:
    """Show an editable data editor for the portfolio holdings."""
    with st.expander("Edit Holdings", expanded=False):
        data = []
        for h in portfolio.holdings:
            data.append(
                {
                    "Ticker": h.ticker.replace(".NS", ""),
                    "Name": h.name,
                    "Quantity": h.quantity,
                    "Avg Price": h.avg_price,
                }
            )

        df = st.data_editor(
            data,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "Ticker": st.column_config.TextColumn("Ticker", width="small"),
                "Name": st.column_config.TextColumn("Name", width="medium"),
                "Quantity": st.column_config.NumberColumn("Quantity", min_value=1, step=1),
                "Avg Price": st.column_config.NumberColumn("Avg Price", min_value=0.01, format="Rs %.2f"),
            },
        )

        if st.button("Update from Editor", use_container_width=True):
            if not isinstance(df, pd.DataFrame) or df.empty:
                st.warning("Add rows in the data editor, then click Update.")
            else:
                new_holdings = []
                for _, row in df.iterrows():
                    ticker_val = row.get("Ticker", "")
                    if not ticker_val or pd.isna(ticker_val):
                        continue
                    ticker_str = str(ticker_val).strip()
                    if not ticker_str:
                        continue
                    new_holdings.append(
                        Holding(
                            ticker=(ticker_str + ".NS")
                            if not ticker_str.endswith(".NS")
                            else ticker_str,
                            name=row.get("Name", ticker_str),
                            quantity=int(row["Quantity"]),
                            avg_price=float(row["Avg Price"]),
                        )
                    )
                portfolio.holdings = new_holdings
                if "manual_holdings" in st.session_state:
                    st.session_state.manual_holdings = []
                st.success(f"Updated to {len(new_holdings)} holdings.")
                st.session_state.portfolio = portfolio
                st.rerun()

    return portfolio


def render_save_button(portfolio: Portfolio):
    """Show save portfolio button."""
    with st.expander("Save Portfolio", expanded=False):
        save_name = st.text_input("Portfolio name", value=portfolio.name or "My Portfolio")
        if st.button("Save to Database", use_container_width=True):
            try:
                from storage.db import save_portfolio
                from storage.models import portfolio_to_saved

                saved = portfolio_to_saved(portfolio, name=save_name)
                p_id = save_portfolio(saved)
                st.success(f"Saved as **{save_name}** (ID: {p_id}).")
            except ImportError:
                st.error("Storage module is not available.")
            except Exception as e:
                st.error(f"Could not save portfolio: {e}")
