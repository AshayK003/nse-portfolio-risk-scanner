"""
CSV upload, portfolio data editor, and saved-portfolio management.
Thin Streamlit presentation — no business logic.
"""
from __future__ import annotations
import streamlit as st
from engine import Holding, Portfolio
from engine.portfolio import parse_portfolio_csv


def render_sidebar():
    """Render the sidebar with saved portfolio management."""
    st.sidebar.header("📂 Saved Portfolios")

    try:
        from storage.db import list_saved_portfolios, delete_portfolio
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
            if delete_name != "— Select —" and st.sidebar.button("🗑 Delete", use_container_width=True):
                p_id = options[delete_name]
                delete_portfolio(p_id)
                st.sidebar.success("Deleted")
                st.rerun()
        else:
            st.sidebar.info("No saved portfolios yet.")
    except ImportError:
        st.sidebar.caption("Storage module not available")
    except Exception as e:
        st.sidebar.caption(f"DB error: {e}")


def render_upload_tab() -> Portfolio | None:
    """Render the CSV upload section. Returns a Portfolio if loaded, None otherwise."""
    uploaded = st.file_uploader(
        "Upload portfolio CSV",
        type="csv",
        help="Upload a CSV exported from Zerodha, Groww, or any broker. "
             "Expected columns: ticker/symbol, quantity/qty, avg_price/price.",
    )

    if uploaded is None:
        # Check if we have a portfolio in session
        if st.session_state.get("portfolio") is not None:
            return st.session_state.portfolio

        st.info("""
        **Upload a CSV** to analyze your portfolio risk metrics.

        Your CSV should have columns for: ticker/symbol, quantity, avg price.
        Supports Zerodha, Groww, and Upstox export formats.
        """)
        return None

    try:
        csv_bytes = uploaded.getvalue()
        portfolio = parse_portfolio_csv(csv_bytes, portfolio_name=uploaded.name)
        st.success(f"✅ Loaded {portfolio.holding_count} holdings from {uploaded.name}")
        return portfolio
    except ValueError as e:
        st.error(f"❌ Could not parse CSV: {e}")
        return None


def render_data_editor(portfolio: Portfolio) -> Portfolio:
    """Show an editable data editor for the portfolio holdings."""
    with st.expander("✏️ Edit Holdings", expanded=False):
        data = []
        for h in portfolio.holdings:
            data.append({
                "Ticker": h.ticker.replace(".NS", ""),
                "Name": h.name,
                "Quantity": h.quantity,
                "Avg Price": h.avg_price,
            })

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

        if st.button("🔄 Update from Editor", use_container_width=True):
            new_holdings = []
            for _, row in df.iterrows():
                new_holdings.append(Holding(
                    ticker=(row["Ticker"] + ".NS") if not row["Ticker"].endswith(".NS") else row["Ticker"],
                    name=row.get("Name", row["Ticker"]),
                    quantity=int(row["Quantity"]),
                    avg_price=float(row["Avg Price"]),
                ))
            portfolio.holdings = new_holdings
            st.success(f"Updated to {len(new_holdings)} holdings")
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
                st.success(f"Saved as '{save_name}' (ID: {p_id})")
            except ImportError:
                st.error("Storage module not available")
            except Exception as e:
                st.error(f"Save failed: {e}")
