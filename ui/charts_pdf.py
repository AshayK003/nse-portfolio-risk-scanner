"""Pure chart and PDF-report functions — zero Streamlit, zero fpdf2.
Uses matplotlib (Agg backend) for chart rendering and pdf-studio for PDF assembly.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
from matplotlib.figure import Figure
from pdf_studio import Document, Style, Font

from engine import Portfolio, RiskMetrics
from engine.recommendations import RecommendationReport
from engine.risk import MonteCarloResult


# ── Matplotlib helpers ──


def _import_matplotlib():
    """Lazy-import matplotlib with Agg backend. Returns (matplotlib, pyplot) or (None, None)."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return matplotlib, plt
    except ImportError:
        return None, None


# ── Chart builders (return matplotlib Figure objects, not bytes) ──


def _sector_pie_chart(sector_data: dict, page_w: float, plt) -> Figure | None:
    """Matplotlib pie chart for sector allocation. Returns figure (not bytes)."""
    if plt is None:
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
        textprops={"fontsize": 8},
    )
    ax.legend(
        wedges,
        [f"{lab} ({s:.0f}%)" for lab, s in zip(labels, sizes, strict=False)],
        loc="center left",
        bbox_to_anchor=(1, 0.5),
        fontsize=7,
    )
    ax.set_title("Sector Allocation", fontsize=10, fontweight="bold")
    fig.tight_layout()
    return fig


def _pnl_bar_chart(df: pd.DataFrame, page_w: float, plt) -> Figure | None:
    """Matplotlib horizontal bar chart of P&L per holding. Returns figure."""
    if plt is None:
        return None
    top = df.iloc[df["P&L %"].abs().argsort()[::-1][:10]] if "P&L %" in df.columns else df.head(10)
    tickers = [t.replace(".NS", "") for t in top["Ticker"]]
    pnl_values = top["P&L %"].values
    colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in pnl_values]
    fig, ax = plt.subplots(figsize=(page_w / 25.4, max(1.5, len(tickers) * 0.3)))
    bars = ax.barh(range(len(tickers)), pnl_values, color=colors, height=0.6)
    ax.set_yticks(range(len(tickers)))
    ax.set_yticklabels(tickers, fontsize=8)
    ax.axvline(0, color="black", linewidth=0.5)
    ax.set_xlabel("P&L %", fontsize=8)
    ax.tick_params(axis="x", labelsize=7)
    for bar, val in zip(bars, pnl_values, strict=False):
        px = bar.get_width()
        ax.text(
            px + (0.3 if px >= 0 else -0.3),
            bar.get_y() + bar.get_height() / 2,
            f"{val:+.1f}%",
            va="center",
            fontsize=7,
            ha="left" if px >= 0 else "right",
        )
    ax.margins(x=0.15)
    ax.set_title("Holdings P&L", fontsize=10, fontweight="bold")
    fig.tight_layout()
    return fig


def _risk_gauge_chart(volatility: float, page_w: float, plt) -> Figure | None:
    """Horizontal risk bar — green/amber/red zones with volatility marker. Returns figure."""
    if plt is None:
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
    ax.text(val, -0.25, f"{volatility:.1f}%", ha="center", fontsize=9, fontweight="bold")
    ax.text(7.5, 0.65, "LOW", ha="center", fontsize=6, color="#15803d", fontweight="bold")
    ax.text(22.5, 0.65, "MOD", ha="center", fontsize=6, color="#a16207", fontweight="bold")
    ax.text(55, 0.65, "HIGH", ha="center", fontsize=6, color="#dc2626", fontweight="bold")
    ax.set_title("Annual Volatility", fontsize=9, fontweight="bold", pad=8)
    fig.tight_layout()
    return fig


