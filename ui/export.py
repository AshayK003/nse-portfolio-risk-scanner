"""
Report export — CSV download and PDF report generation.
Uses Lucide SVG icons instead of emojis.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from engine import Portfolio, RiskMetrics
from ui.icons import DOWNLOAD, icon_text


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
        rows.append(
            {
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
            }
        )

    df = pd.DataFrame(rows)

    # ── CSV Download ──
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download CSV Report",
        data=csv,
        file_name=f"portfolio_report_{portfolio.name.replace(' ', '_')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # ── PDF Download ──
    try:
        pdf_bytes = _generate_pdf_report(portfolio, risk, sector_data, df)
        st.download_button(
            label="Download PDF Report",
            data=pdf_bytes,
            file_name=f"portfolio_report_{portfolio.name.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except ImportError:
        st.caption("PDF export requires fpdf2: pip install fpdf2")
    except Exception as e:
        st.error(f"PDF generation failed: {e}")

    st.caption("Reports include position-level data for further analysis in Excel/Sheets.")


PDF_COLOR_PRIMARY = (25, 60, 120)  # dark blue
PDF_COLOR_ACCENT = (240, 245, 250)  # light blue-gray
PDF_COLOR_GREEN = (220, 245, 220)  # light green
PDF_COLOR_RED = (250, 220, 220)  # light red
PDF_COLOR_WHITE = (255, 255, 255)


def _section_header(pdf, title: str) -> None:
    """Draw a section header with colored background bar."""
    pdf.set_fill_color(*PDF_COLOR_PRIMARY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)


def _kpi_card(pdf, label: str, value: str, x: float, y: float, w: float, color: tuple | None = None) -> float:
    """Draw a KPI card at (x, y) and return the bottom y."""
    card_h = 22
    bg = color or PDF_COLOR_ACCENT
    pdf.set_fill_color(*bg)
    pdf.rect(x, y, w, card_h, style="F")
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(80, 80, 80)
    pdf.set_xy(x + 3, y + 2)
    pdf.cell(w - 6, 5, label)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*PDF_COLOR_PRIMARY)
    pdf.set_xy(x + 3, y + 9)
    pdf.cell(w - 6, 8, value)
    pdf.set_text_color(0, 0, 0)
    return y + card_h + 4


def _data_table(pdf, headers: list[str], widths: list[int], rows: list[list[str]]) -> None:
    """Draw a table with alternating row colors."""
    pdf.set_fill_color(*PDF_COLOR_PRIMARY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    for h, w in zip(headers, widths, strict=False):
        pdf.cell(w, 7, f" {h}", border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 8)
    for i, row in enumerate(rows):
        if i % 2 == 0:
            pdf.set_fill_color(*PDF_COLOR_ACCENT)
        else:
            pdf.set_fill_color(*PDF_COLOR_WHITE)
        for val, w in zip(row, widths, strict=False):
            pdf.cell(w, 6, f" {val}", border=1, fill=True)
        pdf.ln()


try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _MPL_AVAILABLE = True
except ImportError:
    _MPL_AVAILABLE = False


def _chart_bytes(fig) -> bytes:
    """Render a matplotlib figure to PNG bytes."""
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _sector_pie_chart(sector_data: dict, page_w: float) -> bytes | None:
    """Matplotlib pie chart for sector allocation."""
    if not _MPL_AVAILABLE:
        return None
    labels = list(sector_data.keys())
    sizes = list(sector_data.values())
    colors = plt.cm.Set2.colors[: len(labels)]
    fig, ax = plt.subplots(figsize=(page_w / 25.4, 2.5))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=None, autopct="%1.0f%%", startangle=90,
        colors=colors, textprops={"fontsize": 7},
    )
    ax.legend(
        wedges, [f"{l} ({s:.0f}%)" for l, s in zip(labels, sizes)],
        loc="center left", bbox_to_anchor=(1, 0.5), fontsize=6,
    )
    ax.set_title("Sector Allocation", fontsize=9, fontweight="bold")
    return _chart_bytes(fig)


def _pnl_bar_chart(df: pd.DataFrame, page_w: float) -> bytes | None:
    """Matplotlib horizontal bar chart of P&L per holding."""
    if not _MPL_AVAILABLE:
        return None
    top = df.iloc[df["P&L %"].abs().argsort()[::-1][:15]] if "P&L %" in df.columns else df.head(15)
    tickers = [t.replace(".NS", "") for t in top["Ticker"]]
    pnl_values = top["P&L %"].values
    colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in pnl_values]
    fig, ax = plt.subplots(figsize=(page_w / 25.4, max(2, len(tickers) * 0.35)))
    bars = ax.barh(range(len(tickers)), pnl_values, color=colors, height=0.6)
    ax.set_yticks(range(len(tickers)))
    ax.set_yticklabels(tickers, fontsize=7)
    ax.axvline(0, color="black", linewidth=0.5)
    ax.set_xlabel("P&L %", fontsize=7)
    ax.tick_params(axis="x", labelsize=6)
    for bar, val in zip(bars, pnl_values, strict=False):
        px = bar.get_width()
        ax.text(px + (0.3 if px >= 0 else -0.3), bar.get_y() + bar.get_height() / 2,
                f"{val:+.1f}%", va="center", fontsize=6,
                ha="left" if px >= 0 else "right")
    ax.margins(x=0.15)
    return _chart_bytes(fig)


def _generate_pdf_report(
    portfolio: Portfolio,
    risk: RiskMetrics | None,
    sector_data: dict | None,
    df: pd.DataFrame,
) -> bytes:
    """Generate a professional PDF report using fpdf2."""
    from datetime import datetime

    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    page_w = pdf.w - pdf.l_margin - pdf.r_margin  # usable width

    # ── Top Header Bar ──
    pdf.set_fill_color(*PDF_COLOR_PRIMARY)
    pdf.rect(0, 0, pdf.w, 14, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(pdf.l_margin, 3)
    pdf.cell(0, 8, "NSE Portfolio Risk Report")
    pdf.set_y(20)
    pdf.set_text_color(0, 0, 0)

    # ── Portfolio info line ──
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"{portfolio.name}  |  {datetime.now().strftime('%d %b %Y, %I:%M %p')}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # ── KPI Cards ──
    card_w = (page_w - 8) / 4
    y0 = pdf.get_y()
    pnl_color = PDF_COLOR_GREEN if portfolio.total_pnl >= 0 else PDF_COLOR_RED
    pnl_sign = "+" if portfolio.total_pnl >= 0 else ""
    pnl_val = f"Rs {pnl_sign}{portfolio.total_pnl:+,.0f}"

    _kpi_card(pdf, "Holdings", str(portfolio.holding_count), pdf.l_margin, y0, card_w)
    _kpi_card(pdf, "Total Invested", f"Rs {portfolio.total_invested:,.0f}", pdf.l_margin + card_w + 2, y0, card_w)
    _kpi_card(pdf, "Current Value", f"Rs {portfolio.total_current:,.0f}", pdf.l_margin + 2 * (card_w + 2), y0, card_w)
    _kpi_card(pdf, "P&L", pnl_val, pdf.l_margin + 3 * (card_w + 2), y0, card_w, color=pnl_color)
    pdf.set_y(y0 + 26)

    # ── P&L percentage bar ──
    if portfolio.total_invested > 0:
        pdf.ln(2)
        pnl_pct = portfolio.total_pnl_pct
        bar_color = PDF_COLOR_GREEN if pnl_pct >= 0 else PDF_COLOR_RED
        pdf.set_fill_color(*bar_color)
        bar_w = max(min(page_w * abs(pnl_pct) / 50, page_w), 8)
        pdf.cell(bar_w, 5, f"  {pnl_pct:+.2f}%", fill=True)
        pdf.ln(8)

    # ── Risk Metrics Section ──
    if risk:
        _section_header(pdf, "Risk Metrics")

        metrics = [
            ("Annual Volatility", f"{risk.volatility_annual:.1f}%"),
            ("VaR (95%)", f"{risk.var_95:.2f}%"),
            ("CVaR (95%)", f"{risk.cvar_95:.2f}%"),
            ("Max Drawdown", f"{risk.max_drawdown:.1f}%"),
            ("Sharpe Ratio", f"{risk.sharpe:.2f}"),
            ("Sortino Ratio", f"{risk.sortino:.2f}"),
            ("CAGR", f"{risk.cagr:.1f}%"),
            ("Beta (vs Nifty 50)", f"{risk.beta:.2f}"),
        ]

        col_w = page_w / 2
        y_start = pdf.get_y()
        for i, (label, val) in enumerate(metrics):
            col = i % 2
            row = i // 2
            x = pdf.l_margin + col * col_w
            y = y_start + row * 7
            pdf.set_fill_color(*PDF_COLOR_ACCENT)
            pdf.rect(x, y, col_w - 2, 6, style="F")
            pdf.set_font("Helvetica", "", 8)
            pdf.set_xy(x + 2, y + 0.5)
            pdf.cell(col_w - 4, 6, label)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_xy(x + col_w / 2, y + 0.5)
            pdf.cell(col_w / 2 - 4, 6, val)
        pdf.set_y(y_start + (len(metrics) // 2 + len(metrics) % 2) * 7 + 4)

    # ── Sector Allocation Section ──
    if sector_data:
        pdf.ln(2)
        _section_header(pdf, "Sector Allocation")
        chart = _sector_pie_chart(sector_data, page_w)
        if chart:
            img_w = page_w * 0.6
            pdf.image(chart, x=pdf.l_margin + (page_w - img_w) / 2, w=img_w)
            pdf.ln(3)
        else:
            sorted_sectors = sorted(sector_data.items(), key=lambda x: x[1], reverse=True)
            sector_rows = [[s, f"{pct:.1f}%", "=" * max(int(pct / 5), 1)] for s, pct in sorted_sectors]
            _data_table(pdf, ["Sector", "Weight", "Bar"], [60, 30, page_w - 90], sector_rows)
        pdf.ln(3)

    # ── Holdings P&L Chart ──
    pnl_chart = _pnl_bar_chart(df, page_w)
    if pnl_chart:
        img_w = page_w
        pdf.image(pnl_chart, x=pdf.l_margin, w=img_w)
        pdf.ln(2)

    # ── Holdings Section ──
    pdf.ln(2)
    _section_header(pdf, "Holdings Breakdown")

    cols = ["Ticker", "Name", "Qty", "Avg Price", "Current", "P&L %", "Sector"]
    col_widths = [24, 44, 14, 24, 24, 18, 22]
    # adjust to fit page_w
    col_widths = [int(w * page_w / sum(col_widths)) for w in col_widths]
    pdf.set_fill_color(*PDF_COLOR_PRIMARY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 7)
    for c, w in zip(cols, col_widths, strict=False):
        pdf.cell(w, 7, f" {c}", border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 7)

    for i, (_, row) in enumerate(df.head(30).iterrows()):
        if i % 2 == 0:
            pdf.set_fill_color(*PDF_COLOR_ACCENT)
        else:
            pdf.set_fill_color(*PDF_COLOR_WHITE)
        pnl = float(row.get("P&L %", 0))
        values = [
            str(row.get("Ticker", "")),
            str(row.get("Name", ""))[:18],
            str(int(row.get("Quantity", 0))),
            f"{row.get('Avg Price', 0):,.0f}",
            f"{row.get('Current Price', 0):,.0f}",
            f"{pnl:+.1f}%",
            str(row.get("Sector", ""))[:8],
        ]
        for j, (v, w) in enumerate(zip(values, col_widths, strict=False)):
            if j == 5:
                pdf.set_text_color(0, 140, 0) if pnl >= 0 else pdf.set_text_color(200, 0, 0)
            else:
                pdf.set_text_color(0, 0, 0)
            pdf.cell(w, 5.5, f" {v}", border=1, fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln()

    if len(df) > 30:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, f"(+{len(df) - 30} more holdings — see CSV export for full data)",
                 new_x="LMARGIN", new_y="NEXT")

    # ── Footer ──
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(160, 160, 160)
    pdf.cell(0, 4, "Generated by NSE Portfolio Risk Scanner", align="C",
             new_x="LMARGIN", new_y="NEXT")
    # page number
    pdf.cell(0, 4, f"Page {pdf.page_no()}", align="C",
             new_x="LMARGIN", new_y="NEXT")

    result = pdf.output()
    return bytes(result) if isinstance(result, bytearray) else result
