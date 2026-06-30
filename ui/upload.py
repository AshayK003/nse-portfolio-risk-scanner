"""
CSV upload, manual stock entry, portfolio data editor, and saved-portfolio management.
Thin Streamlit presentation — no business logic.
Uses Lucide SVG icons instead of emojis (markdown-only, not in button/expander labels).
"""

from __future__ import annotations

import streamlit as st

from engine import Holding, Portfolio
from engine.portfolio import parse_portfolio_csv
from ui.icons import (
    CHECK_CIRCLE,
    FOLDER_OPEN,
    PLUS,
    UPLOAD,
    X_CIRCLE,
    icon_html,
)


def render_sidebar():
    """Render the sidebar with saved portfolio management."""
    st.sidebar.markdown(
        f'<div class="section-header">{icon_html(FOLDER_OPEN)} Saved Portfolios</div>',
        unsafe_allow_html=True,
    )

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
                st.sidebar.markdown(
                    f"{icon_html(CHECK_CIRCLE)} **Loaded:** {sp.name}",
                    unsafe_allow_html=True,
                )
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
                st.sidebar.markdown(
                    f"{icon_html(CHECK_CIRCLE)} Deleted",
                    unsafe_allow_html=True,
                )
                st.rerun()
        else:
            st.sidebar.info("No saved portfolios yet.")
    except ImportError:
        st.sidebar.caption("Storage module not available")
    except Exception as e:
        st.sidebar.caption(f"DB error: {e}")


def render_manual_entry() -> list[Holding]:
    """Render manual stock entry form. Returns list of holdings entered so far."""
    st.markdown(
        f'<div class="section-header">{icon_html(PLUS)} Add Stocks Manually</div>',
        unsafe_allow_html=True,
    )

    # Initialize manual holdings in session state
    if "manual_holdings" not in st.session_state:
        st.session_state.manual_holdings = []

    # Form
    with st.form("manual_entry_form", clear_on_submit=True):
        cols = st.columns([2, 1, 1, 1])
        with cols[0]:
            ticker = (
                st.text_input(
                    "Ticker",
                    placeholder="e.g. RELIANCE",
                    label_visibility="collapsed",
                )
                .strip()
                .upper()
            )
        with cols[1]:
            qty = st.number_input("Qty", min_value=1, step=1, label_visibility="collapsed")
        with cols[2]:
            price = st.number_input(
                "Avg Price (₹)",
                min_value=0.01,
                step=1.0,
                format="%.2f",
                label_visibility="collapsed",
            )
        with cols[3]:
            st.write("")
            submitted = st.form_submit_button("Add Stock", use_container_width=True)

        if submitted:
            if not ticker:
                st.warning("Enter a ticker symbol")
            else:
                clean_ticker = ticker.replace(".NS", "")
                if not clean_ticker.endswith(".NS"):
                    clean_ticker = f"{clean_ticker}.NS"
                new_holding = Holding(
                    ticker=clean_ticker,
                    name=ticker.replace(".NS", ""),
                    quantity=int(qty),
                    avg_price=round(price, 2),
                )
                st.session_state.manual_holdings.append(new_holding)

    # Show entered stocks with remove button
    manual = st.session_state.manual_holdings
    if manual:
        st.markdown(
            f'<div style="margin: 0.5rem 0 0.3rem; color: #94a3b8; font-size: 0.85rem;">'
            f"{len(manual)} stock(s) added</div>",
            unsafe_allow_html=True,
        )
        for i, h in enumerate(manual):
            col_a, col_b, col_c, col_d = st.columns([2, 1, 1, 1])
            with col_a:
                st.markdown(f"**{h.ticker.replace('.NS', '')}**")
            with col_b:
                st.text(f"{h.quantity} shares")
            with col_c:
                st.text(f"₹{h.avg_price:,.2f}")
            with col_d:
                if st.button("✕", key=f"remove_manual_{i}"):
                    st.session_state.manual_holdings.pop(i)
                    st.rerun()

    return manual