def _drawdown_area_chart(portfolio_cum: pd.Series, page_w: float, plt) -> Figure | None:
    """Red area chart of portfolio drawdown. Returns figure."""
    if plt is None:
        return None
    running_max = portfolio_cum.cummax()
    drawdown = (portfolio_cum - running_max) / running_max * 100
    fig, ax = plt.subplots(figsize=(page_w / 25.4, 2.0))
    ax.fill_between(drawdown.index, drawdown.values, 0, color="#ef4444", alpha=0.25)
    ax.plot(drawdown.index, drawdown.values, color="#dc2626", linewidth=0.8)
    ax.axhline(0, color="black", linewidth=0.3)
    ax.set_title("Portfolio Drawdown", fontsize=10, fontweight="bold")
    ax.set_ylabel("Drawdown (%)", fontsize=8)
    ax.tick_params(axis="both", labelsize=7)
    fig.tight_layout()
    return fig


def _monte_carlo_fan_chart(mc_result: MonteCarloResult, page_w: float, plt) -> Figure | None:
    """Monte Carlo confidence interval visualization. Returns figure."""
    if plt is None:
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
        fontsize=7,
        color="#2563eb",
    )
    ax.plot(mc_result.var_95, 0.25, "v", color="#ef4444", markersize=4, zorder=3)
    ax.text(
        mc_result.var_95, 0.08, f"VaR 95%: {mc_result.var_95:.1f}%", ha="center", fontsize=6, color="#ef4444"
    )
    ax.text(
        0,
        -0.05,
        f"P(Profit): {mc_result.prob_profit:.1f}% | {mc_result.n_simulations:,} sims, {mc_result.horizon_days}d horizon",
        ha="center",
        fontsize=6.5,
        color="#6b7280",
    )
    ax.set_title("Monte Carlo Projection", fontsize=10, fontweight="bold")
    fig.tight_layout()
    return fig


def _holdings_weight_bar(portfolio: Portfolio, page_w: float, plt) -> Figure | None:
    """Horizontal bar chart of top holdings by weight. Returns figure."""
    if plt is None:
        return None
    holdings = sorted(portfolio.holdings, key=lambda h: h.current_value, reverse=True)[:10]
    tickers = [h.ticker.replace(".NS", "") for h in holdings]
    total = portfolio.total_current or 1
    weights = [h.current_value / total * 100 for h in holdings]
    fig, ax = plt.subplots(figsize=(page_w / 25.4 * 0.45, 2.2))
    colors = plt.cm.Set2.colors[: len(tickers)]
    bars = ax.barh(range(len(tickers)), weights, color=colors, height=0.6)
    ax.set_yticks(range(len(tickers)))
    ax.set_yticklabels(tickers, fontsize=8)
    ax.set_xlabel("Weight (%)", fontsize=8)
    ax.tick_params(axis="x", labelsize=7)
    for bar, w in zip(bars, weights, strict=False):
        ax.text(
            bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2, f"{w:.1f}%", va="center", fontsize=7
        )
    ax.set_title("Top Holdings by Weight", fontsize=10, fontweight="bold")
    ax.margins(x=0.15)
    fig.tight_layout()
    return fig


# ── Cover / KPI figure builders (matplotlib, returns figures) ──


