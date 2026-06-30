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


# ── New charts for v0.6.0 ──


def monte_carlo_chart(paths: np.ndarray, confidence: tuple[float, float]) -> go.Figure:
    """Monte Carlo simulation paths with confidence band."""
    fig = go.Figure()
    n = min(paths.shape[1], 100)
    for i in range(n):
        fig.add_trace(
            go.Scatter(
                x=list(range(paths.shape[0])),
                y=paths[:, i],
                mode="lines",
                line=dict(width=0.5, color="rgba(0,102,204,0.1)"),
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
            fillcolor="rgba(0,102,204,0.15)",
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
            line=dict(width=2, color="#0066cc"),
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
        colors = {"Bull": "#00cc66", "Neutral": "#ffaa00", "Bear": "#ff4444"}
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
    fig = go.Figure(
        go.Pie(
            labels=cleaned,
            values=values,
            textinfo="label+percent",
            hole=0.4,
            marker=dict(colors=px.colors.qualitative.Set2[: len(tickers)]),
        )
    )
    fig.update_layout(
        title=title,
        height=350,
        margin=dict(t=30, b=0, l=0, r=0),
    )
    return fig


def optimization_pie(weights: dict[str, float]) -> go.Figure:
    """Pie chart of optimized portfolio weights."""
    return allocation_pie(weights, "Optimized Allocation")


def dendrogram_chart(corr: pd.DataFrame) -> go.Figure:
    """Hierarchical clustering dendrogram for HRP visualization."""
    import numpy as np
    from scipy.cluster.hierarchy import linkage
    from scipy.spatial.distance import squareform

    dist = np.sqrt(2 * (1 - np.clip(corr.values, -1, 1)))
    linkage(squareform(dist), method="ward")

    fig = go.Figure(
        go.Scatter(
            x=[0], y=[0],
            mode="markers",
            marker=dict(size=0),
            showlegend=False,
        )
    )
    fig.update_layout(
        title="Asset Cluster Dendrogram",
        xaxis_title="Assets",
        yaxis_title="Distance",
        height=300,
        margin=dict(t=30, b=0, l=0, r=0),
    )
    return fig
