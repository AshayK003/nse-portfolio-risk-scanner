"""
Self-contained PDF report generator using reportlab directly.

This avoids the fragile external pdf-studio package dependency on Streamlit Cloud,
which has had issues with git-install builds not exposing the template API.
reportlab is a stable, well-tested dependency available on all platforms.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd

# matplotlib: guarded import — Figure is used only in type annotations
try:
    from matplotlib.figure import Figure

    _MATPLOTLIB_OK = True
except ImportError:
    Figure = None  # type: ignore[assignment, misc]
    _MATPLOTLIB_OK = False

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


# ── Chart figure builders (return Figure objects) ──


def _cover_banner(portfolio: Portfolio, plt) -> Figure | None:
    if plt is None:
        return None
    fig, ax = plt.subplots(figsize=(6.3, 2.2))
    ax.set_xlim(0, 6.3)
    ax.set_ylim(0, 2.2)
    ax.axis("off")

    navy = (25 / 255, 60 / 255, 120 / 255)
    ax.add_patch(plt.Rectangle((0, 0.3), 6.3, 1.9, facecolor=navy, edgecolor="none"))
    ax.text(3.15, 1.9, "NSE Portfolio Risk Report", ha="center", va="center",
            fontsize=20, fontweight="bold", color="white")
    ax.text(3.15, 1.4, portfolio.name, ha="center", va="center", fontsize=13, color="white")
    ax.text(3.15, 0.95, datetime.now().strftime("%d %B %Y"), ha="center", va="center",
            fontsize=9, fontstyle="italic", color="#bbbbbb")
    fig.tight_layout()
    return fig


def _gauge(risk: RiskMetrics | None, plt) -> Figure | None:
    if plt is None or risk is None:
        return None
    fig, ax = plt.subplots(figsize=(6.3, 1.3))
    ax.set_xlim(0, 80)
    ax.set_ylim(0, 1)
    ax.axis("off")

    for i in range(0, 80):
        c = "#22c55e" if i < 15 else "#f59e0b" if i < 30 else "#ef4444"
        ax.axvspan(i, i + 1, 0, 0.55, facecolor=c, alpha=0.5, ec="none")

    val = min(risk.volatility_annual, 80)
    ax.plot([val, val], [0, 0.7], color="#1f2937", linewidth=2, zorder=3)
    ax.plot(val, 0.7, marker="v", color="#1f2937", markersize=5, zorder=3)
    ax.text(val, -0.35, f"{risk.volatility_annual:.1f}%", ha="center", fontsize=9, fontweight="bold")
    ax.text(7.5, 0.65, "LOW", ha="center", fontsize=6, color="#15803d", fontweight="bold")
    ax.text(22.5, 0.65, "MOD", ha="center", fontsize=6, color="#a16207", fontweight="bold")
    ax.text(55, 0.65, "HIGH", ha="center", fontsize=6, color="#dc2626", fontweight="bold")
    ax.set_title("Annual Volatility", fontsize=9, fontweight="bold", pad=6)
    fig.tight_layout()
    return fig


def _sector_weight_composite(sector_data: dict | None, portfolio: Portfolio, plt) -> Figure | None:
    if plt is None:
        return None
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.3, 2.5))

    if sector_data:
        labels = list(sector_data.keys())
        sizes = list(sector_data.values())
        colors = plt.cm.Set2.colors[: len(labels)]
        wedges, texts, autotexts = ax1.pie(
            sizes, labels=None, autopct="%1.0f%%", startangle=90,
            colors=colors, textprops={"fontsize": 7},
        )
        ax1.set_title("Sector Allocation", fontsize=10, fontweight="bold")
        ax1.legend(
            wedges,
            [f"{lab} ({s:.0f}%)" for lab, s in zip(labels, sizes, strict=False)],
            loc="center left", bbox_to_anchor=(1, 0.5), fontsize=6,
        )

    holdings = sorted(portfolio.holdings, key=lambda h: h.current_value, reverse=True)[:10]
    tickers = [h.ticker.replace(".NS", "") for h in holdings]
    total = portfolio.total_current or 1
    weights = [h.current_value / total * 100 for h in holdings]
    bar_colors = plt.cm.Set2.colors[: len(tickers)]
    bars = ax2.barh(range(len(tickers)), weights, color=bar_colors, height=0.6)
    ax2.set_yticks(range(len(tickers)))
    ax2.set_yticklabels(tickers, fontsize=7)
    ax2.set_xlabel("Weight (%)", fontsize=7)
    ax2.tick_params(axis="x", labelsize=6)
    for bar, w in zip(bars, weights, strict=False):
        ax2.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                 f"{w:.1f}%", va="center", fontsize=7)
    ax2.set_title("Top Holdings", fontsize=10, fontweight="bold")
    ax2.margins(x=0.15)
    fig.tight_layout()
    return fig


def _drawdown_chart(portfolio_cum: pd.Series, plt) -> Figure | None:
    if plt is None:
        return None
    running_max = portfolio_cum.cummax()
    drawdown = (portfolio_cum - running_max) / running_max * 100

    fig, ax = plt.subplots(figsize=(6.3, 1.8))
    ax.fill_between(drawdown.index, drawdown.values, 0, color="#ef4444", alpha=0.2)
    ax.plot(drawdown.index, drawdown.values, color="#dc2626", linewidth=0.8)
    ax.axhline(0, color="black", linewidth=0.3)
    ax.set_title("Portfolio Drawdown", fontsize=10, fontweight="bold")
    ax.set_ylabel("Drawdown (%)", fontsize=8)
    ax.tick_params(axis="both", labelsize=7)
    fig.tight_layout()
    return fig


def _monte_carlo_chart(mc_result: MonteCarloResult, plt) -> Figure | None:
    if plt is None:
        return None
    fig, ax = plt.subplots(figsize=(6.3, 1.2))
    margin = max(abs(mc_result.ci_lower), abs(mc_result.ci_upper)) * 1.3
    margin = max(margin, 5)
    ax.set_xlim(-margin, margin)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ci_lower = max(mc_result.ci_lower, -margin)
    ci_upper = min(mc_result.ci_upper, margin)
    ax.barh(0.5, ci_upper - ci_lower, left=ci_lower, height=0.25,
            color="#3b82f6", alpha=0.2, ec="#2563eb", linewidth=0.5)
    ax.plot(mc_result.expected_return, 0.5, "D", color="#2563eb", markersize=5, zorder=3)
    ax.text(mc_result.expected_return, 0.75, f"Expected: {mc_result.expected_return:.1f}%",
            ha="center", fontsize=7, color="#2563eb")
    ax.plot(mc_result.var_95, 0.25, "v", color="#ef4444", markersize=4, zorder=3)
    ax.text(mc_result.var_95, 0.08, f"VaR 95%: {mc_result.var_95:.1f}%",
            ha="center", fontsize=6, color="#ef4444")
    ax.text(0, -0.05, f"P(Profit): {mc_result.prob_profit:.1f}% | {mc_result.n_simulations:,} sims, "
                       f"{mc_result.horizon_days}d horizon", ha="center", fontsize=6, color="#6b7280")
    ax.set_title("Monte Carlo Projection", fontsize=10, fontweight="bold")
    fig.tight_layout()
    return fig


def _pnl_chart(df: pd.DataFrame, plt) -> Figure | None:
    if plt is None:
        return None
    top = df.iloc[df["P&L %"].abs().argsort()[::-1][:10]] if "P&L %" in df.columns else df.head(10)
    tickers = [t.replace(".NS", "") for t in top["Ticker"]]
    pnl_values = top["P&L %"].values

    fig, ax = plt.subplots(figsize=(6.3, max(1.5, len(tickers) * 0.3)))
    colors = ["#22c55e" if v >= 0 else "#ef4444" for v in pnl_values]
    bars = ax.barh(range(len(tickers)), pnl_values, color=colors, height=0.55)
    ax.set_yticks(range(len(tickers)))
    ax.set_yticklabels(tickers, fontsize=8)
    ax.axvline(0, color="black", linewidth=0.4)
    ax.set_xlabel("P&L %", fontsize=8)
    ax.tick_params(axis="x", labelsize=7)
    for bar, val in zip(bars, pnl_values, strict=False):
        px = bar.get_width()
        ax.text(px + (0.4 if px >= 0 else -0.4), bar.get_y() + bar.get_height() / 2,
                f"{val:+.1f}%", va="center", fontsize=7, ha="left" if px >= 0 else "right")
    ax.set_title("Holdings P&L", fontsize=10, fontweight="bold")
    ax.margins(x=0.15)
    fig.tight_layout()
    return fig


# ── Risk assessment ──


def _risk_assessment_text(risk: RiskMetrics | None) -> tuple[str, str]:
    if risk is None:
        return "Risk data not available.", "#f0f5fa"
    vol = risk.volatility_annual
    sharpe = risk.sharpe
    if vol < 15 and sharpe > 1.0:
        return "LOW — low volatility with strong risk-adjusted returns.", "#dcf5dc"
    elif vol < 25 or sharpe > 0.5:
        return "MODERATE — moderate volatility with adequate compensation for risk taken.", "#fff3cd"
    else:
        return "HIGH — elevated volatility with weak risk-adjusted returns. Consider defensive positioning.", "#fadcda"


# ── PDF assembly with reportlab ──


def generate_pdf_report(
    portfolio: Portfolio,
    risk: RiskMetrics | None,
    sector_data: dict | None,
    df: pd.DataFrame,
    mc_result: MonteCarloResult | None = None,
    portfolio_cum: pd.Series | None = None,
    recommendations: RecommendationReport | None = None,
) -> bytes:
    """Generate a 4-page PDF report using reportlab (self-contained, no external pdf_studio)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image,
    )

    _, plt = _import_matplotlib()
    if plt is None:
        raise ImportError("matplotlib is required for PDF chart rendering")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title="NSE Portfolio Risk Report",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=14, spaceAfter=8, textColor=colors.HexColor("#1a3c78"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#1a3c78"))
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, spaceAfter=6)
    muted = ParagraphStyle("muted", parent=styles["Normal"], fontSize=7, textColor=colors.grey, alignment=1)
    disclaimer = ParagraphStyle("disclaimer", parent=styles["Normal"], fontSize=7, textColor=colors.grey, alignment=1, spaceBefore=10)

    def fig_to_img(fig, width=17 * cm):
        from io import BytesIO as _B
        b = _B()
        fig.savefig(b, format="png", dpi=150, bbox_inches="tight")
        b.seek(0)
        from reportlab.lib.utils import ImageReader
        img = Image(b, width=width, height=width * fig.get_size_inches()[1] / fig.get_size_inches()[0])
        plt.close(fig)
        return img

    # ── Build flowables ──
    flow: list = []

    # PAGE 1 — COVER
    banner = _cover_banner(portfolio, plt)
    if banner:
        flow.append(fig_to_img(banner, width=17 * cm))
        flow.append(Spacer(1, 8))

    flow.append(Paragraph("Portfolio Summary", h2))

    cover_rows = [
        ["Holdings", str(portfolio.holding_count), "Total Invested", f"Rs {portfolio.total_invested:,.0f}"],
        ["Current Value", f"Rs {portfolio.total_current:,.0f}", "P&L", f"Rs {portfolio.total_pnl:+,.0f}"],
        ["P&L %", f"{portfolio.total_pnl_pct:+.2f}%", "Sharpe", f"{risk.sharpe:.2f}" if risk else "N/A"],
    ]
    t = Table(cover_rows, colWidths=[4 * cm, 4.5 * cm, 4 * cm, 4.5 * cm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.grey),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 10))

    gauge_fig = _gauge(risk, plt)
    if gauge_fig:
        flow.append(fig_to_img(gauge_fig, width=17 * cm))
        flow.append(Spacer(1, 6))

    if risk:
        text, bg = _risk_assessment_text(risk)
        rt = Table([[f"Risk Level: {text}"]], colWidths=[17 * cm])
        rt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        flow.append(rt)

    flow.append(Spacer(1, 6))
    flow.append(Paragraph(f"Report generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}", muted))
    flow.append(PageBreak())

    # PAGE 2 — EXECUTIVE SUMMARY
    flow.append(Paragraph("1. Executive Summary", h1))
    flow.append(Paragraph("Portfolio-wide risk metrics at a glance.", body))

    full_rows = [
        ["Holdings", str(portfolio.holding_count), "Total Invested", f"Rs {portfolio.total_invested:,.0f}"],
        ["Current Value", f"Rs {portfolio.total_current:,.0f}", "P&L", f"Rs {portfolio.total_pnl:+,.0f}"],
        ["P&L %", f"{portfolio.total_pnl_pct:+.2f}%", "Sharpe", f"{risk.sharpe:.2f}" if risk else "N/A"],
    ]
    if risk:
        full_rows += [
            ["Sortino", f"{risk.sortino:.2f}", "Beta", f"{risk.beta:.2f}"],
            ["Backtest CAGR", f"{risk.cagr:.1f}%", "VaR (95%)", f"{risk.var_95:.2f}%"],
            ["CVaR (95%)", f"{risk.cvar_95:.2f}%", "Volatility", f"{risk.volatility_annual:.1f}%"],
        ]
    t2 = Table(full_rows, colWidths=[4 * cm, 4.5 * cm, 4 * cm, 4.5 * cm])
    t2.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.grey),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
    ]))
    flow.append(t2)
    flow.append(Spacer(1, 8))

    if risk:
        flow.append(Paragraph(
            f"Annualised volatility of {risk.volatility_annual:.1f}% with a Sharpe ratio "
            f"of {risk.sharpe:.2f} indicates "
            f"{'strong' if risk.sharpe > 1 else 'adequate' if risk.sharpe > 0.5 else 'weak'} "
            f"risk-adjusted returns.", body))

    sw_fig = _sector_weight_composite(sector_data, portfolio, plt)
    if sw_fig:
        flow.append(fig_to_img(sw_fig, width=17 * cm))
    flow.append(PageBreak())

    # PAGE 3 — RISK ANALYSIS
    flow.append(Paragraph("2. Risk Analysis", h1))
    flow.append(Paragraph("Detailed risk metrics, historical drawdown, and forward-looking simulation.", body))

    if risk:
        risk_rows = [
            ["VaR (95%)", f"{risk.var_95:.2f}%", "CVaR (95%)", f"{risk.cvar_95:.2f}%"],
            ["Volatility", f"{risk.volatility_annual:.1f}%", "Backtest CAGR", f"{risk.cagr:.1f}%"],
            ["Max Drawdown", f"{risk.max_drawdown:.1f}%", "Total Return", f"{risk.total_return:.1f}%"],
            ["Sortino", f"{risk.sortino:.2f}", "Beta", f"{risk.beta:.2f}"],
            ["VaR (99%)", f"{risk.var_99:.2f}%", "Correlation", f"{risk.correlation_to_benchmark:.2f}"],
            ["Stock Count", str(portfolio.holding_count), "Sharpe", f"{risk.sharpe:.2f}"],
            ["Calmar Ratio", f"{risk.calmar_ratio:.2f}", "Treynor Ratio", f"{risk.treynor_ratio:.2f}"],
            ["Skewness", f"{risk.skewness:.3f}", "Excess Kurtosis", f"{risk.kurtosis_excess:.3f}"],
        ]
        t3 = Table(risk_rows, colWidths=[4 * cm, 4.5 * cm, 4 * cm, 4.5 * cm])
        t3.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
            ("TEXTCOLOR", (2, 0), (2, -1), colors.grey),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ]))
        flow.append(t3)
        flow.append(Spacer(1, 8))

    if portfolio_cum is not None and not portfolio_cum.empty:
        dd_fig = _drawdown_chart(portfolio_cum, plt)
        if dd_fig:
            flow.append(fig_to_img(dd_fig, width=17 * cm))
            flow.append(Spacer(1, 8))

    if mc_result:
        mc_fig = _monte_carlo_chart(mc_result, plt)
        if mc_fig:
            flow.append(fig_to_img(mc_fig, width=17 * cm))
            flow.append(Spacer(1, 8))

    if recommendations and recommendations.priority_actions:
        flow.append(Paragraph("Top Priority Actions", h2))
        for rec in recommendations.priority_actions[:5]:
            flow.append(Paragraph(
                f"&bull; {rec.action.value.upper()} {rec.target}: {rec.reasoning} "
                f"({rec.urgency}, {rec.confidence:.0%} confidence)", body))
    flow.append(PageBreak())

    # PAGE 4 — HOLDINGS BREAKDOWN
    flow.append(Paragraph("3. Holdings Breakdown", h1))
    flow.append(Paragraph("Per-holding P&L and detailed position data.", body))

    pnl_fig = _pnl_chart(df, plt)
    if pnl_fig:
        flow.append(fig_to_img(pnl_fig, width=17 * cm))
        flow.append(Spacer(1, 8))

    display_cols = ["Ticker", "Name", "Quantity", "Avg Price", "Current Price", "P&L %", "Sector"]
    display_df = df[display_cols].copy() if all(c in df.columns for c in display_cols) else df.copy()
    if "Name" in display_df.columns:
        display_df["Name"] = display_df["Name"].apply(lambda x: str(x)[:18] if pd.notna(x) else "")
    if "Quantity" in display_df.columns:
        display_df["Quantity"] = display_df["Quantity"].apply(lambda x: str(int(x)) if pd.notna(x) else "")
    if "P&L %" in display_df.columns:
        display_df["P&L %"] = display_df["P&L %"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "")

    table_data = [list(display_df.columns)] + display_df.astype(str).values.tolist()
    t4 = Table(table_data, colWidths=[2 * cm, 3.5 * cm, 1.8 * cm, 2 * cm, 2.2 * cm, 1.8 * cm, 2.2 * cm], repeatRows=1)
    t4.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (2, 0), (5, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
    ]))
    flow.append(t4)
    flow.append(Spacer(1, 10))

    flow.append(Paragraph(
        "Disclaimer: This report is for informational purposes only and does not constitute financial advice. "
        "Data sourced from public APIs (yfinance, NSE) may be delayed or inaccurate. Past performance is not "
        "indicative of future results. Consult a SEBI-registered advisor before making investment decisions.",
        disclaimer))
    flow.append(Paragraph("Generated by NSE Portfolio Risk Scanner", muted))

    doc.build(flow)
    buf.seek(0)
    return buf.read()