def _cover_page_figure(portfolio: Portfolio, risk: RiskMetrics | None, plt) -> Figure | None:
    """Build a single matplotlib figure that acts as the PDF cover page.

    Navy header block + centered text + KPI grid + risk gauge + assessment.
    """
    if plt is None:
        return None
    fig, ax = plt.subplots(figsize=(6.3, 8.5))
    ax.set_xlim(0, 6.3)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    # Navy header block
    ax.add_patch(plt.Rectangle((0, 6.8), 6.3, 1.7, facecolor=(25 / 255, 60 / 255, 120 / 255), edgecolor="none"))
    ax.text(3.15, 7.7, "NSE Portfolio Risk Report", ha="center", va="center", fontsize=18,
            fontweight="bold", color="white")
    ax.text(3.15, 7.2, portfolio.name, ha="center", va="center", fontsize=11, color="white")
    ax.text(3.15, 6.9, datetime.now().strftime("%d %B %Y"), ha="center", va="center",
            fontsize=9, fontstyle="italic", color="#cccccc")

    # KPI cards (2 rows × 3 columns)
    card_w = 1.9
    card_h = 0.55
    colors = [(240 / 255, 245 / 255, 250 / 255)] * 6
    pnl_clr = (220 / 255, 245 / 255, 220 / 255) if portfolio.total_pnl >= 0 else (250 / 255, 220 / 255, 220 / 255)
    colors[3] = pnl_clr

    kpis = [
        ("Holdings", str(portfolio.holding_count)),
        ("Total Invested", f"Rs {portfolio.total_invested:,.0f}"),
        ("Current Value", f"Rs {portfolio.total_current:,.0f}"),
        ("P&L", f"{'+' if portfolio.total_pnl >= 0 else ''}Rs {portfolio.total_pnl:+,.0f}"),
        ("P&L %", f"{portfolio.total_pnl_pct:+.2f}%"),
        ("Sharpe", f"{risk.sharpe:.2f}" if risk else "N/A"),
    ]

    primary_rgb = (25 / 255, 60 / 255, 120 / 255)
    y0 = 6.0
    for idx, ((label, value), bg) in enumerate(zip(kpis, colors, strict=False)):
        col = idx % 3
        row = idx // 3
        x = col * (card_w + 0.05) + 0.2
        y = y0 - row * (card_h + 0.08)
        ax.add_patch(plt.Rectangle((x, y), card_w, card_h, facecolor=bg, edgecolor="none"))
        ax.text(x + card_w / 2, y + card_h * 0.6, label, ha="center", va="center",
                fontsize=7, color=(80 / 255, 80 / 255, 80 / 255))
        ax.text(x + card_w / 2, y + card_h * 0.25, value, ha="center", va="center",
                fontsize=10, fontweight="bold", color=primary_rgb)

    # Risk gauge
    gauge_y = 4.2
    if risk:
        vol = risk.volatility_annual
        for i in range(80):
            c = "#22c55e" if i < 15 else "#f59e0b" if i < 30 else "#ef4444"
            ax.barh(gauge_y, 1, left=i, height=0.25, color=c, alpha=0.5, edgecolor="none")
        val = min(vol, 80)
        ax.plot(val, gauge_y, marker="v", color="#1f2937", markersize=5, zorder=3)
        ax.text(val, gauge_y - 0.2, f"{vol:.1f}%", ha="center", fontsize=8, fontweight="bold")
        ax.text(12, gauge_y + 0.3, "LOW", ha="center", fontsize=6, color="#15803d", fontweight="bold")
        ax.text(22.5, gauge_y + 0.3, "MOD", ha="center", fontsize=6, color="#a16207", fontweight="bold")
        ax.text(60, gauge_y + 0.3, "HIGH", ha="center", fontsize=6, color="#dc2626", fontweight="bold")

    # Risk assessment text
    assessment, bg_color = _risk_assessment_text(risk)
    ax.add_patch(plt.Rectangle((0, 3.5), 6.3, 0.35,
                               facecolor=tuple(c / 255 for c in bg_color), edgecolor="none"))
    ax.text(3.15, 3.67, f"Risk Level: {assessment}", ha="center", va="center",
            fontsize=8, fontweight="bold", color=(30 / 255, 30 / 255, 30 / 255))

    # Generation timestamp footer
    ax.text(3.15, 0.3, f"Report generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
            ha="center", fontsize=7, fontstyle="italic", color=(100 / 255, 100 / 255, 100 / 255))

    fig.tight_layout()
    return fig


def _kpi_row_figure(kpis: list[tuple[str, str]], page_w: float, plt,
                    colors: list[tuple] | None = None) -> Figure | None:
    """Build a single row of KPI/metric badges as a matplotlib figure.

    Each KPI is (label, value). Returns figure sized to fit a PDF column.
    """
    if plt is None or not kpis:
        return None
    n = len(kpis)
    fig_w = page_w / 25.4  # width in inches
    fig, ax = plt.subplots(figsize=(fig_w, 0.65))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    col_w = 1.0 / n
    default_bg = (240 / 255, 245 / 255, 250 / 255)
    primary_rgb = (25 / 255, 60 / 255, 120 / 255)

    for idx, ((label, value), bg) in enumerate(zip(kpis, colors or [default_bg] * n, strict=False)):
        x = idx * col_w
        ax.add_patch(plt.Rectangle((x + 0.01, 0), col_w - 0.02, 1,
                                   facecolor=bg, edgecolor="none"))
        ax.text(x + col_w / 2, 0.65, label, ha="center", va="center",
                fontsize=7, color=(80 / 255, 80 / 255, 80 / 255))
        ax.text(x + col_w / 2, 0.25, value, ha="center", va="center",
                fontsize=10, fontweight="bold", color=primary_rgb)
    fig.tight_layout()
    return fig


