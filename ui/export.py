"""
Report export — CSV download and PDF report generation.
3-page professional report with charts, risk gauge, drawdown, Monte Carlo.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from engine import Portfolio, RiskMetrics
from engine.recommendations import RecommendationReport
from engine.risk import MonteCarloResult
from ui.icons import DOWNLOAD, icon_text

PDF_COLOR_PRIMARY = (25, 60, 120)
PDF_COLOR_ACCENT = (240, 245, 250)
PDF_COLOR_GREEN = (220, 245, 220)
PDF_COLOR_RED = (250, 220, 220)
PDF_COLOR_AMBER = (255, 243, 205)
PDF_COLOR_WHITE = (255, 255, 255)
PDF_COLOR_DARK = (30, 30, 30)
PDF_COLOR_GRAY = (100, 100, 100)


def render_export_section(
    portfolio: Portfolio,
    risk: RiskMetrics | None = None,
    sector_data: dict | None = None,
    mc_result: MonteCarloResult | None = None,
    portfolio_returns: pd.Series | None = None,
    portfolio_cum: pd.Series | None = None,
    recommendations: RecommendationReport | None = None,
) -> None:
    """Display export buttons for the analysis results."""
    st.markdown(
        f'<div class="section-header">{icon_text(DOWNLOAD, "Export Report")}</div>',
        unsafe_allow_html=True,
    )

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

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download CSV Report",
        data=csv,
        file_name=f"portfolio_report_{portfolio.name.replace(' ', '_')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    try:
        pdf_bytes = _generate_pdf_report(
            portfolio, risk, sector_data, df, mc_result, portfolio_cum, recommendations
        )
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


def _section_header(pdf, title: str) -> None:
    """Draw a section header with colored background bar."""
    pdf.set_fill_color(*PDF_COLOR_PRIMARY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _kpi_card(pdf, label: str, value: str, x: float, y: float, w: float, color: tuple | None = None) -> float:
    """Draw a KPI card at (x, y) and return the bottom y."""
    card_h = 20
    bg = color or PDF_COLOR_ACCENT
    pdf.set_fill_color(*bg)
    pdf.rect(x, y, w, card_h, style="F")
    pdf.set_font("Helvetica", "", 6)
    pdf.set_text_color(80, 80, 80)
    pdf.set_xy(x + 2, y + 1.5)
    pdf.cell(w - 4, 4, label)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*PDF_COLOR_PRIMARY)
    pdf.set_xy(x + 2, y + 7)
    pdf.cell(w - 4, 7, value)
    pdf.set_text_color(0, 0, 0)
    return y + card_h + 3


def _data_table(pdf, headers: list[str], widths: list[int], rows: list[list[str]]) -> None:
    """Draw a table with alternating row colors."""
    pdf.set_fill_color(*PDF_COLOR_PRIMARY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 7)
    for h, w in zip(headers, widths, strict=False):
        pdf.cell(w, 6, f" {h}", border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 7)
    for i, row in enumerate(rows):
        if i % 2 == 0:
            pdf.set_fill_color(*PDF_COLOR_ACCENT)
        else:
            pdf.set_fill_color(*PDF_COLOR_WHITE)
        for val, w in zip(row, widths, strict=False):
            pdf.cell(w, 5.5, f" {val}", border=1, fill=True)
        pdf.ln()


def _chart_bytes(fig, plt_module) -> bytes:
    """Render a matplotlib figure to PNG bytes."""
    import io

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt_module.close(fig)
    buf.seek(0)
    return buf.read()


def _sector_pie_chart(sector_data: dict, page_w: float) -> bytes | None:
    """Matplotlib pie chart for sector allocation."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    labels = list(sector_data.keys())
    sizes = list(sector_data.values())
    colors = plt.cm.Set2.colors[: len(labels)]
    fig, ax = plt.subplots(figsize=(page_w / 25.4 * 0.55, 2.2))
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=None,
        autopct="%1.0f%%",
        startangle=90,
        colors=colors,
        textprops={"fontsize": 7},
    )
    ax.legend(
        wedges,
        [f"{lab} ({s:.0f}%)" for lab, s in zip(labels, sizes, strict=False)],
        loc="center left",
        bbox_to_anchor=(1, 0.5),
        fontsize=6,
    )
    ax.set_title("Sector Allocation", fontsize=9, fontweight="bold")
    return _chart_bytes(fig, plt)


