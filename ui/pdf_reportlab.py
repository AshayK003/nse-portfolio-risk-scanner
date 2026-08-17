"""Self-contained PDF report generator using reportlab directly.

Aesthetic parity with the `pdf-studio` library's "ledger" theme:
deep-green foundation (#064E3B), gold accent (#B45309), light-green surface
(#F0FDF4), Lora-Bold display headings, Inter body. Charts carry the same
chrome (white canvas, green titles, light-green grid, theme series palette).

This keeps the dependency graph flat (only reportlab + matplotlib, both
installable cleanly anywhere) while matching the brand look the user expects.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from threading import Lock

import numpy as np
import pandas as pd

# matplotlib guarded import — Figure is used only in type annotations
try:
    from matplotlib.figure import Figure

    _MATPLOTLIB_OK = True
except ImportError:
    Figure = None  # type: ignore[assignment, misc]
    _MATPLOTLIB_OK = False

from engine import BenchmarkComparison, Portfolio, RiskMetrics
from engine.factors import FactorRiskReport, MacroDriver
from engine.recommendations import RecommendationReport
from engine.regime import RegimeResult
from engine.risk import MonteCarloResult
from engine.scenario import MacroScenarioResult
from engine.scoring import InstitutionalRiskScores
from engine.warnings import WarningReport

# ── Ledger theme tokens (mirrors pdf_studio.themes.Theme.ledger) ──

FOUNDATION = "#064E3B"  # deep green — headings, table header
SURFACE = "#F0FDF4"  # light green — KPI card / zebra bg
BODY_TEXT = "#1F2937"
MUTED_TEXT = "#374151"
ACCENT = "#B45309"  # gold — rules, bullets, highlights
GOOD = "#047857"
BAD = "#B91C1C"
GRID = "#D1FAE5"  # light green gridlines / borders
SERIES = [FOUNDATION, ACCENT, "#0F766E", MUTED_TEXT, "#166534"]


# ── Font registration (Lora headings + Inter body) ──

_FONT_DIR = Path(__file__).parent / "fonts"
_FONTS_REGISTERED = False
_FONT_LOCK = Lock()

_BUILTIN_FONTS = {
    "Inter": "Inter-Regular.ttf",
    "Inter-Bold": "Inter-Bold.ttf",
    "Lora": "Lora-Regular.ttf",
    "Lora-Bold": "Lora-Bold.ttf",
}


def _register_fonts() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    with _FONT_LOCK:
        if _FONTS_REGISTERED:
            return
        from reportlab.lib.fonts import addMapping
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        for reg_name, filename in _BUILTIN_FONTS.items():
            ttf = _FONT_DIR / filename
            if ttf.exists():
                pdfmetrics.registerFont(TTFont(reg_name, str(ttf)))

        addMapping("Inter", 0, 0, "Inter")
        addMapping("Inter", 1, 0, "Inter-Bold")
        addMapping("Lora", 0, 0, "Lora")
        addMapping("Lora", 1, 0, "Lora-Bold")
        _FONTS_REGISTERED = True


# Register the same TTFs with matplotlib so chart text uses Inter/Lora
_MPL_FONTS_REGISTERED = False
_MPL_FONT_LOCK = Lock()

_MPL_FONT_FILES = {
    "Inter": "Inter-Regular.ttf",
    "Inter-Bold": "Inter-Bold.ttf",
    "Lora": "Lora-Regular.ttf",
    "Lora-Bold": "Lora-Bold.ttf",
}


def _register_mpl_fonts():
    global _MPL_FONTS_REGISTERED
    if _MPL_FONTS_REGISTERED:
        return
    with _MPL_FONT_LOCK:
        if _MPL_FONTS_REGISTERED:
            return
        try:
            import matplotlib.font_manager as fm

            for _, filename in _MPL_FONT_FILES.items():
                ttf = _FONT_DIR / filename
                if ttf.exists():
                    fm.fontManager.addfont(str(ttf))
        except Exception:
            pass
        _MPL_FONTS_REGISTERED = True


# ── Matplotlib helpers ─────────────────────────────────────────────


def _import_matplotlib():
    """Lazy-import matplotlib with Agg backend. Returns (matplotlib, pyplot) or (None, None)."""
    try:
        import matplotlib
        import matplotlib.pyplot as plt

        matplotlib.use("Agg")
        _register_mpl_fonts()
        try:
            matplotlib.rcParams["font.family"] = "Inter"
            matplotlib.rcParams["font.sans-serif"] = ["Inter"]
        except Exception:
            pass
        return matplotlib, plt
    except ImportError:
        return None, None


def _base_chart_style(fig, ax, title=None, plt=None):
    """Apply pdf-studio brand chrome: white canvas, green title, light-green grid."""
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    if title:
        ax.set_title(title, color=FOUNDATION, fontsize=12, fontweight="bold", pad=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED_TEXT, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    return ax


def _cover_banner(portfolio: Portfolio, plt) -> Figure | None:
    if plt is None:
        return None
    fig, ax = plt.subplots(figsize=(6.3, 2.2))
    ax.set_xlim(0, 6.3)
    ax.set_ylim(0, 2.2)
    ax.axis("off")

    ax.add_patch(plt.Rectangle((0, 0.3), 6.3, 1.9, facecolor=FOUNDATION, edgecolor="none"))
    ax.text(
        3.15,
        1.9,
        "NSE Portfolio Risk Report",
        ha="center",
        va="center",
        fontsize=20,
        fontweight="bold",
        color="white",
        fontfamily="Lora",
    )
    ax.text(
        3.15, 1.4, portfolio.name, ha="center", va="center", fontsize=13, color="white", fontfamily="Inter"
    )
    ax.text(
        3.15,
        0.95,
        datetime.now().strftime("%d %B %Y"),
        ha="center",
        va="center",
        fontsize=9,
        fontstyle="italic",
        color="#bbbbbb",
        fontfamily="Inter",
    )
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
        c = GOOD if i < 15 else ACCENT if i < 30 else BAD
        ax.axvspan(i, i + 1, 0, 0.55, facecolor=c, alpha=0.5, ec="none")

    val = min(risk.volatility_annual, 80)
    ax.plot([val, val], [0, 0.7], color=FOUNDATION, linewidth=2, zorder=3)
    ax.plot(val, 0.7, marker="v", color=FOUNDATION, markersize=5, zorder=3)
    ax.text(
        val,
        -0.35,
        f"{risk.volatility_annual:.1f}%",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color=FOUNDATION,
        fontfamily="Inter",
    )
    ax.text(7.5, 0.65, "LOW", ha="center", fontsize=6, color=GOOD, fontweight="bold")
    ax.text(22.5, 0.65, "MOD", ha="center", fontsize=6, color=ACCENT, fontweight="bold")
    ax.text(55, 0.65, "HIGH", ha="center", fontsize=6, color=BAD, fontweight="bold")
    ax.set_title(
        "Annual Volatility", fontsize=9, fontweight="bold", pad=6, color=FOUNDATION, fontfamily="Inter"
    )
    fig.tight_layout()
    return fig


def _sector_weight_composite(sector_data: dict | None, portfolio: Portfolio, plt) -> Figure | None:
    if plt is None:
        return None
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.3, 2.5))

    if sector_data:
        labels = list(sector_data.keys())
        sizes = list(sector_data.values())
        colors = SERIES[: len(labels)]
        wedges, texts, autotexts = ax1.pie(
            sizes,
            labels=None,
            autopct="%1.0f%%",
            startangle=90,
            colors=colors,
            textprops={"fontsize": 7},
        )
        ax1.set_title("Sector Allocation", fontsize=10, fontweight="bold", color=FOUNDATION)
        ax1.legend(
            wedges,
            [f"{lab} ({s:.0f}%)" for lab, s in zip(labels, sizes, strict=False)],
            loc="center left",
            bbox_to_anchor=(1, 0.5),
            fontsize=6,
            labelcolor=MUTED_TEXT,
        )

    holdings = sorted(portfolio.holdings, key=lambda h: h.current_value, reverse=True)[:10]
    tickers = [h.ticker.replace(".NS", "") for h in holdings]
    total = portfolio.total_current or 1
    weights = [h.current_value / total * 100 for h in holdings]
    bars = ax2.barh(range(len(tickers)), weights, color=SERIES[0], height=0.6, zorder=3)
    ax2.set_yticks(range(len(tickers)))
    ax2.set_yticklabels(tickers, fontsize=7, color=MUTED_TEXT)
    ax2.set_xlabel("Weight (%)", fontsize=7, color=MUTED_TEXT)
    ax2.tick_params(axis="x", labelsize=6)
    for bar, w in zip(bars, weights, strict=False):
        ax2.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            f"{w:.1f}%",
            va="center",
            fontsize=7,
            color=FOUNDATION,
            fontweight="bold",
        )
    ax2.set_title("Top Holdings", fontsize=10, fontweight="bold", color=FOUNDATION)
    ax2.margins(x=0.15)
    _base_chart_style(fig, ax2)
    fig.tight_layout()
    return fig


def _drawdown_chart(portfolio_cum: pd.Series, plt) -> Figure | None:
    if plt is None:
        return None
    running_max = portfolio_cum.cummax()
    drawdown = (portfolio_cum - running_max) / running_max * 100

    fig, ax = plt.subplots(figsize=(6.3, 1.8))
    ax.fill_between(drawdown.index, drawdown.values, 0, color=BAD, alpha=0.2)
    ax.plot(drawdown.index, drawdown.values, color=BAD, linewidth=0.8)
    ax.axhline(0, color="black", linewidth=0.3)
    ax.set_title("Portfolio Drawdown", fontsize=10, fontweight="bold", color=FOUNDATION)
    ax.set_ylabel("Drawdown (%)", fontsize=8, color=MUTED_TEXT)
    ax.tick_params(axis="both", labelsize=7)
    _base_chart_style(fig, ax)
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
    ax.barh(
        0.5,
        ci_upper - ci_lower,
        left=ci_lower,
        height=0.25,
        color=ACCENT,
        alpha=0.2,
        ec=FOUNDATION,
        linewidth=0.5,
    )
    ax.plot(mc_result.expected_return, 0.5, "D", color=FOUNDATION, markersize=5, zorder=3)
    ax.text(
        mc_result.expected_return,
        0.75,
        f"Expected: {mc_result.expected_return:.1f}%",
        ha="center",
        fontsize=7,
        color=FOUNDATION,
        fontfamily="Inter",
    )
    ax.plot(mc_result.var_95, 0.25, "v", color=BAD, markersize=4, zorder=3)
    ax.text(
        mc_result.var_95,
        0.08,
        f"VaR 95%: {mc_result.var_95:.1f}%",
        ha="center",
        fontsize=6,
        color=BAD,
        fontfamily="Inter",
    )
    ax.text(
        0,
        -0.05,
        f"P(Profit): {mc_result.prob_profit:.1f}% | {mc_result.n_simulations:,} sims, "
        f"{mc_result.horizon_days}d horizon",
        ha="center",
        fontsize=6,
        color=MUTED_TEXT,
        fontfamily="Inter",
    )
    ax.set_title("Monte Carlo Projection", fontsize=10, fontweight="bold", color=FOUNDATION)
    fig.tight_layout()
    return fig


def _pnl_chart(df: pd.DataFrame, plt) -> Figure | None:
    if plt is None:
        return None
    top = df.iloc[df["P&L %"].abs().argsort()[::-1][:10]] if "P&L %" in df.columns else df.head(10)
    tickers = [t.replace(".NS", "") for t in top["Ticker"]]
    pnl_values = top["P&L %"].values

    fig, ax = plt.subplots(figsize=(6.3, max(1.5, len(tickers) * 0.3)))
    colors = [GOOD if v >= 0 else BAD for v in pnl_values]
    bars = ax.barh(range(len(tickers)), pnl_values, color=colors, height=0.55, zorder=3)
    ax.set_yticks(range(len(tickers)))
    ax.set_yticklabels(tickers, fontsize=8, color=MUTED_TEXT)
    ax.axvline(0, color="black", linewidth=0.4)
    ax.set_xlabel("P&L %", fontsize=8, color=MUTED_TEXT)
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
            color=FOUNDATION,
            fontweight="bold",
        )
    ax.set_title("Holdings P&L", fontsize=10, fontweight="bold", color=FOUNDATION)
    ax.margins(x=0.15)
    _base_chart_style(fig, ax)
    fig.tight_layout()
    return fig


# ── Risk assessment ────────────────────────────────────────────────


def _risk_assessment_text(risk: RiskMetrics | None) -> tuple[str, str]:
    if risk is None:
        return "Risk data not available.", "#F0FDF4"
    vol = risk.volatility_annual
    sharpe = risk.sharpe
    if vol < 15 and sharpe > 1.0:
        return "LOW — low volatility with strong risk-adjusted returns.", "#DCFCE7"
    elif vol < 25 or sharpe > 0.5:
        return "MODERATE — moderate volatility with adequate compensation for risk taken.", "#FEF3C7"
    else:
        return (
            "HIGH — elevated volatility with weak risk-adjusted returns. Consider defensive positioning.",
            "#FEE2E2",
        )


# ── PDF assembly with reportlab ────────────────────────────────────


def generate_pdf_report(
    portfolio: Portfolio,
    risk: RiskMetrics | None,
    sector_data: dict | None,
    df: pd.DataFrame,
    mc_result: MonteCarloResult | None = None,
    portfolio_cum: pd.Series | None = None,
    recommendations: RecommendationReport | None = None,
    benchmark: BenchmarkComparison | None = None,
    factor_risk: FactorRiskReport | None = None,
    macro_drivers: list[MacroDriver] | None = None,
    regime_result: RegimeResult | None = None,
    institutional_scores: InstitutionalRiskScores | None = None,
    scenario_results: list[MacroScenarioResult] | None = None,
    warning_report: WarningReport | None = None,
) -> bytes:
    """Generate an 8-page PDF report using reportlab, styled to pdf-studio's ledger theme."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    _register_fonts()
    _, plt = _import_matplotlib()
    if plt is None:
        raise ImportError("matplotlib is required for PDF chart rendering")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="NSE Portfolio Risk Report",
    )

    # Ledger-themed paragraph styles
    h1 = ParagraphStyle(
        "h1",
        fontName="Lora-Bold",
        fontSize=18,
        leading=21,
        spaceBefore=16,
        spaceAfter=10,
        textColor=colors.HexColor(FOUNDATION),
    )
    h2 = ParagraphStyle(
        "h2",
        fontName="Lora-Bold",
        fontSize=14,
        leading=16,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor(FOUNDATION),
    )
    body = ParagraphStyle(
        "body", fontName="Inter", fontSize=9, leading=13, spaceAfter=6, textColor=colors.HexColor(BODY_TEXT)
    )
    muted = ParagraphStyle(
        "muted",
        fontName="Inter",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor(MUTED_TEXT),
        alignment=TA_CENTER,
    )
    disclaimer = ParagraphStyle("disclaimer", parent=muted, fontSize=7, spaceBefore=10)
    kpi_label = ParagraphStyle(
        "kpi_label",
        fontName="Inter",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor(MUTED_TEXT),
        alignment=TA_CENTER,
    )
    kpi_value = ParagraphStyle(
        "kpi_value",
        fontName="Inter-Bold",
        fontSize=18,
        leading=20,
        textColor=colors.HexColor(FOUNDATION),
        alignment=TA_CENTER,
    )
    kpi_delta_up = ParagraphStyle(
        "kpi_delta_up",
        fontName="Inter-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor(GOOD),
        alignment=TA_CENTER,
    )
    kpi_delta_down = ParagraphStyle(
        "kpi_delta_down",
        fontName="Inter-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor(BAD),
        alignment=TA_CENTER,
    )

    def fig_to_img(fig, width=17 * cm):
        b = BytesIO()
        fig.savefig(b, format="png", dpi=150, bbox_inches="tight", facecolor="white")
        b.seek(0)
        img = Image(b, width=width, height=width * fig.get_size_inches()[1] / fig.get_size_inches()[0])
        plt.close(fig)
        return img

    def heading_rule(level_after=0):
        return HRFlowable(
            width="100%", thickness=0.6, color=colors.HexColor(ACCENT), spaceBefore=0, spaceAfter=10
        )

    def styled_metric_table(rows, col_widths, right_align=None, caption=None):
        """Two-column-pair metric table styled like pdf-studio."""
        data = [list(r) for r in rows]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        cmds = [
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (0, -1), "Inter"),
            ("FONTNAME", (2, 0), (2, -1), "Inter"),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor(MUTED_TEXT)),
            ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor(MUTED_TEXT)),
            ("FONTNAME", (1, 0), (1, -1), "Inter-Bold"),
            ("FONTNAME", (3, 0), (3, -1), "Inter-Bold"),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor(FOUNDATION)),
            ("TEXTCOLOR", (3, 0), (3, -1), colors.HexColor(FOUNDATION)),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor(GRID)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        t.setStyle(TableStyle(cmds))
        if caption:
            cap = Paragraph(caption, muted)
            return [cap, t]
        return t

    def kpi_row(cards):
        """Row of KPI cards (label/value/delta) — surface bg, gold hairline dividers."""
        label_cells, value_cells, delta_cells = [], [], []
        for c in cards:
            label_cells.append(Paragraph(str(c.get("label", "")), kpi_label))
            value_cells.append(Paragraph(str(c.get("value", "")), kpi_value))
            delta = c.get("delta")
            if delta is None:
                delta_cells.append(Paragraph("", kpi_label))
            elif str(delta).startswith("-"):
                delta_cells.append(Paragraph(str(delta), kpi_delta_down))
            else:
                delta_cells.append(Paragraph(str(delta), kpi_delta_up))
        data = [label_cells, value_cells, delta_cells]
        n = len(cards)
        col_widths = [17 * cm / n] * n
        t = Table(data, colWidths=col_widths)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(SURFACE)),
                    ("LINEBEFORE", (1, 0), (-1, -1), 0.5, colors.HexColor(GRID)),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(GRID)),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return t

    def holdings_table(display_df):
        header_style = ParagraphStyle(
            "th", fontName="Inter-Bold", fontSize=9, leading=11, textColor=colors.white
        )
        body_style = ParagraphStyle(
            "td", fontName="Inter", fontSize=9, leading=12, textColor=colors.HexColor(BODY_TEXT)
        )
        body_right = ParagraphStyle("tdr", parent=body_style, alignment=1)
        header = [Paragraph(str(c), header_style) for c in display_df.columns]
        body_rows = []
        for _, row in display_df.iterrows():
            cells = []
            for ci, val in enumerate(row):
                st = body_right if ci in (2, 3, 4, 5) else body_style
                cells.append(Paragraph(str(val), st))
            body_rows.append(cells)
        wrapped = [header] + body_rows
        col_widths = [2 * cm, 3.5 * cm, 1.8 * cm, 2 * cm, 2.2 * cm, 1.8 * cm, 2.2 * cm]
        t = Table(wrapped, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(FOUNDATION)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor(ACCENT)),
            ("GRID", (0, 1), (-1, -1), 0.5, colors.HexColor(GRID)),
            ("ALIGN", (2, 0), (5, -1), "RIGHT"),
        ]
        for i in range(1, len(wrapped)):
            bg = colors.HexColor(SURFACE) if i % 2 == 0 else colors.white
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
        t.setStyle(TableStyle(style_cmds))
        return t

    # ── Build flowables ────────────────────────────────────────────

    flow: list = []

    # PAGE 1 — COVER
    banner = _cover_banner(portfolio, plt)
    if banner:
        flow.append(fig_to_img(banner, width=17 * cm))
        flow.append(Spacer(1, 8))

    pnl_pct = f"{portfolio.total_pnl_pct:+.2f}%"
    pnl_val = f"Rs {portfolio.total_pnl:+,.0f}"
    kpi_cards = [
        {"label": "Holdings", "value": str(portfolio.holding_count)},
        {"label": "Total Invested", "value": f"Rs {portfolio.total_invested:,.0f}"},
        {"label": "Current Value", "value": f"Rs {portfolio.total_current:,.0f}"},
        {"label": "P&L", "value": f"{pnl_val}", "delta": pnl_pct},
    ]
    flow.append(kpi_row(kpi_cards))
    flow.append(Spacer(1, 10))

    gauge_fig = _gauge(risk, plt)
    if gauge_fig:
        flow.append(fig_to_img(gauge_fig, width=17 * cm))
        flow.append(Spacer(1, 6))

    if risk:
        text, bg = _risk_assessment_text(risk)
        rt = Table([[f"Risk Level: {text}"]], colWidths=[17 * cm])
        rt.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("FONTNAME", (0, 0), (-1, -1), "Inter-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        flow.append(rt)

    flow.append(Spacer(1, 6))
    flow.append(Paragraph(f"Report generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}", muted))
    flow.append(PageBreak())

    # PAGE 2 — EXECUTIVE SUMMARY
    flow.append(Paragraph("1. Executive Summary", h1))
    flow.append(heading_rule())
    flow.append(Paragraph("Portfolio-wide risk metrics at a glance.", body))

    full_rows = [
        ["Holdings", str(portfolio.holding_count), "Total Invested", f"Rs {portfolio.total_invested:,.0f}"],
        ["Current Value", f"Rs {portfolio.total_current:,.0f}", "P&L", pnl_val],
        ["P&L %", pnl_pct, "Sharpe", f"{risk.sharpe:.2f}" if risk else "N/A"],
    ]
    if risk:
        full_rows += [
            ["Sortino", f"{risk.sortino:.2f}", "Beta", f"{risk.beta:.2f}"],
            ["Backtest CAGR", f"{risk.cagr:.1f}%", "VaR (95%)", f"{risk.var_95:.2f}%"],
            ["CVaR (95%)", f"{risk.cvar_95:.2f}%", "Volatility", f"{risk.volatility_annual:.1f}%"],
        ]
    flow.append(styled_metric_table(full_rows, [4 * cm, 4.5 * cm, 4 * cm, 4.5 * cm]))
    flow.append(Spacer(1, 8))

    if risk:
        flow.append(
            Paragraph(
                f"Annualised volatility of {risk.volatility_annual:.1f}% with a Sharpe ratio "
                f"of {risk.sharpe:.2f} indicates "
                f"{'strong' if risk.sharpe > 1 else 'adequate' if risk.sharpe > 0.5 else 'weak'} "
                f"risk-adjusted returns.",
                body,
            )
        )

    sw_fig = _sector_weight_composite(sector_data, portfolio, plt)
    if sw_fig:
        flow.append(fig_to_img(sw_fig, width=17 * cm))
    flow.append(PageBreak())

    # PAGE 3 — RISK ANALYSIS
    flow.append(Paragraph("2. Risk Analysis", h1))
    flow.append(heading_rule())
    flow.append(
        Paragraph("Detailed risk metrics, historical drawdown, and forward-looking simulation.", body)
    )

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
        flow.extend(
            styled_metric_table(
                risk_rows, [4 * cm, 4.5 * cm, 4 * cm, 4.5 * cm], caption="Risk Metrics Detail"
            )
        )
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
        flow.append(heading_rule())
        for rec in recommendations.priority_actions[:5]:
            flow.append(
                Paragraph(
                    f"• {rec.action.value.upper()} {rec.target}: {rec.reasoning} "
                    f"({rec.urgency}, {rec.confidence:.0%} confidence)",
                    body,
                )
            )
    flow.append(PageBreak())

    # PAGE 4 — HOLDINGS BREAKDOWN
    flow.append(Paragraph("3. Holdings Breakdown", h1))
    flow.append(heading_rule())
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

    flow.append(holdings_table(display_df))
    flow.append(Spacer(1, 10))

    flow.append(PageBreak())

    # PAGE 5 — BENCHMARK COMPARISON
    if benchmark:
        flow.append(Paragraph("4. Benchmark Comparison", h1))
        flow.append(heading_rule())
        flow.append(Paragraph("Portfolio performance relative to Nifty 50 benchmark.", body))

        bench_rows = [
            ["Beta", f"{benchmark.beta:.2f}", "Alpha (ann.)", f"{benchmark.alpha:.2f}%"],
            [
                "Information Ratio",
                f"{benchmark.information_ratio:.2f}",
                "Tracking Error",
                f"{benchmark.tracking_error:.2f}%",
            ],
            ["Correlation", f"{benchmark.correlation:.2f}", "Up Capture", f"{benchmark.up_capture:.2f}%"],
            ["Down Capture", f"{benchmark.down_capture:.2f}%", "", ""],
        ]
        flow.extend(
            styled_metric_table(
                bench_rows, [4 * cm, 4.5 * cm, 4 * cm, 4.5 * cm], caption="Benchmark Comparison Metrics"
            )
        )
        flow.append(Spacer(1, 8))

        # Benchmark returns chart
        if benchmark.benchmark_returns is not None and benchmark.portfolio_returns is not None:
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(8.5, 3))
            ax.plot(
                benchmark.benchmark_returns.index,
                benchmark.benchmark_returns.cumsum(),
                label="Nifty 50",
                color=MUTED_TEXT,
                linewidth=1.5,
            )
            ax.plot(
                benchmark.portfolio_returns.index,
                benchmark.portfolio_returns.cumsum(),
                label="Portfolio",
                color=FOUNDATION,
                linewidth=1.5,
            )
            ax.set_title("Cumulative Returns: Portfolio vs Benchmark", fontsize=11, color=FOUNDATION)
            ax.set_xlabel("")
            ax.set_ylabel("Cumulative Return", color=MUTED_TEXT)
            ax.legend(frameon=False, loc="upper left")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.tick_params(colors=MUTED_TEXT)
            flow.append(fig_to_img(fig, width=17 * cm))
            flow.append(Spacer(1, 8))

    flow.append(PageBreak())

    # PAGE 6 — FACTOR RISK DECOMPOSITION
    if factor_risk:
        flow.append(Paragraph("5. Factor Risk Decomposition", h1))
        flow.append(heading_rule())
        flow.append(
            Paragraph("Risk attribution across systematic factors and idiosyncratic component.", body)
        )

        if factor_risk.factor_exposures:
            factor_rows = [["Factor", "Exposure", "Risk Contribution", "% of Total Risk"]]
            for name, exp in factor_risk.factor_exposures.items():
                contrib = factor_risk.factor_contributions.get(name, 0)
                pct = (contrib / factor_risk.specific_risk * 100) if factor_risk.specific_risk > 0 else 0
                factor_rows.append([name, f"{exp:.2f}", f"{contrib:.4f}", f"{pct:.1f}%"])
            total_risk = factor_risk.specific_risk + sum(factor_risk.factor_contributions.values())
            spec_pct = (factor_risk.specific_risk / total_risk * 100) if total_risk > 0 else 0
            factor_rows.append(
                ["Specific (Idiosyncratic)", "—", f"{factor_risk.specific_risk:.4f}", f"{spec_pct:.1f}%"]
            )
            flow.extend(
                styled_metric_table(
                    factor_rows,
                    [5 * cm, 3 * cm, 4.5 * cm, 4.5 * cm],
                    caption="Factor Exposures & Contributions",
                )
            )
            flow.append(Spacer(1, 8))

        if factor_risk.r_squared is not None:
            flow.append(
                Paragraph(
                    f"Model R²: {factor_risk.r_squared:.1%} — proportion of portfolio variance explained by factor model.",
                    body,
                )
            )
            flow.append(Spacer(1, 4))

    flow.append(PageBreak())

    # PAGE 7 — MACRO DRIVERS & SCENARIOS / INSTITUTIONAL SCORES & EARLY WARNINGS
    flow.append(Paragraph("6. Macro Drivers, Scenarios & Institutional Scores", h1))
    flow.append(heading_rule())

    # Macro Drivers
    if macro_drivers:
        flow.append(Paragraph("Macro Factor Sensitivities", h2))
        flow.append(heading_rule())
        flow.append(
            Paragraph("Portfolio sensitivity to key macroeconomic drivers (rolling regression).", body)
        )

        macro_rows = [["Driver", "Beta", "p-value", "Ann. Contribution"]]
        for md in macro_drivers:
            macro_rows.append([md.name, f"{md.beta:.3f}", f"{md.p_value:.3f}", f"{md.contribution:.2f}%"])
        flow.extend(
            styled_metric_table(
                macro_rows, [5 * cm, 3 * cm, 3 * cm, 5 * cm], caption="Macro Driver Sensitivities"
            )
        )
        flow.append(Spacer(1, 8))

    # Macro Scenarios
    if scenario_results:
        flow.append(Paragraph("Macro Stress Scenarios", h2))
        flow.append(heading_rule())
        flow.append(Paragraph("Portfolio impact under hypothetical macro scenarios.", body))

        scen_rows = [["Scenario", "Portfolio Return", "Benchmark Return", "VaR 95%", "CVaR 95%", "Max DD"]]
        for s in scenario_results:
            scen_rows.append(
                [
                    s.scenario_name,
                    f"{s.portfolio_return:.2f}%",
                    f"{s.benchmark_return:.2f}%",
                    f"{s.var_95:.2f}%",
                    f"{s.cvar_95:.2f}%",
                    f"{s.max_drawdown:.2f}%",
                ]
            )
        flow.extend(
            styled_metric_table(
                scen_rows,
                [3 * cm, 2.8 * cm, 2.8 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm],
                caption="Scenario Analysis",
            )
        )
        flow.append(Spacer(1, 8))

    # Institutional Scores
    if institutional_scores:
        flow.append(Paragraph("Institutional Risk Scores", h2))
        flow.append(heading_rule())
        flow.append(Paragraph("Multi-factor institutional scoring framework (higher = better).", body))

        score_rows = [
            [
                "Quality",
                f"{institutional_scores.quality:.1f}",
                "Momentum",
                f"{institutional_scores.momentum:.1f}",
            ],
            [
                "Value",
                f"{institutional_scores.value:.1f}",
                "Volatility",
                f"{institutional_scores.volatility:.1f}",
            ],
            ["Liquidity", f"{institutional_scores.liquidity:.1f}", "ESG", f"{institutional_scores.esg:.1f}"],
            ["Composite", f"{institutional_scores.composite:.1f}", "", ""],
        ]
        flow.extend(
            styled_metric_table(
                score_rows, [4 * cm, 4.5 * cm, 4 * cm, 4.5 * cm], caption="Institutional Scores"
            )
        )
        flow.append(Spacer(1, 8))

    # Early Warnings
    if warning_report and warning_report.warnings:
        flow.append(Paragraph("Early Warnings", h2))
        flow.append(heading_rule())
        flow.append(Paragraph("Automated risk flags from portfolio monitoring.", body))

        for w in warning_report.warnings[:8]:
            sev_color = BAD if w.severity == "high" else ACCENT if w.severity == "medium" else GOOD
            flow.append(
                Paragraph(
                    f'<font color="{sev_color}">• {w.severity.upper()}</font> {w.message}',
                    body,
                )
            )
        flow.append(Spacer(1, 8))

    flow.append(PageBreak())

    # PAGE 8 — REGIME ANALYSIS & ADVANCED METRICS
    flow.append(Paragraph("7. Regime Analysis & Advanced Metrics", h1))
    flow.append(heading_rule())

    if regime_result:
        flow.append(Paragraph("Market Regime Detection (HMM)", h2))
        flow.append(heading_rule())
        flow.append(
            Paragraph("Hidden Markov Model regime identification and transition probabilities.", body)
        )

        if regime_result.current_regime is not None:
            flow.append(Paragraph(f"Current Regime: {regime_result.current_regime}", body))
            flow.append(Spacer(1, 4))

        if regime_result.regime_probabilities:
            regime_rows = [["Regime", "Probability"]]
            for r, p in regime_result.regime_probabilities.items():
                regime_rows.append([str(r), f"{p:.1%}"])
            flow.extend(styled_metric_table(regime_rows, [5 * cm, 5 * cm], caption="Regime Probabilities"))
            flow.append(Spacer(1, 8))

        if regime_result.regime_returns:
            reg_ret_rows = [["Regime", "Ann. Return", "Ann. Volatility", "Sharpe"]]
            for r, ret in regime_result.regime_returns.items():
                reg_ret_rows.append(
                    [
                        str(r),
                        f"{ret.get('return', 0):.2f}%",
                        f"{ret.get('vol', 0):.2f}%",
                        f"{ret.get('sharpe', 0):.2f}",
                    ]
                )
            flow.extend(
                styled_metric_table(
                    reg_ret_rows, [4 * cm, 4 * cm, 4 * cm, 4 * cm], caption="Regime Performance"
                )
            )
            flow.append(Spacer(1, 8))

    # Advanced Metrics
    if risk:
        flow.append(Paragraph("Advanced Risk Metrics", h2))
        flow.append(heading_rule())

        # Z-score (Altman proxy)
        z_score = None
        if risk.volatility_annual > 0:
            z_score = (risk.total_return / 100) / (risk.volatility_annual / 100 / (252**0.5))

        # VaR Backtest (Kupiec)
        var_breaches = 0
        daily_returns = None
        if portfolio_cum is not None and len(portfolio_cum) > 1:
            daily_returns = portfolio_cum.pct_change().dropna()
            if len(daily_returns) > 0:
                var_threshold = -abs(risk.var_95 / 100)
                var_breaches = (daily_returns < var_threshold).sum()

        kupiec_p = "N/A"
        if var_breaches > 0 and daily_returns is not None and len(daily_returns) > 0:
            from scipy import stats

            expected = len(daily_returns) * 0.05
            if expected > 0:
                lr = -2 * (
                    var_breaches * np.log(expected / var_breaches)
                    + (len(daily_returns) - var_breaches)
                    * np.log((len(daily_returns) - expected) / (len(daily_returns) - var_breaches))
                )
                kupiec_p = f"{1 - stats.chi2.cdf(lr, 1):.3f}"

        # GARCH volatility forecast (1-day ahead)
        garch_forecast = "N/A"
        try:
            from arch import arch_model

            if portfolio_cum is not None and len(portfolio_cum) > 30:
                daily_ret = portfolio_cum.pct_change().dropna() * 100
                if len(daily_ret) > 30:
                    am = arch_model(daily_ret, vol="Garch", p=1, q=1, dist="normal")
                    res = am.fit(update_freq=0, disp="off")
                    garch_forecast = f"{np.sqrt(res.conditional_volatility.iloc[-1] ** 2):.3f}%"
        except Exception:
            pass

        adv_rows = [
            ["Altman Z-Score (portfolio proxy)", f"{z_score:.2f}" if z_score else "N/A"],
            ["VaR Backtest (Kupiec p-value)", kupiec_p],
            ["VaR Breaches (95%, 1y)", str(var_breaches) if var_breaches else "N/A"],
            ["GARCH(1,1) 1-day Vol Forecast", garch_forecast],
            ["Skewness", f"{risk.skewness:.3f}"],
            ["Excess Kurtosis", f"{risk.kurtosis_excess:.3f}"],
            ["Calmar Ratio", f"{risk.calmar_ratio:.2f}"],
            ["Treynor Ratio", f"{risk.treynor_ratio:.2f}"],
        ]
        flow.extend(styled_metric_table(adv_rows, [7 * cm, 7 * cm], caption="Advanced Metrics"))
        flow.append(Spacer(1, 8))

    # FINAL DISCLAIMER
    flow.append(
        Paragraph(
            "Disclaimer: This report is for informational purposes only and does not constitute financial advice. "
            "Data sourced from public APIs (yfinance, NSE) may be delayed or inaccurate. Past performance is not "
            "indicative of future results. Consult a SEBI-registered advisor before making investment decisions.",
            disclaimer,
        )
    )
    flow.append(Paragraph("Generated by NSE Portfolio Risk Scanner", muted))

    doc.build(flow)
    buf.seek(0)
    return buf.read()