def _risk_assessment_text(risk: RiskMetrics | None) -> tuple[str, tuple]:
    """Return (assessment_text, background_color_tuple) based on risk metrics."""
    if risk is None:
        return "Risk data not available.", (240, 245, 250)
    vol = risk.volatility_annual
    sharpe = risk.sharpe
    if vol < 15 and sharpe > 1.0:
        return "LOW - portfolio shows low volatility with strong risk-adjusted returns.", (220, 245, 220)
    elif vol < 25 or sharpe > 0.5:
        return "MODERATE - moderate volatility with adequate compensation for risk taken.", (255, 243, 205)
    else:
        return (
            "HIGH - elevated volatility with weak risk-adjusted returns. Consider defensive positioning.",
            (250, 220, 220),
        )


# ── PDF report generator (pdf-studio) ──


def _generate_pdf_report(
    portfolio: Portfolio,
    risk: RiskMetrics | None,
    sector_data: dict | None,
    df: pd.DataFrame,
    mc_result: MonteCarloResult | None = None,
    portfolio_cum: pd.Series | None = None,
    recommendations: RecommendationReport | None = None,
) -> bytes:
    """Generate a professional PDF report using pdf-studio."""
    _, plt = _import_matplotlib()

    doc = Document()
    doc.set_header("NSE Portfolio Risk Report")

    # ── Cover Page ──
    cover = _cover_page_figure(portfolio, risk, plt)
    if cover:
        doc.add_chart(cover)

    # ── Page 2: Executive Summary ──
    doc.add_heading("1. Executive Summary", level=1)

    kpi_row1 = [
        ("Holdings", str(portfolio.holding_count)),
        ("Total Invested", f"Rs {portfolio.total_invested:,.0f}"),
        ("Current Value", f"Rs {portfolio.total_current:,.0f}"),
    ]
    pnl_color = (220 / 255, 245 / 255, 220 / 255) if portfolio.total_pnl >= 0 else (250 / 255, 220 / 255, 220 / 255)
    kpi_row2 = [
        ("P&L", f"{'+' if portfolio.total_pnl >= 0 else ''}Rs {portfolio.total_pnl:+,.0f}"),
        ("P&L %", f"{portfolio.total_pnl_pct:+.2f}%"),
        ("Sharpe", f"{risk.sharpe:.2f}" if risk else "N/A"),
    ]
    kpi1 = _kpi_row_figure(kpi_row1, 170, plt)
    if kpi1:
        doc.add_chart(kpi1, width=430, height=35)
    kpi2 = _kpi_row_figure(kpi_row2, 170, plt, colors=[pnl_color, None, None])
    if kpi2:
        doc.add_chart(kpi2, width=430, height=35)

    if risk:
        gauge = _risk_gauge_chart(risk.volatility_annual, 170, plt)
        if gauge:
            doc.add_chart(gauge, width=300, height=50)

        badge_kpis = [
            ("Sortino", f"{risk.sortino:.2f}"),
            ("Beta", f"{risk.beta:.2f}"),
            ("CAGR", f"{risk.cagr:.1f}%"),
        ]
        badge_row = _kpi_row_figure(badge_kpis, 170, plt)
        if badge_row:
            doc.add_chart(badge_row, width=300, height=35)

        assessment_text, bg_color = _risk_assessment_text(risk)
        doc.add_paragraph(f"Risk Level: {assessment_text}",
                         Style(font=Font("Inter", 10, bold=True), space_before=6, space_after=4))

    # Sector and weight charts side by side
    sector_fig = _sector_pie_chart(sector_data, 170, plt) if sector_data else None
    weight_fig = _holdings_weight_bar(portfolio, 170, plt)
    if sector_fig:
        doc.add_chart(sector_fig, width=230, height=140)
    if weight_fig:
        doc.add_chart(weight_fig, width=200, height=140)

    # ── Page 3: Risk Analysis ──
    doc.add_heading("2. Risk Analysis", level=1)

    if risk:
        metric_rows = [
            ("VaR (95%)", f"{risk.var_95:.2f}%", "CVaR (95%)", f"{risk.cvar_95:.2f}%",
             "Volatility", f"{risk.volatility_annual:.1f}%", "CAGR", f"{risk.cagr:.1f}%"),
            ("Max Drawdown", f"{risk.max_drawdown:.1f}%", "Total Return", f"{risk.total_return:.1f}%",
             "Sortino", f"{risk.sortino:.2f}", "Beta", f"{risk.beta:.2f}"),
            ("VaR (99%)", f"{risk.var_99:.2f}%", "Correlation", f"{risk.correlation_to_benchmark:.2f}",
             "Stock Count", str(portfolio.holding_count), "Sharpe", f"{risk.sharpe:.2f}"),
        ]
        for row in metric_rows:
            kpis = [(row[i], row[i + 1]) for i in range(0, 8, 2)]
            row_fig = _kpi_row_figure(kpis, 170, plt)
            if row_fig:
                doc.add_chart(row_fig, width=430, height=32)

    if portfolio_cum is not None and not portfolio_cum.empty:
        dd_fig = _drawdown_area_chart(portfolio_cum, 170, plt)
        if dd_fig:
            doc.add_chart(dd_fig, width=430, height=100)

    if mc_result:
        mc_fig = _monte_carlo_fan_chart(mc_result, 170, plt)
        if mc_fig:
            doc.add_chart(mc_fig, width=430, height=70)

    if recommendations and recommendations.priority_actions:
        doc.add_heading("Top Priority Actions", level=2)
        for rec in recommendations.priority_actions[:3]:
            action_text = f"{rec.action.value.upper()} {rec.target}"
            doc.add_paragraph(
                f"{action_text}: {rec.reasoning} ({rec.urgency}, confidence: {rec.confidence:.0%})",
                Style(font=Font("Inter", 9), space_before=2, space_after=2),
            )

    # ── Page 4: Holdings Breakdown ──
    doc.add_heading("3. Holdings Breakdown", level=1)

    pnl_fig = _pnl_bar_chart(df, 170, plt)
    if pnl_fig:
        doc.add_chart(pnl_fig, width=430, height=120)

    # Holdings table via pdf-studio
    display_df = df[["Ticker", "Name", "Quantity", "Avg Price", "Current Price", "P&L %", "Sector"]].copy()
    # Compact names for table readability
    if "Name" in display_df.columns:
        display_df["Name"] = display_df["Name"].apply(lambda x: str(x)[:18] if pd.notna(x) else "")
    if "Quantity" in display_df.columns:
        display_df["Quantity"] = display_df["Quantity"].apply(lambda x: str(int(x)) if pd.notna(x) else "")
    doc.add_table(display_df, caption="Holdings Detail")

    # Disclaimer
    doc.add_paragraph(
        "Disclaimer: This report is for informational purposes only and does not "
        "constitute financial advice. Data sourced from public APIs (yfinance, NSE) "
        "may be delayed or inaccurate. Past performance is not indicative of future results. "
        "Consult a SEBI-registered advisor before making investment decisions.",
        Style(font=Font("Inter", 8, italic=True), alignment="center", space_before=10, space_after=4),
    )
    doc.add_paragraph(
        "Generated by NSE Portfolio Risk Scanner",
        Style(font=Font("Inter", 7, italic=True), alignment="center", space_before=0, space_after=0),
    )

    # Render to bytes
    buf = BytesIO()
    doc.render(buf)
    buf.seek(0)
    return buf.read()