def _pnl_bar_chart(df: pd.DataFrame, page_w: float) -> bytes | None:
    """Matplotlib horizontal bar chart of P&L per holding."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    top = df.iloc[df["P&L %"].abs().argsort()[::-1][:10]] if "P&L %" in df.columns else df.head(10)
    tickers = [t.replace(".NS", "") for t in top["Ticker"]]
    pnl_values = top["P&L %"].values
    colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in pnl_values]
    fig, ax = plt.subplots(figsize=(page_w / 25.4, max(1.5, len(tickers) * 0.3)))
    bars = ax.barh(range(len(tickers)), pnl_values, color=colors, height=0.6)
    ax.set_yticks(range(len(tickers)))
    ax.set_yticklabels(tickers, fontsize=7)
    ax.axvline(0, color="black", linewidth=0.5)
    ax.set_xlabel("P&L %", fontsize=7)
    ax.tick_params(axis="x", labelsize=6)
    for bar, val in zip(bars, pnl_values, strict=False):
        px = bar.get_width()
        ax.text(
            px + (0.3 if px >= 0 else -0.3),
            bar.get_y() + bar.get_height() / 2,
            f"{val:+.1f}%",
            va="center",
            fontsize=6,
            ha="left" if px >= 0 else "right",
        )
    ax.margins(x=0.15)
    ax.set_title("Holdings P&L", fontsize=9, fontweight="bold")
    fig.tight_layout()
    return _chart_bytes(fig, plt)


def _risk_gauge_chart(volatility: float, page_w: float) -> bytes | None:
    """Horizontal risk bar — green/amber/red zones with volatility marker."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    fig, ax = plt.subplots(figsize=(page_w / 25.4, 0.9))
    ax.set_xlim(0, 80)
    ax.set_ylim(0, 1)
    ax.axis("off")

    for i in range(0, 80):
        c = "#22c55e" if i < 15 else "#f59e0b" if i < 30 else "#ef4444"
        ax.axvspan(i, i + 1, 0, 0.55, facecolor=c, alpha=0.5, ec="none")

    val = min(volatility, 80)
    ax.plot([val, val], [0, 0.7], color="#1f2937", linewidth=2, zorder=3)
    ax.plot(val, 0.7, marker="v", color="#1f2937", markersize=5, zorder=3)
    ax.text(val, -0.25, f"{volatility:.1f}%", ha="center", fontsize=8, fontweight="bold")

    ax.text(7.5, 0.65, "LOW", ha="center", fontsize=5, color="#15803d", fontweight="bold")
    ax.text(22.5, 0.65, "MOD", ha="center", fontsize=5, color="#a16207", fontweight="bold")
    ax.text(55, 0.65, "HIGH", ha="center", fontsize=5, color="#dc2626", fontweight="bold")

    ax.set_title("Annual Volatility", fontsize=8, fontweight="bold", pad=6)
    fig.tight_layout()
    return _chart_bytes(fig, plt)


def _drawdown_area_chart(portfolio_cum: pd.Series, page_w: float) -> bytes | None:
    """Red area chart of portfolio drawdown."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    running_max = portfolio_cum.cummax()
    drawdown = (portfolio_cum - running_max) / running_max * 100

    fig, ax = plt.subplots(figsize=(page_w / 25.4, 2.0))
    ax.fill_between(drawdown.index, drawdown.values, 0, color="#ef4444", alpha=0.25)
    ax.plot(drawdown.index, drawdown.values, color="#dc2626", linewidth=0.8)
    ax.axhline(0, color="black", linewidth=0.3)
    ax.set_title("Portfolio Drawdown", fontsize=9, fontweight="bold")
    ax.set_ylabel("Drawdown (%)", fontsize=7)
    ax.tick_params(axis="both", labelsize=6)
    fig.tight_layout()
    return _chart_bytes(fig, plt)


def _monte_carlo_fan_chart(mc_result: MonteCarloResult, page_w: float) -> bytes | None:
    """Monte Carlo confidence interval visualization."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    fig, ax = plt.subplots(figsize=(page_w / 25.4, 1.2))
    margin = max(abs(mc_result.ci_lower), abs(mc_result.ci_upper)) * 1.3
    margin = max(margin, 5)
    ax.set_xlim(-margin, margin)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ci_lower = max(mc_result.ci_lower, -margin)
    ci_upper = min(mc_result.ci_upper, margin)
    ax.barh(
        0.5,
        ci_upper - ci_lower,
        left=ci_lower,
        height=0.25,
        color="#3b82f6",
        alpha=0.2,
        ec="#2563eb",
        linewidth=0.5,
    )

    ax.plot(mc_result.expected_return, 0.5, "D", color="#2563eb", markersize=5, zorder=3)
    ax.text(
        mc_result.expected_return,
        0.75,
        f"Expected: {mc_result.expected_return:.1f}%",
        ha="center",
        fontsize=6,
        color="#2563eb",
    )

    ax.plot(mc_result.var_95, 0.25, "v", color="#ef4444", markersize=4, zorder=3)
    ax.text(
        mc_result.var_95, 0.08, f"VaR 95%: {mc_result.var_95:.1f}%", ha="center", fontsize=5, color="#ef4444"
    )

    ax.text(
        0,
        -0.05,
        f"P(Profit): {mc_result.prob_profit:.1f}% | {mc_result.n_simulations:,} sims, {mc_result.horizon_days}d horizon",
        ha="center",
        fontsize=5.5,
        color="#6b7280",
    )

    ax.set_title("Monte Carlo Projection", fontsize=9, fontweight="bold")
    fig.tight_layout()
    return _chart_bytes(fig, plt)