def render_upload_tab() -> Portfolio | None:
    """Render the CSV upload + manual entry section. Returns a Portfolio if loaded."""
    # ── CSV Upload Section ──
    st.markdown(
        f'<div class="section-header">{icon_html(UPLOAD)} Upload Portfolio CSV</div>',
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Upload portfolio CSV",
        type="csv",
        help="Upload a CSV exported from Zerodha, Groww, or any broker. "
        "Expected columns: ticker/symbol, quantity/qty, avg_price/price.",
    )

    csv_portfolio = None
    if uploaded is not None:
        try:
            csv_bytes = uploaded.getvalue()
            csv_portfolio = parse_portfolio_csv(csv_bytes, portfolio_name=uploaded.name)
            st.markdown(
                f"{icon_html(CHECK_CIRCLE)} **Loaded** {csv_portfolio.holding_count} "
                f"holdings from {uploaded.name}",
                unsafe_allow_html=True,
            )
        except ValueError as e:
            st.markdown(
                f"{icon_html(X_CIRCLE)} **Could not parse CSV:** {e}",
                unsafe_allow_html=True,
            )

    # ── Manual Entry Section ──
    st.markdown("<hr style='border-color: #2a2d3e; margin: 1.5rem 0;'>", unsafe_allow_html=True)
    manual_holdings = render_manual_entry()

    # ── Combine sources ──
    all_holdings = []
    if csv_portfolio:
        all_holdings.extend(csv_portfolio.holdings)
    if manual_holdings:
        all_holdings.extend(manual_holdings)

    if not all_holdings:
        if st.session_state.get("portfolio") is not None:
            return st.session_state.portfolio

        st.markdown(
            f"{icon_html(UPLOAD)} **Upload a CSV** or **add stocks manually** "
            f"above to analyze your portfolio.",
            unsafe_allow_html=True,
        )
        return None

    portfolio = csv_portfolio or Portfolio(name="My Portfolio")
    if csv_portfolio and manual_holdings:
        seen = {h.ticker for h in csv_portfolio.holdings}
        for h in manual_holdings:
            if h.ticker not in seen:
                portfolio.holdings.append(h)
                seen.add(h.ticker)
        portfolio.name = f"{csv_portfolio.name} + Manual"

    return portfolio


def render_data_editor(portfolio: Portfolio) -> Portfolio:
    """Show an editable data editor for the portfolio holdings."""
    with st.expander("✎ Edit Holdings", expanded=False):
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
                "Avg Price": st.column_config.NumberColumn("Avg Price", min_value=0.01, format="₹%.2f"),
            },
        )

        if st.button("Update from Editor", use_container_width=True):
            new_holdings = []
            for _, row in df.iterrows():
                new_holdings.append(
                    Holding(
                        ticker=(row["Ticker"] + ".NS")
                        if not row["Ticker"].endswith(".NS")
                        else row["Ticker"],
                        name=row.get("Name", row["Ticker"]),
                        quantity=int(row["Quantity"]),
                        avg_price=float(row["Avg Price"]),
                    )
                )
            portfolio.holdings = new_holdings
            if "manual_holdings" in st.session_state:
                st.session_state.manual_holdings = []
            st.markdown(
                f"{icon_html(CHECK_CIRCLE)} Updated to {len(new_holdings)} holdings",
                unsafe_allow_html=True,
            )
            st.session_state.portfolio = portfolio
            st.rerun()

    return portfolio


def render_save_button(portfolio: Portfolio):
    """Show save portfolio button."""
    with st.expander("💾 Save Portfolio", expanded=False):
        save_name = st.text_input("Portfolio name", value=portfolio.name or "My Portfolio")
        if st.button("Save to Database", use_container_width=True):
            try:
                from storage.db import save_portfolio
                from storage.models import portfolio_to_saved

                saved = portfolio_to_saved(portfolio, name=save_name)
                p_id = save_portfolio(saved)
                st.markdown(
                    f"{icon_html(CHECK_CIRCLE)} Saved as **{save_name}** (ID: {p_id})",
                    unsafe_allow_html=True,
                )
            except ImportError:
                st.error("Storage module not available")
            except Exception as e:
                st.error(f"Save failed: {e}")
