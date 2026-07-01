"""
Plotly chart builders for the risk dashboard.
Thin presentation layer — no business logic, just chart config.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def sector_treemap(sector_allocation: dict[str, float]) -> go.Figure:
    """Treemap showing sector allocation."""
    labels = list(sector_allocation.keys())
    values = list(sector_allocation.values())
    if not labels:
        fig = go.Figure()
        fig.update_layout(title="Sector Allocation — no data")
        return fig

    fig = px.treemap(
        names=labels,
        parents=[""] * len(labels),
        values=values,
        color=values,
        color_continuous_scale=["#29c76a", "#eab308", "#ef4444"],
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
            fillcolor="rgba(239, 68, 68, 0.20)",
            line=dict(color="#ef4444", width=1.5),
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
            line=dict(color="#29c76a", width=2.5),
            name="Portfolio",
            hovertemplate="%{x|%b %Y}<br>%{y:.1f}%",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=benchmark_cum.index,
            y=(benchmark_cum - 1) * 100,
            line=dict(color="#6b7280", width=2, dash="dash"),
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
    if corr_matrix.empty:
        fig = go.Figure()
        fig.update_layout(title="Correlation Matrix — no data")
        return fig
    fig = px.imshow(
        corr_matrix,
        text_auto=".2f",
        color_continuous_scale=["#29c76a", "#f1f5f9", "#ef4444"],
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
                "bar": {"color": "#ef4444"},
                "steps": [
                    {"range": [0, 15], "color": "rgba(41,199,106,0.2)"},
                    {"range": [15, 30], "color": "rgba(234,179,8,0.2)"},
                    {"range": [30, 80], "color": "rgba(239,68,68,0.2)"},
                ],
                "threshold": {
                    "line": {"color": "#dc2626", "width": 2},
                    "thickness": 0.75,
                    "value": volatility,
                },
            },
        )
    )
    fig.update_layout(height=250, margin=dict(t=30, b=0, l=0, r=0))
    return fig


# ── New charts for v0.6.0 ──


def monte_carlo_chart(paths: np.ndarray, confidence: tuple[float, float]) -> go.Figure:
    """Monte Carlo simulation paths with confidence band."""
    fig = go.Figure()
    if paths.ndim < 2 or paths.shape[1] == 0 or paths.shape[0] == 0:
        fig.update_layout(title="Monte Carlo — no data")
        return fig
    n = min(paths.shape[1], 100)
    for i in range(n):
        fig.add_trace(
            go.Scatter(
                x=list(range(paths.shape[0])),
                y=paths[:, i],
                mode="lines",
                line=dict(width=0.5, color="rgba(41,199,106,0.08)"),
                showlegend=False,
                hovertemplate="%{y:.1f}",
            )
        )
    median = np.median(paths, axis=1)
    lower = np.percentile(paths, 5, axis=1)
    upper = np.percentile(paths, 95, axis=1)
    fig.add_trace(
        go.Scatter(
            x=list(range(paths.shape[0])),
            y=upper,
            mode="lines",
            line=dict(width=0, color="rgba(0,0,0,0)"),
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=list(range(paths.shape[0])),
            y=lower,
            fill="tonexty",
            fillcolor="rgba(41,199,106,0.12)",
            mode="lines",
            line=dict(width=0, color="rgba(0,0,0,0)"),
            name="5th-95th percentile",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=list(range(paths.shape[0])),
            y=median,
            mode="lines",
            line=dict(width=2, color="#29c76a"),
            name="Median",
            hovertemplate="Day %{x}<br>%{y:.1f}",
        )
    )
    fig.update_layout(
        title="Monte Carlo Projection (10,000 paths)",
        xaxis_title="Trading Days",
        yaxis_title="Portfolio Value (₹)",
        hovermode="x unified",
        height=400,
        margin=dict(t=30, b=0, l=0, r=0),
    )
    return fig


def regime_chart(returns: pd.Series, state_sequence: list, colors: dict | None = None) -> go.Figure:
    """Portfolio returns colored by market regime."""
    if colors is None:
        colors = {"Bull": "#29c76a", "Neutral": "#9ca3af", "Bear": "#ef4444"}
    fig = go.Figure()
    unique_states = sorted(set(state_sequence))
    for state in unique_states:
        mask = np.array([s == state for s in state_sequence])
        x = returns.index[mask]
        y = returns.values[mask]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="markers",
                marker=dict(color=colors.get(state, "#888"), size=3, opacity=0.6),
                name=state,
                hovertemplate="%{x|%b %Y}<br>%{y:.2f}%",
            )
        )
    fig.update_layout(
        title="Daily Returns by Market Regime",
        xaxis_title="Date",
        yaxis_title="Daily Return (%)",
        hovermode="x unified",
        height=350,
        margin=dict(t=30, b=0, l=0, r=0),
    )
    return fig


def allocation_pie(weights: dict[str, float], title: str = "Allocation") -> go.Figure:
    """Pie chart of portfolio weights."""
    tickers = list(weights.keys())
    values = list(weights.values())
    cleaned = [t.replace(".NS", "") for t in tickers]
    # Stock-market palette: greens, greys, muted reds
    stock_colors = ["#29c76a", "#6b7280", "#ef4444", "#eab308", "#8b5cf6",
                    "#14b8a6", "#f97316", "#3b82f6", "#ec4899", "#84cc16"]
    fig = go.Figure(
        go.Pie(
            labels=cleaned,
            values=values,
            textinfo="label+percent",
            hole=0.4,
            marker=dict(colors=stock_colors[: len(tickers)]),
        )
    )
    fig.update_layout(
        title=title,
        height=350,
        margin=dict(t=30, b=0, l=0, r=0),
    )
    return fig


