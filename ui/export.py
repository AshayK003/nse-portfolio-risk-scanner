"""
Report export — CSV download and PDF report generation.
Streamlit-dependent presentation layer; chart/render logic lives in charts_pdf.py.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from engine import Portfolio, RiskMetrics
from engine.recommendations import RecommendationReport
from engine.risk import MonteCarloResult
from ui.charts_pdf import _generate_pdf_report
from ui.icons import DOWNLOAD, icon_text


def _to_rich_csv(
    portfolio: Portfolio,
    risk: RiskMetrics | None = None,
    sector_data: dict | None = None,
    recommendations: RecommendationReport | None = None,
    risk_data: dict | None = None,
) -> bytes:
    """
    Build a rich multi-section CSV with portfolio summary, per-holding detail,
    sector allocation, and recommendations.
    """
    lines: list[str] = []

    # ── Section 1: Portfolio Summary ──
    lines.append("PORTFOLIO SUMMARY")
    lines.append(f"Name,{portfolio.name}")
    lines.append(f"Holdings,{portfolio.holding_count}")
    lines.append(f"Total Invested,{portfolio.total_invested:,.0f}")
    lines.append(f"Current Value,{portfolio.total_current:,.0f}")
    lines.append(f"P&L,{portfolio.total_pnl:+,.0f}")
    lines.append(f"P&L %,{portfolio.total_pnl_pct:+.2f}%")
    if risk:
        lines.append(f"Annual Volatility,{risk.volatility_annual:.1f}%")
        lines.append(f"Sharpe Ratio,{risk.sharpe:.2f}")
        lines.append(f"Sortino Ratio,{risk.sortino:.2f}")
        lines.append(f"Beta,{risk.beta:.2f}")
        lines.append(f"VaR (95%),{risk.var_95:.2f}%")
        lines.append(f"CVaR (95%),{risk.cvar_95:.2f}%")
        lines.append(f"Max Drawdown,{risk.max_drawdown:.1f}%")
        lines.append(f"Backtest CAGR,{risk.cagr:.1f}%")
        lines.append(f"Calmar Ratio,{risk.calmar_ratio:.2f}")
        lines.append(f"Treynor Ratio,{risk.treynor_ratio:.2f}")
        lines.append(f"Skewness,{risk.skewness:.3f}")
        lines.append(f"Excess Kurtosis,{risk.kurtosis_excess:.3f}")
    lines.append("")

    # ── Section 2: Holdings Detail ──
    lines.append("HOLDINGS")
    header = [
        "Ticker",
        "Name",
        "Quantity",
        "Avg Price",
        "Current Price",
        "Invested",
        "Current Value",
        "P&L",
        "P&L %",
        "Sector",
        "Weight %",
        "Volatility (Ann%)",
        "Beta",
    ]
    lines.append(",".join(header))

    vol_map = (risk_data or {}).get("volatility", {})
    beta_map = (risk_data or {}).get("beta", {})

    for h in portfolio.holdings:
        ticker = h.ticker.replace(".NS", "")
        weight = (h.current_value / portfolio.total_current * 100) if portfolio.total_current > 0 else 0
        vol = vol_map.get(h.ticker, "")
        beta = beta_map.get(h.ticker, "")
        row = [
            ticker,
            _esc(h.name or ""),
            str(h.quantity),
            f"{h.avg_price:.2f}",
            f"{h.current_price:.2f}",
            f"{h.invested_value:,.0f}",
            f"{h.current_value:,.0f}",
            f"{h.pnl:+,.0f}",
            f"{h.pnl_pct:+.2f}%",
            _esc(h.sector or ""),
            f"{weight:.1f}%",
            f"{vol:.1f}" if vol != "" else "",
            f"{beta:.2f}" if beta != "" else "",
        ]
        lines.append(",".join(row))
    lines.append("")

    # ── Section 3: Sector Allocation ──
    if sector_data:
        lines.append("SECTOR ALLOCATION")
        lines.append("Sector,Allocation %")
        for sec, pct in sorted(sector_data.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"{_esc(sec)},{pct:.1f}%")
        lines.append("")

    # ── Section 4: Recommendations ──
    if recommendations and recommendations.recommendations:
        lines.append("RECOMMENDATIONS")
        lines.append("Action,Target,Urgency,Confidence,Risk Reduction %,Reasoning")
        for rec in recommendations.recommendations:
            lines.append(
                f"{rec.action.value},{_esc(rec.target)},{rec.urgency},"
                f"{rec.confidence:.0%},{rec.expected_risk_reduction:.1f},"
                f"{_esc(rec.reasoning)}"
            )
        if recommendations.risk_reduction_potential > 0:
            lines.append(
                f"Total Risk Reduction Potential,,,,{recommendations.risk_reduction_potential:.1f}%,"
            )
        lines.append("")

    # ── Section 5: Risk Reduction Notice ──
    lines.append("NOTE")
    lines.append(
        "Risk reduction estimates are directional heuristics based on "
        "rule-of-thumb multipliers, not backtested or simulated forecasts. "
        "Past performance does not guarantee future results."
    )
    lines.append(
        "This tool does not provide investment advice. "
        "The creator is not a SEBI-registered investment advisor."
    )
    lines.append("")

    return "\r\n".join(lines).encode("utf-8-sig")


def _esc(val: str) -> str:
    """Escape a value for CSV — wrap in quotes if it contains comma or newline."""
    if "," in val or "\n" in val or '"' in val:
        escaped = val.replace('"', '""')
        return f'"{escaped}"'
    return val


def render_export_section(
    portfolio: Portfolio,
    risk: RiskMetrics | None = None,
    sector_data: dict | None = None,
    mc_result: MonteCarloResult | None = None,
    portfolio_cum: pd.Series | None = None,
    recommendations: RecommendationReport | None = None,
    risk_data: dict | None = None,
) -> None:
    """Display export buttons for the analysis results."""
    st.markdown(
        f'<div class="section-header">{icon_text(DOWNLOAD, "Export Report")}</div>',
        unsafe_allow_html=True,
    )

    # ── Rich CSV ──
    csv_bytes = _to_rich_csv(portfolio, risk, sector_data, recommendations, risk_data)
    st.download_button(
        label="Download CSV Report (Rich)",
        data=csv_bytes,
        file_name=f"portfolio_report_{portfolio.name.replace(' ', '_')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # ── PDF ──
    # Build the legacy holdings DataFrame for the PDF generator
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

    try:
        with st.spinner("Generating PDF report..."):
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
        st.caption("PDF export uses pdf-studio (ReportLab backend)")
    except Exception as e:
        st.error(f"PDF generation failed: {e}")

    st.caption(
        "CSV report includes portfolio summary, per-holding risk metrics, "
        "sector allocation, and recommendation details — structured for "
        "further analysis in Excel/Sheets."
    )
