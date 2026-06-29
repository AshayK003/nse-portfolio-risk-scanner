"""
Report export — CSV download and PDF report generation.
Uses Lucide SVG icons instead of emojis.
"""
from __future__ import annotations
import io
import streamlit as st
import pandas as pd
from engine import Portfolio, RiskMetrics
from ui.icons import DOWNLOAD, FILE_TEXT, icon_text


def render_export_section(
    portfolio: Portfolio,
    risk: RiskMetrics | None = None,
    sector_data: dict | None = None,
) -> None:
    """Display export buttons for the analysis results."""
    st.markdown(
        f'<div class="section-header">{icon_text(DOWNLOAD, "Export Report")}</div>',
        unsafe_allow_html=True,
    )

    # Build data rows
    rows = []
    for h in portfolio.holdings:
        rows.append({
            "Ticker": h.ticker.replace(".NS", ""),
            "Name": h.name,
            "Quantity": h.quantity,
            "Avg Price": h.avg_price,
            "Current Price": h.current_price,
            "Invested": h.invested_value,
            "Current Value": h.current_value,
            "P&L": h.pnl,
            "P&L %": h.pnl_pct,
            "Sector": h.sector,
        })

    df = pd.DataFrame(rows)

    # ── CSV Download ──
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=f"{icon_text(DOWNLOAD, 'Download CSV Report')}",
        data=csv,
        file_name=f"portfolio_report_{portfolio.name.replace(' ', '_')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # ── PDF Download ──
    try:
        pdf_bytes = _generate_pdf_report(portfolio, risk, sector_data, df)
        st.download_button(
            label=f"{icon_text(FILE_TEXT, 'Download PDF Report')}",
            data=pdf_bytes,
            file_name=f"portfolio_report_{portfolio.name.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except ImportError:
        st.caption("💡 PDF export requires fpdf2: `pip install fpdf2`")
    except Exception as e:
        st.caption(f"⚠️ PDF generation failed: {e}")

    st.caption("Reports include position-level data for further analysis in Excel/Sheets.")


def _generate_pdf_report(
    portfolio: Portfolio,
    risk: RiskMetrics | None,
    sector_data: dict | None,
    df: pd.DataFrame,
) -> bytes:
    """Generate a PDF report using fpdf2."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "NSE Portfolio Risk Report", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Portfolio name and date
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Portfolio: {portfolio.name}", new_x="LMARGIN", new_y="NEXT")
    from datetime import datetime
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ── Summary Section ──
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Portfolio Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Holdings: {portfolio.holding_count}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Total Invested: Rs {portfolio.total_invested:,.0f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Current Value: Rs {portfolio.total_current:,.0f}", new_x="LMARGIN", new_y="NEXT")
    pnl_color = (0, 128, 0) if portfolio.total_pnl >= 0 else (200, 0, 0)
    pdf.set_text_color(*pnl_color)
    pnl_sign = "+" if portfolio.total_pnl >= 0 else ""
    pdf.cell(0, 6, f"P&L: Rs {pnl_sign}{portfolio.total_pnl:+,.0f} ({pnl_sign}{portfolio.total_pnl_pct:+.2f}%)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # ── Risk Metrics Section ──
    if risk:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Risk Metrics", new_x="LMARGIN", new_y="NEXT")

        risk_items = [
            ("Annual Volatility", f"{risk.volatility_annual:.1f}%"),
            ("Value at Risk (95%)", f"{risk.var_95:.2f}%"),
            ("Conditional VaR (95%)", f"{risk.cvar_95:.2f}%"),
            ("Max Drawdown", f"{risk.max_drawdown:.1f}%"),
            ("Sharpe Ratio", f"{risk.sharpe:.2f}"),
            ("Sortino Ratio", f"{risk.sortino:.2f}"),
            ("CAGR", f"{risk.cagr:.1f}%"),
            ("Beta (vs Nifty 50)", f"{risk.beta:.2f}"),
        ]

        pdf.set_font("Helvetica", "", 10)
        for i in range(0, len(risk_items), 2):
            col1, val1 = risk_items[i]
            if i + 1 < len(risk_items):
                col2, val2 = risk_items[i + 1]
                pdf.cell(75, 6, f"{col1}: {val1}", border=0)
                pdf.cell(0, 6, f"{col2}: {val2}", new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.cell(0, 6, f"{col1}: {val1}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # ── Holdings Table ──
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Holdings Breakdown", new_x="LMARGIN", new_y="NEXT")

    cols = ["Ticker", "Qty", "Avg Price", "Current", "P&L %"]
    col_widths = [30, 20, 35, 35, 30]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 235, 240)
    for col_name, w in zip(cols, col_widths):
        pdf.cell(w, 7, col_name, border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for _, row in df.head(30).iterrows():
        pdf.cell(col_widths[0], 6, str(row.get("Ticker", "")), border=1)
        pdf.cell(col_widths[1], 6, str(int(row.get("Quantity", 0))), border=1)
        pdf.cell(col_widths[2], 6, f"Rs {row.get('Avg Price', 0):,.2f}", border=1)
        pdf.cell(col_widths[3], 6, f"Rs {row.get('Current Price', 0):,.2f}", border=1)
        pnl = row.get("P&L %", 0)
        if pnl >= 0:
            pdf.set_text_color(0, 128, 0)
        else:
            pdf.set_text_color(200, 0, 0)
        pdf.cell(col_widths[4], 6, f"{pnl:+.1f}%", border=1)
        pdf.set_text_color(0, 0, 0)
        pdf.ln()

    if len(df) > 30:
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 6, f"... and {len(df) - 30} more holdings (see CSV for full data)", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 5, "Generated by NSE Portfolio Risk Scanner", align="C", new_x="LMARGIN", new_y="NEXT")

    return pdf.output()
