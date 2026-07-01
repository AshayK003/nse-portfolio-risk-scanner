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


def render_export_section(
    portfolio: Portfolio,
    risk: RiskMetrics | None = None,
    sector_data: dict | None = None,
    mc_result: MonteCarloResult | None = None,
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
        st.caption("PDF export requires fpdf2: pip install fpdf2")
    except Exception as e:
        st.error(f"PDF generation failed: {e}")

    st.caption("Reports include position-level data for further analysis in Excel/Sheets.")