def _holdings_weight_bar(portfolio: Portfolio, page_w: float) -> bytes | None:
    """Horizontal bar chart of top holdings by weight."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    holdings = sorted(portfolio.holdings, key=lambda h: h.current_value, reverse=True)[:10]
    tickers = [h.ticker.replace(".NS", "") for h in holdings]
    total = portfolio.total_current or 1
    weights = [h.current_value / total * 100 for h in holdings]

    fig, ax = plt.subplots(figsize=(page_w / 25.4 * 0.45, 2.2))
    colors = plt.cm.Set2.colors[: len(tickers)]
    bars = ax.barh(range(len(tickers)), weights, color=colors, height=0.6)
    ax.set_yticks(range(len(tickers)))
    ax.set_yticklabels(tickers, fontsize=7)
    ax.set_xlabel("Weight (%)", fontsize=7)
    ax.tick_params(axis="x", labelsize=6)
    for bar, w in zip(bars, weights, strict=False):
        ax.text(
            bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2, f"{w:.1f}%", va="center", fontsize=6
        )
    ax.set_title("Top Holdings by Weight", fontsize=9, fontweight="bold")
    ax.margins(x=0.15)
    fig.tight_layout()
    return _chart_bytes(fig, plt)


def _metric_badge(pdf, label: str, value: str, x: float, y: float, w: float) -> float:
    """Draw a compact metric badge and return the next y position."""
    h = 12
    pdf.set_fill_color(*PDF_COLOR_ACCENT)
    pdf.rect(x, y, w, h, style="F")
    pdf.set_font("Helvetica", "", 6)
    pdf.set_text_color(80, 80, 80)
    pdf.set_xy(x + 2, y + 1)
    pdf.cell(w - 4, 4, label)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*PDF_COLOR_PRIMARY)
    pdf.set_xy(x + 2, y + 5)
    pdf.cell(w - 4, 6, value)
    pdf.set_text_color(0, 0, 0)
    return y + h + 3


def _risk_assessment_text(risk: RiskMetrics | None) -> tuple[str, tuple]:
    """Return (assessment_text, background_color_tuple) based on risk metrics."""
    if risk is None:
        return "Risk data not available.", PDF_COLOR_ACCENT
    vol = risk.volatility_annual
    sharpe = risk.sharpe
    if vol < 15 and sharpe > 1.0:
        return "LOW - portfolio shows low volatility with strong risk-adjusted returns.", PDF_COLOR_GREEN
    elif vol < 25 or sharpe > 0.5:
        return "MODERATE - moderate volatility with adequate compensation for risk taken.", PDF_COLOR_AMBER
    else:
        return (
            "HIGH - elevated volatility with weak risk-adjusted returns. Consider defensive positioning.",
            PDF_COLOR_RED,
        )


def _generate_pdf_report(
    portfolio: Portfolio,
    risk: RiskMetrics | None,
    sector_data: dict | None,
    df: pd.DataFrame,
    mc_result: MonteCarloResult | None = None,
    portfolio_cum: pd.Series | None = None,
    recommendations: RecommendationReport | None = None,
) -> bytes:
    """Generate a 3-page professional PDF report using fpdf2."""
    from datetime import datetime

    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    page_w = pdf.w - pdf.l_margin - pdf.r_margin

    # ── Page 1: Executive Summary ──
    _add_page_header(pdf, "Executive Summary")

    # KPI Cards: 2 rows x 3 cols
    card_w = (page_w - 6) / 3
    y0 = pdf.get_y()
    pnl_color = PDF_COLOR_GREEN if portfolio.total_pnl >= 0 else PDF_COLOR_RED
    pnl_sign = "+" if portfolio.total_pnl >= 0 else ""

    _kpi_card(pdf, "Holdings", str(portfolio.holding_count), pdf.l_margin, y0, card_w)
    _kpi_card(
        pdf, "Total Invested", f"Rs {portfolio.total_invested:,.0f}", pdf.l_margin + card_w + 3, y0, card_w
    )
    _kpi_card(
        pdf,
        "Current Value",
        f"Rs {portfolio.total_current:,.0f}",
        pdf.l_margin + 2 * (card_w + 3),
        y0,
        card_w,
    )

    y1 = y0 + 23
    _kpi_card(
        pdf, "P&L", f"{pnl_sign}Rs {portfolio.total_pnl:+,.0f}", pdf.l_margin, y1, card_w, color=pnl_color
    )
    _kpi_card(pdf, "P&L %", f"{portfolio.total_pnl_pct:+.2f}%", pdf.l_margin + card_w + 3, y1, card_w)
    _kpi_card(
        pdf, "Sharpe", f"{risk.sharpe:.2f}" if risk else "N/A", pdf.l_margin + 2 * (card_w + 3), y1, card_w
    )

    pdf.set_y(y1 + 23)

    # Risk gauge + metric badges side by side
    gauge_chart = _risk_gauge_chart(risk.volatility_annual if risk else 0, page_w)
    if gauge_chart:
        gauge_w = page_w * 0.5
        pdf.image(gauge_chart, x=pdf.l_margin, w=gauge_w)
    if risk:
        badge_w = (page_w - gauge_w - 4) / 3
        bx = pdf.l_margin + gauge_w + 4
        by = pdf.get_y() + 2
        _metric_badge(pdf, "Sortino", f"{risk.sortino:.2f}", bx, by, badge_w)
        _metric_badge(pdf, "Beta", f"{risk.beta:.2f}", bx + badge_w + 2, by, badge_w)
        _metric_badge(pdf, "CAGR", f"{risk.cagr:.1f}%", bx + 2 * (badge_w + 2), by, badge_w)

    pdf.ln(4)

    # Risk assessment box
    assessment_text, bg_color = _risk_assessment_text(risk)
    pdf.set_fill_color(*bg_color)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*PDF_COLOR_DARK)
    pdf.cell(0, 6, f"  Risk Level: {assessment_text}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Sector pie + Holdings weight side by side
    col_w = page_w / 2
    y_before_charts = pdf.get_y()
    chart_top = y_before_charts

    sector_chart = _sector_pie_chart(sector_data, page_w) if sector_data else None
    weight_chart = _holdings_weight_bar(portfolio, page_w)

    if sector_chart:
        pdf.image(sector_chart, x=pdf.l_margin, w=col_w - 2)
    if weight_chart:
        pdf.image(weight_chart, x=pdf.l_margin + col_w + 2, w=col_w - 2)

    pdf.set_y(max(chart_top + 55, pdf.get_y()))

    # Info line: date generated
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(*PDF_COLOR_GRAY)
    pdf.cell(
        0,
        4,
        f"Report generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    # ── Page 2: Risk Analysis ──
    pdf.add_page()
    _add_page_header(pdf, "Risk Analysis")

    if risk:
        metrics = [
            ("VaR (95%)", f"{risk.var_95:.2f}%", "CAGR", f"{risk.cagr:.1f}%"),
            ("CVaR (95%)", f"{risk.cvar_95:.2f}%", "Total Return", f"{risk.total_return:.1f}%"),
            ("Max Drawdown", f"{risk.max_drawdown:.1f}%", "Volatility", f"{risk.volatility_annual:.1f}%"),
            ("Correlation to Bmk", f"{risk.correlation_to_benchmark:.2f}", "Beta", f"{risk.beta:.2f}"),
        ]
        col_w = page_w / 2
        y_start = pdf.get_y()
        for i, (lbl1, val1, lbl2, val2) in enumerate(metrics):
            y = y_start + i * 6
            pdf.set_fill_color(*PDF_COLOR_ACCENT)
            pdf.rect(pdf.l_margin, y, col_w - 2, 5, style="F")
            pdf.set_font("Helvetica", "", 7)
            pdf.set_xy(pdf.l_margin + 2, y + 0.5)
            pdf.cell(col_w - 4, 5, lbl1)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_xy(pdf.l_margin + col_w / 2, y + 0.5)
            pdf.cell(col_w / 2 - 4, 5, val1)

            pdf.set_fill_color(*PDF_COLOR_ACCENT)
            pdf.rect(pdf.l_margin + col_w + 2, y, col_w - 2, 5, style="F")
            pdf.set_font("Helvetica", "", 7)
            pdf.set_xy(pdf.l_margin + col_w + 4, y + 0.5)
            pdf.cell(col_w - 4, 5, lbl2)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_xy(pdf.l_margin + col_w + 2 + col_w / 2, y + 0.5)
            pdf.cell(col_w / 2 - 4, 5, val2)

        pdf.set_y(y_start + len(metrics) * 6 + 4)

    # Drawdown chart
    if portfolio_cum is not None and not portfolio_cum.empty:
        dd_chart = _drawdown_area_chart(portfolio_cum, page_w)
        if dd_chart:
            pdf.image(dd_chart, x=pdf.l_margin, w=page_w)
            pdf.ln(2)

    # Monte Carlo fan
    if mc_result:
        mc_chart = _monte_carlo_fan_chart(mc_result, page_w)
        if mc_chart:
            pdf.image(mc_chart, x=pdf.l_margin, w=page_w)
            pdf.ln(2)

    # Top 3 recommendations
    if recommendations and recommendations.priority_actions:
        pdf.ln(1)
        _section_header(pdf, "Top Priority Actions")
        for rec in recommendations.priority_actions[:3]:
            action_colors_map = {
                "reduce": "#ef4444",
                "hedge": "#f59e0b",
                "diversify": "#3b82f6",
                "accumulate": "#22c55e",
                "monitor": "#6b7280",
                "rebalance": "#a855f7",
            }
            hex_color = action_colors_map.get(rec.action.value, "#6b7280")
            rgb = tuple(int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
            pdf.set_fill_color(*rgb)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 7)
            action_label = f"  {rec.action.value.upper()} {rec.target}  "
            pdf.cell(pdf.get_string_width(action_label) + 4, 5, action_label, fill=True)
            pdf.ln(3)
            pdf.set_text_color(*PDF_COLOR_DARK)
            pdf.set_font("Helvetica", "", 7)
            pdf.multi_cell(0, 3.5, f"{rec.reasoning}  ({rec.urgency}, confidence: {rec.confidence:.0%})")
            pdf.ln(1)

    # ── Page 3: Holdings Breakdown ──
    pdf.add_page()
    _add_page_header(pdf, "Holdings Breakdown")

    pnl_chart = _pnl_bar_chart(df, page_w)
    if pnl_chart:
        pdf.image(pnl_chart, x=pdf.l_margin, w=page_w)
        pdf.ln(2)

    # Holdings table
    cols = ["Ticker", "Name", "Qty", "Avg Price", "Current", "P&L %", "Sector"]
    col_widths = [24, 44, 14, 24, 24, 18, 22]
    col_widths = [int(w * page_w / sum(col_widths)) for w in col_widths]

    pdf.set_fill_color(*PDF_COLOR_PRIMARY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 7)
    for c, w in zip(cols, col_widths, strict=False):
        pdf.cell(w, 6, f" {c}", border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 7)

    for i, (_, row) in enumerate(df.head(25).iterrows()):
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
            pdf.cell(w, 5, f" {v}", border=1, fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln()

    if len(df) > 25:
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(
            0,
            5,
            f"(+{len(df) - 25} more holdings - see CSV export for full data)",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    # Disclaimer
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 6)
    pdf.set_text_color(140, 140, 140)
    pdf.multi_cell(
        0,
        2.5,
        "Disclaimer: This report is for informational purposes only and does not "
        "constitute financial advice. Data sourced from public APIs (yfinance, NSE) "
        "may be delayed or inaccurate. Past performance is not indicative of future results. "
        "Consult a SEBI-registered advisor before making investment decisions.",
        align="C",
    )

    # Footer
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 6)
    pdf.set_text_color(160, 160, 160)
    pdf.cell(0, 3, "Generated by NSE Portfolio Risk Scanner", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 3, f"Page {pdf.page_no()}", align="C", new_x="LMARGIN", new_y="NEXT")

    result = pdf.output()
    return bytes(result) if isinstance(result, bytearray) else result


def _add_page_header(pdf, title: str | None = None) -> None:
    """Draw a dark navy header bar at the top of the current page."""
    pdf.set_fill_color(*PDF_COLOR_PRIMARY)
    pdf.rect(0, 0, pdf.w, 10, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(pdf.l_margin, 2)
    label = "NSE Portfolio Risk Report"
    if title:
        label += f" - {title}"
    pdf.cell(0, 6, label)
    pdf.set_text_color(*PDF_COLOR_GRAY)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_xy(pdf.w - pdf.r_margin - 55, 2.5)
    from datetime import datetime

    pdf.cell(55, 6, datetime.now().strftime("%d %b %Y"), align="R")
    pdf.set_y(14)
    pdf.set_text_color(0, 0, 0)
