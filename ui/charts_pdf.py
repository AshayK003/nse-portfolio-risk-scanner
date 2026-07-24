"""Clean PDF report using pdf-studio native features.
Chart builders return matplotlib figures; PDF assembly uses pdf-studio tables,
headings, paragraphs, charts, bullets, and explicit page breaks.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
from matplotlib.figure import Figure

from engine import Portfolio, RiskMetrics
from engine.recommendations import RecommendationReport
from engine.risk import MonteCarloResult

# pdf-studio: lazy import so the module loads even when not installed
try:
    from pdf_studio import Document, Font, Style

    _PDFSTUDIO_OK = True
except ImportError:
    _PDFSTUDIO_OK = False


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


# ── Style presets (used inside _generate_pdf_report) ──


def _body_style() -> Style:
    return Style(font=Font("Inter", 9), space_before=1, space_after=10)


def _body_bold() -> Style:
    return Style(font=Font("Inter", 9, bold=True), space_before=2, space_after=10)


def _muted_style() -> Style:
    return Style(font=Font("Inter", 7, italic=True), alignment="center", space_before=1, space_after=2)


def _disclaimer_style() -> Style:
    return Style(font=Font("Inter", 7, italic=True), alignment="center", space_before=14, space_after=8)


def _subtitle_style() -> Style:
    return Style(font=Font("Inter", 11, bold=True), space_before=14, space_after=14)


def _spacer(pts: float) -> Style:
    """Return a minimal-height paragraph style acting as a vertical spacer."""
    return Style(font=Font("Inter", 1), space_before=0, space_after=pts)


# ── Helper: build 4-column data tables ──


def _metrics_table(rows: list[tuple[str, str, str, str]]) -> list[list[str]]:
    """Build a 4-column [Metric, Value, Metric, Value] table from paired tuples."""
    header = ["Metric", "Value", "Metric", "Value"]
    return [header] + [list(r) for r in rows]


def _cover_metrics(portfolio: Portfolio, risk: RiskMetrics | None) -> list[list[str]]:
    """Portfolio summary for the cover page (4-column)."""
    sharpe_val = f"{risk.sharpe:.2f}" if risk else "N/A"
    pnl_val = f"Rs {portfolio.total_pnl:+,.0f}"
    return _metrics_table(
        [
            (
                "Holdings",
                str(portfolio.holding_count),
                "Total Invested",
                f"Rs {portfolio.total_invested:,.0f}",
            ),
            ("Current Value", f"Rs {portfolio.total_current:,.0f}", "P&L", pnl_val),
            ("P&L %", f"{portfolio.total_pnl_pct:+.2f}%", "Sharpe", sharpe_val),
        ]
    )


def _full_metrics(portfolio: Portfolio, risk: RiskMetrics | None) -> list[list[str]]:
    """Extended metrics for Executive Summary (4-column)."""
    pnl_val = f"Rs {portfolio.total_pnl:+,.0f}"
    metric_rows = [
        ("Holdings", str(portfolio.holding_count), "Total Invested", f"Rs {portfolio.total_invested:,.0f}"),
        ("Current Value", f"Rs {portfolio.total_current:,.0f}", "P&L", pnl_val),
        ("P&L %", f"{portfolio.total_pnl_pct:+.2f}%", "Sharpe", f"{risk.sharpe:.2f}" if risk else "N/A"),
    ]
    if risk:
        metric_rows += [
            ("Sortino", f"{risk.sortino:.2f}", "Beta", f"{risk.beta:.2f}"),
            ("Backtest CAGR", f"{risk.cagr:.1f}%", "VaR (95%)", f"{risk.var_95:.2f}%"),
            ("CVaR (95%)", f"{risk.cvar_95:.2f}%", "Volatility", f"{risk.volatility_annual:.1f}%"),
        ]
    return _metrics_table(metric_rows)


def _risk_metrics_table(risk: RiskMetrics, portfolio: Portfolio) -> list[list[str]]:
    """Risk metric detail table for Risk Analysis page."""
    return _metrics_table(
        [
            ("VaR (95%)", f"{risk.var_95:.2f}%", "CVaR (95%)", f"{risk.cvar_95:.2f}%"),
            ("Volatility", f"{risk.volatility_annual:.1f}%", "Backtest CAGR", f"{risk.cagr:.1f}%"),
            ("Max Drawdown", f"{risk.max_drawdown:.1f}%", "Total Return", f"{risk.total_return:.1f}%"),
            ("Sortino", f"{risk.sortino:.2f}", "Beta", f"{risk.beta:.2f}"),
            ("VaR (99%)", f"{risk.var_99:.2f}%", "Correlation", f"{risk.correlation_to_benchmark:.2f}"),
            ("Stock Count", str(portfolio.holding_count), "Sharpe", f"{risk.sharpe:.2f}"),
            ("Calmar Ratio", f"{risk.calmar_ratio:.2f}", "Treynor Ratio", f"{risk.treynor_ratio:.2f}"),
            ("Skewness", f"{risk.skewness:.3f}", "Excess Kurtosis", f"{risk.kurtosis_excess:.3f}"),
        ]
    )


# ── Chart figure builders (return Figure objects) ──


def _cover_banner(portfolio: Portfolio, plt) -> Figure | None:
    """Navy header block with title, portfolio name, and date."""
    if plt is None:
        return None
    fig, ax = plt.subplots(figsize=(6.3, 2.2))
    ax.set_xlim(0, 6.3)
    ax.set_ylim(0, 2.2)
    ax.axis("off")

    navy = (25 / 255, 60 / 255, 120 / 255)
    ax.add_patch(plt.Rectangle((0, 0.3), 6.3, 1.9, facecolor=navy, edgecolor="none"))
    ax.text(
        3.15,
        1.9,
        "NSE Portfolio Risk Report",
        ha="center",
        va="center",
        fontsize=20,
        fontweight="bold",
        color="white",
    )
    ax.text(3.15, 1.4, portfolio.name, ha="center", va="center", fontsize=13, color="white")
    ax.text(
        3.15,
        0.95,
        datetime.now().strftime("%d %B %Y"),
        ha="center",
        va="center",
        fontsize=9,
        fontstyle="italic",
        color="#bbbbbb",
    )

    fig.tight_layout()
    return fig


def _gauge(risk: RiskMetrics | None, plt) -> Figure | None:
    """Risk gauge bar with marker and LOW/MOD/HIGH zones."""
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
    """Sector pie chart + holdings weight bar as two subplots side by side."""
    if plt is None:
        return None
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.3, 2.5))

    # ── Left: Sector pie ──
    if sector_data:
        labels = list(sector_data.keys())
        sizes = list(sector_data.values())
        colors = plt.cm.Set2.colors[: len(labels)]
        wedges, texts, autotexts = ax1.pie(
            sizes,
            labels=None,
            autopct="%1.0f%%",
            startangle=90,
            colors=colors,
            textprops={"fontsize": 7},
        )
        ax1.set_title("Sector Allocation", fontsize=10, fontweight="bold")
        ax1.legend(
            wedges,
            [f"{lab} ({s:.0f}%)" for lab, s in zip(labels, sizes, strict=False)],
            loc="center left",
            bbox_to_anchor=(1, 0.5),
            fontsize=6,
        )

    # ── Right: Holdings weight ──
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
        ax2.text(
            bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2, f"{w:.1f}%", va="center", fontsize=7
        )
    ax2.set_title("Top Holdings", fontsize=10, fontweight="bold")
    ax2.margins(x=0.15)

    fig.tight_layout()
    return fig


def _drawdown_chart(portfolio_cum: pd.Series, plt) -> Figure | None:
    """Red area chart of portfolio drawdown."""
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
    """Monte Carlo confidence interval visualization."""
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
        f"P(Profit): {mc_result.prob_profit:.1f}% | {mc_result.n_simulations:,} sims, "
        f"{mc_result.horizon_days}d horizon",
        ha="center",
        fontsize=6,
        color="#6b7280",
    )
    ax.set_title("Monte Carlo Projection", fontsize=10, fontweight="bold")
    fig.tight_layout()
    return fig


def _pnl_chart(df: pd.DataFrame, plt) -> Figure | None:
    """Horizontal bar chart of P&L per holding."""
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
        ax.text(
            px + (0.4 if px >= 0 else -0.4),
            bar.get_y() + bar.get_height() / 2,
            f"{val:+.1f}%",
            va="center",
            fontsize=7,
            ha="left" if px >= 0 else "right",
        )
    ax.set_title("Holdings P&L", fontsize=10, fontweight="bold")
    ax.margins(x=0.15)
    fig.tight_layout()
    return fig


def _risk_assessment_text(risk: RiskMetrics | None) -> tuple[str, tuple]:
    """Return (assessment_text, background_color_tuple) based on risk metrics."""
    if risk is None:
        return "Risk data not available.", (240, 245, 250)
    vol = risk.volatility_annual
    sharpe = risk.sharpe
    if vol < 15 and sharpe > 1.0:
        return "LOW — low volatility with strong risk-adjusted returns.", (220, 245, 220)
    elif vol < 25 or sharpe > 0.5:
        return "MODERATE — moderate volatility with adequate compensation for risk taken.", (255, 243, 205)
    else:
        return (
            "HIGH — elevated volatility with weak risk-adjusted returns. Consider defensive positioning.",
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
    """Generate a 4-page PDF report using pdf-studio.

    Layout:
      Page 1: Cover — banner figure, summary table, gauge, risk assessment
      Page 2: Executive Summary — metrics table, sector+weight charts
      Page 3: Risk Analysis — risk metrics table, drawdown, MC, recommendations
      Page 4: Holdings Breakdown — P&L chart, holdings table, disclaimer
    """
    if not _PDFSTUDIO_OK:
        raise ImportError("pdf-studio is required for PDF export — pip install pdf-studio")

    _, plt = _import_matplotlib()

    doc = Document()
    doc.set_header("NSE Portfolio Risk Report")

    # ════════════════════════════════════════════════════
    # PAGE 1 — COVER
    # ════════════════════════════════════════════════════

    banner = _cover_banner(portfolio, plt)
    if banner:
        doc.add_chart(banner, space_before=0, space_after=12)

    doc.add_paragraph("Portfolio Summary", style=_subtitle_style())
    doc.add_table(_cover_metrics(portfolio, risk))

    gauge_fig = _gauge(risk, plt)
    if gauge_fig:
        doc.add_chart(gauge_fig, space_before=12, space_after=16)

    if risk:
        text, bg_color = _risk_assessment_text(risk)
        doc.add_paragraph(
            f"Risk Level: {text}",
            Style(font=Font("Inter", 8, bold=True), space_before=4, space_after=2),
        )

    doc.add_paragraph(
        f"Report generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        style=_muted_style(),
    )
    doc.add_page_break()

    # ════════════════════════════════════════════════════
    # PAGE 2 — EXECUTIVE SUMMARY
    # ════════════════════════════════════════════════════

    doc.add_heading("1. Executive Summary", level=1)
    doc.add_paragraph("Portfolio-wide risk metrics at a glance.", style=_body_style())
    doc.add_paragraph("", style=_spacer(2))
    doc.add_table(_full_metrics(portfolio, risk))
    doc.add_paragraph("", style=_spacer(16))

    if risk:
        doc.add_paragraph(
            f"Annualised volatility of {risk.volatility_annual:.1f}% with a Sharpe ratio "
            f"of {risk.sharpe:.2f} indicates "
            f"{'strong' if risk.sharpe > 1 else 'adequate' if risk.sharpe > 0.5 else 'weak'} "
            f"risk-adjusted returns.",
            style=_body_style(),
        )

    sw_fig = _sector_weight_composite(sector_data, portfolio, plt)
    if sw_fig:
        doc.add_chart(sw_fig, space_before=12, space_after=16)
    doc.add_page_break()

    # ════════════════════════════════════════════════════
    # PAGE 3 — RISK ANALYSIS
    # ════════════════════════════════════════════════════

    doc.add_heading("2. Risk Analysis", level=1)
    doc.add_paragraph(
        "Detailed risk metrics, historical drawdown, and forward-looking simulation.", style=_body_style()
    )

    if risk:
        doc.add_paragraph("", style=_spacer(2))
        doc.add_table(_risk_metrics_table(risk, portfolio))
        doc.add_paragraph("", style=_spacer(16))

    if portfolio_cum is not None and not portfolio_cum.empty:
        dd_fig = _drawdown_chart(portfolio_cum, plt)
        if dd_fig:
            doc.add_chart(dd_fig, space_before=12, space_after=16)

    if mc_result:
        mc_fig = _monte_carlo_chart(mc_result, plt)
        if mc_fig:
            doc.add_chart(mc_fig, space_before=12, space_after=16)

    if recommendations and recommendations.priority_actions:
        doc.add_heading("Top Priority Actions", level=2)
        for rec in recommendations.priority_actions[:5]:
            doc.add_bullet(
                f"{rec.action.value.upper()} {rec.target}: {rec.reasoning} "
                f"({rec.urgency}, {rec.confidence:.0%} confidence)",
                style=_body_style(),
            )

    doc.add_page_break()

    # ════════════════════════════════════════════════════
    # PAGE 4 — HOLDINGS BREAKDOWN
    # ════════════════════════════════════════════════════

    doc.add_heading("3. Holdings Breakdown", level=1)
    doc.add_paragraph("Per-holding P&L and detailed position data.", style=_body_style())

    pnl_fig = _pnl_chart(df, plt)
    if pnl_fig:
        doc.add_chart(pnl_fig, space_before=12, space_after=16)

    # Build display table
    display_cols = ["Ticker", "Name", "Quantity", "Avg Price", "Current Price", "P&L %", "Sector"]
    display_df = df[display_cols].copy() if all(c in df.columns for c in display_cols) else df.copy()
    if "Name" in display_df.columns:
        display_df["Name"] = display_df["Name"].apply(lambda x: str(x)[:18] if pd.notna(x) else "")
    if "Quantity" in display_df.columns:
        display_df["Quantity"] = display_df["Quantity"].apply(lambda x: str(int(x)) if pd.notna(x) else "")
    if "P&L %" in display_df.columns:
        display_df["P&L %"] = display_df["P&L %"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "")
    # Quantity(2), Avg Price(3), Current Price(4), P&L %(5) — right-aligned
    doc.add_paragraph("", style=_spacer(2))
    doc.add_table(display_df, caption="Holdings Detail", right_align_cols=[2, 3, 4, 5])
    doc.add_paragraph("", style=_spacer(16))

    doc.add_paragraph(
        "Disclaimer: This report is for informational purposes only and does not "
        "constitute financial advice. Data sourced from public APIs (yfinance, NSE) "
        "may be delayed or inaccurate. Past performance is not indicative of future results. "
        "Consult a SEBI-registered advisor before making investment decisions.",
        style=_disclaimer_style(),
    )
    doc.add_paragraph(
        "Generated by NSE Portfolio Risk Scanner",
        style=_muted_style(),
    )

    # Render to bytes
    buf = BytesIO()
    doc.render(buf)
    buf.seek(0)
    return buf.read()
