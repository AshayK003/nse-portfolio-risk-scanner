"""
Plotly chart builders for the risk dashboard.
Thin presentation layer — no business logic, just chart config.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def sector_treemap(sector_allocation: dict[str, float]) -> go.Figure:
    """Treemap showing sector allocation."""
    labels = list(sector_allocation.keys())
    values = list(sector_allocation.values())

    fig = px.treemap(
        names=labels,
        parents=[""] * len(labels),
        values=values,
        color=values,
        color_continuous_scale="RdYlGn",
        title="Sector Allocation",
    )
    fig.update_traces(textinfo="label+percent root", hovertemplate="%{label}<br>%{value:.1f}%")
    fig.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=400)
    return fig


def drawdown_chart(drawdown_series: pd.Series) -> go.Figure:
    """Area chart of portfolio drawdown over time."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=drawdown_series.index,
            y=drawdown_series * 100,
            fill="tozeroy",
            fillcolor="rgba(255, 80, 80, 0.3)",
            line=dict(color="red", width=1),
            name="Drawdown",
            hovertemplate="%{x|%b %Y}<br>%{y:.1f}%",
        )
    )
    fig.update_layout(
        title="Portfolio Drawdown",
        yaxis_title="Drawdown (%)",
        xaxis_title="Date",
        hovermode="x unified",
        height=350,
        margin=dict(t=30, b=0, l=0, r=0),
    )
    fig.update_yaxes(zeroline=True, zerolinecolor="gray", zerolinewidth=1)
    return fig


def benchmark_chart(
    portfolio_cum: pd.Series,
    benchmark_cum: pd.Series,
) -> go.Figure:
    """Overlay line chart of portfolio vs benchmark cumulative returns."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=portfolio_cum.index,
            y=(portfolio_cum - 1) * 100,
            line=dict(color="#0066cc", width=2),
            name="Portfolio",
            hovertemplate="%{x|%b %Y}<br>%{y:.1f}%",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=benchmark_cum.index,
            y=(benchmark_cum - 1) * 100,
            line=dict(color="#ff6600", width=2, dash="dash"),
            name="Nifty 50",
            hovertemplate="%{x|%b %Y}<br>%{y:.1f}%",
        )
    )
    fig.update_layout(
        title="Portfolio vs Nifty 50",
        yaxis_title="Cumulative Return (%)",
        xaxis_title="Date",
        hovermode="x unified",
        height=350,
        margin=dict(t=30, b=0, l=0, r=0),
    )
    return fig


def correlation_heatmap(corr_matrix: pd.DataFrame) -> go.Figure:
    """Heatmap of holding correlations."""
    fig = px.imshow(
        corr_matrix,
        text_auto=".2f",
        color_continuous_scale="RdBu_r",
        aspect="auto",
        title="Correlation Matrix",
        zmin=-1,
        zmax=1,
    )
    fig.update_layout(height=400, margin=dict(t=30, b=0, l=0, r=0))
    return fig


def volatility_gauge(volatility: float) -> go.Figure:
    """Gauge chart for annualized volatility."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=volatility,
            title={"text": "Annual Volatility (%)"},
            gauge={
                "axis": {"range": [0, 80]},
                "bar": {"color": "#0066cc"},
                "steps": [
                    {"range": [0, 15], "color": "#d4f5d4"},
                    {"range": [15, 30], "color": "#fdf5d4"},
                    {"range": [30, 80], "color": "#f5d4d4"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 2},
                    "thickness": 0.75,
                    "value": volatility,
                },
            },
        )
    )
    fig.update_layout(height=250, margin=dict(t=30, b=0, l=0, r=0))
    return fig
