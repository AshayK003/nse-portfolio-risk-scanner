"""
Early-warning signal detection.

Detects technical, momentum, volatility, and correlation-based warning signals
from price data. Each signal includes severity, reasoning, and suggested response.
Pure functions — zero IO, zero Streamlit imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd


class SignalSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class WarningSignal:
    """A single early-warning signal."""

    name: str
    severity: SignalSeverity
    signal_type: str  # "technical", "momentum", "volatility", "correlation", "breadth"
    description: str
    reasoning: str  # causal explanation
    affected_holdings: list[str]  # tickers most affected
    suggested_action: str


@dataclass
class WarningReport:
    """Complete set of early-warning signals."""

    signals: list[WarningSignal]
    overall_warning_level: str  # "green", "amber", "red"
    signal_count_by_severity: dict[str, int]
    summary: str


def _detect_ma_crossover(
    prices: pd.DataFrame, short_window: int = 20, long_window: int = 50
) -> list[WarningSignal]:
    """Detect moving average crossover signals (death cross, golden cross)."""
    signals = []
    for col in prices.columns:
        if len(prices) < long_window + 5:
            continue
        short_ma = prices[col].rolling(short_window).mean()
        long_ma = prices[col].rolling(long_window).mean()

        # Check recent crossover (last 5 days)
        recent = 5
        if len(short_ma.dropna()) < recent or len(long_ma.dropna()) < recent:
            continue

        short_recent = short_ma.iloc[-recent:]
        long_recent = long_ma.iloc[-recent:]

        # Death cross: short MA crosses below long MA
        if (short_recent.iloc[-1] < long_recent.iloc[-1]) and (short_recent.iloc[-2] >= long_recent.iloc[-2]):
            ticker = col.replace(".NS", "")
            signals.append(
                WarningSignal(
                    name=f"Death Cross: {ticker}",
                    severity=SignalSeverity.WARNING,
                    signal_type="technical",
                    description=f"20-day MA crossed below 50-day MA for {ticker}",
                    reasoning="The 20-day moving average has fallen below the 50-day, indicating short-term "
                    "momentum has shifted negative. This is a classic bearish signal that often precedes "
                    "further downside. The stock's short-term trend has weakened relative to its medium-term trend.",
                    affected_holdings=[ticker],
                    suggested_action=f"Monitor {ticker} closely. Consider tightening stop-losses or reducing position size.",
                )
            )

        # Golden cross: short MA crosses above long MA
        if (short_recent.iloc[-1] > long_recent.iloc[-1]) and (short_recent.iloc[-2] <= long_recent.iloc[-2]):
            ticker = col.replace(".NS", "")
            signals.append(
                WarningSignal(
                    name=f"Golden Cross: {ticker}",
                    severity=SignalSeverity.INFO,
                    signal_type="technical",
                    description=f"20-day MA crossed above 50-day MA for {ticker}",
                    reasoning="The 20-day moving average has risen above the 50-day, indicating short-term "
                    "momentum has shifted positive. This is a bullish signal suggesting strengthening trend.",
                    affected_holdings=[ticker],
                    suggested_action=f"Positive signal for {ticker}. Current positioning is appropriate.",
                )
            )

    return signals


def _detect_rsi_extremes(prices: pd.DataFrame, period: int = 14) -> list[WarningSignal]:
    """Detect RSI overbought (>70) and oversold (<30) conditions."""
    signals = []
    for col in prices.columns:
        if len(prices) < period + 5:
            continue
        delta = prices[col].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        if rsi.empty or pd.isna(rsi.iloc[-1]):
            continue

        current_rsi = rsi.iloc[-1]
        ticker = col.replace(".NS", "")

        if current_rsi > 80:
            signals.append(
                WarningSignal(
                    name=f"Overbought: {ticker} (RSI {current_rsi:.0f})",
                    severity=SignalSeverity.WARNING,
                    signal_type="technical",
                    description=f"{ticker} is deeply overbought with RSI at {current_rsi:.0f}",
                    reasoning="RSI above 80 indicates extreme buying pressure. Historically, stocks with RSI > 80 "
                    "experience mean reversion within 5-10 trading days. The probability of a pullback increases "
                    "significantly at these levels.",
                    affected_holdings=[ticker],
                    suggested_action=f"Consider taking partial profits on {ticker} or tightening trailing stop-loss.",
                )
            )
        elif current_rsi > 70:
            signals.append(
                WarningSignal(
                    name=f"Overbought: {ticker} (RSI {current_rsi:.0f})",
                    severity=SignalSeverity.INFO,
                    signal_type="technical",
                    description=f"{ticker} is approaching overbought territory with RSI at {current_rsi:.0f}",
                    reasoning="RSI above 70 suggests the stock may be due for a consolidation or pullback.",
                    affected_holdings=[ticker],
                    suggested_action=f"Monitor {ticker} for signs of reversal.",
                )
            )
        elif current_rsi < 20:
            signals.append(
                WarningSignal(
                    name=f"Deeply Oversold: {ticker} (RSI {current_rsi:.0f})",
                    severity=SignalSeverity.WARNING,
                    signal_type="technical",
                    description=f"{ticker} is deeply oversold with RSI at {current_rsi:.0f}",
                    reasoning="RSI below 20 indicates extreme selling pressure. While this can signal further downside, "
                    "it also presents potential mean-reversion opportunity. However, oversold conditions can persist "
                    "in strong downtrends.",
                    affected_holdings=[ticker],
                    suggested_action=f"Evaluate if {ticker}'s decline is fundamental or sentiment-driven before accumulating.",
                )
            )
        elif current_rsi < 30:
            signals.append(
                WarningSignal(
                    name=f"Oversold: {ticker} (RSI {current_rsi:.0f})",
                    severity=SignalSeverity.INFO,
                    signal_type="technical",
                    description=f"{ticker} is approaching oversold territory with RSI at {current_rsi:.0f}",
                    reasoning="RSI below 30 suggests the stock may be nearing a bounce, but caution is warranted in strong downtrends.",
                    affected_holdings=[ticker],
                    suggested_action=f"Watch for volume confirmation before considering entry on {ticker}.",
                )
            )

    return signals


def _detect_volatility_regime_shift(
    returns: pd.DataFrame, short_window: int = 21, long_window: int = 63
) -> list[WarningSignal]:
    """Detect sudden volatility regime shifts (vol spike or compression)."""
    signals = []
    if returns.empty or len(returns) < long_window + short_window:
        return signals

    for col in returns.columns:
        stock_returns = returns[col]
        recent_vol = stock_returns.iloc[-short_window:].std() * np.sqrt(252)
        historical_vol = stock_returns.iloc[-long_window:-short_window].std() * np.sqrt(252)

        if historical_vol == 0:
            continue

        vol_ratio = recent_vol / historical_vol
        ticker = col.replace(".NS", "")

        if vol_ratio > 2.0:
            signals.append(
                WarningSignal(
                    name=f"Volatility Spike: {ticker}",
                    severity=SignalSeverity.CRITICAL,
                    signal_type="volatility",
                    description=f"{ticker} volatility has more than doubled ({vol_ratio:.1f}x historical)",
                    reasoning=f"Recent 21-day volatility ({recent_vol:.1%}) is {vol_ratio:.1f}x the 63-day historical "
                    f"volatility ({historical_vol:.1%}). This indicates a regime shift — the stock is experiencing "
                    f"abnormally large price swings. Such spikes often precede further instability or mark "
                    f"the beginning of a larger trend change.",
                    affected_holdings=[ticker],
                    suggested_action=f"URGENT: Review {ticker} position. Consider reducing size or hedging with options.",
                )
            )
        elif vol_ratio > 1.5:
            signals.append(
                WarningSignal(
                    name=f"Elevated Volatility: {ticker}",
                    severity=SignalSeverity.WARNING,
                    signal_type="volatility",
                    description=f"{ticker} volatility is elevated ({vol_ratio:.1f}x historical)",
                    reasoning=f"Recent volatility has increased to {vol_ratio:.1f}x its historical norm. This suggests "
                    f"the stock is entering a more turbulent phase.",
                    affected_holdings=[ticker],
                    suggested_action=f"Monitor {ticker} for further volatility expansion. Adjust position sizing if needed.",
                )
            )
        elif vol_ratio < 0.5:
            signals.append(
                WarningSignal(
                    name=f"Volatility Compression: {ticker}",
                    severity=SignalSeverity.INFO,
                    signal_type="volatility",
                    description=f"{ticker} volatility is unusually compressed ({vol_ratio:.1f}x historical)",
                    reasoning="Low volatility often precedes large moves (either direction). Bollinger Band squeeze patterns "
                    "form during these periods. The market is 'coiling' for a breakout.",
                    affected_holdings=[ticker],
                    suggested_action=f"Prepare for potential breakout in {ticker}. Set alerts for volume and price breakouts.",
                )
            )

    return signals


def _detect_correlation_breakdown(corr_matrix: pd.DataFrame, threshold: float = 0.7) -> list[WarningSignal]:
    """Detect unusually high correlations between holdings (diversification failure)."""
    signals = []
    if corr_matrix.empty or corr_matrix.shape[0] < 2:
        return signals

    n = corr_matrix.shape[0]
    high_corr_pairs = []

    for i in range(n):
        for j in range(i + 1, n):
            corr_val = corr_matrix.iloc[i, j]
            if abs(corr_val) > threshold:
                t1 = corr_matrix.index[i].replace(".NS", "")
                t2 = corr_matrix.columns[j].replace(".NS", "")
                high_corr_pairs.append((t1, t2, corr_val))

    if len(high_corr_pairs) > n * (n - 1) / 4:  # >25% of pairs are highly correlated
        pairs_str = ", ".join(f"{t1}-{t2} ({c:.2f})" for t1, t2, c in high_corr_pairs[:5])
        signals.append(
            WarningSignal(
                name="Correlation Breakdown",
                severity=SignalSeverity.WARNING,
                signal_type="correlation",
                description=f"{len(high_corr_pairs)}/{n * (n - 1) // 2} holding pairs have correlation > {threshold}",
                reasoning=f"High correlation across holdings means the portfolio is less diversified than it appears. "
                f"During market stress, correlations tend to spike toward 1.0, meaning all positions will "
                f"move in the same direction simultaneously. Key correlated pairs: {pairs_str}",
                affected_holdings=[t for t, _, _ in high_corr_pairs[:5]],
                suggested_action="Add uncorrelated assets (gold, international equities, or defensive sectors) to reduce correlation risk.",
            )
        )

    return signals


def _detect_momentum_divergence(
    prices: pd.DataFrame, short_window: int = 21, long_window: int = 63
) -> list[WarningSignal]:
    """Detect momentum divergences between price trend and recent performance."""
    signals = []
    if prices.empty or len(prices) < long_window + 5:
        return signals

    for col in prices.columns:
        stock_prices = prices[col]
        # Short-term momentum (1 month)
        short_return = (
            (stock_prices.iloc[-1] / stock_prices.iloc[-short_window] - 1)
            if len(stock_prices) >= short_window
            else 0
        )
        # Medium-term momentum (3 months)
        long_return = (
            (stock_prices.iloc[-1] / stock_prices.iloc[-long_window] - 1)
            if len(stock_prices) >= long_window
            else 0
        )

        ticker = col.replace(".NS", "")

        # Divergence: short-term down while medium-term up (potential reversal)
        if short_return < -0.05 and long_return > 0.1:
            signals.append(
                WarningSignal(
                    name=f"Momentum Divergence: {ticker}",
                    severity=SignalSeverity.WARNING,
                    signal_type="momentum",
                    description=f"{ticker}: 1-month return {short_return:.1%} vs 3-month {long_return:.1%}",
                    reasoning="The stock's short-term momentum has turned negative while medium-term trend remains positive. "
                    "This divergence often precedes trend reversals. The stock may be rolling over from its recent high.",
                    affected_holdings=[ticker],
                    suggested_action=f"Review {ticker}'s fundamental thesis. Consider reducing position if the divergence widens.",
                )
            )
        # Extreme negative momentum
        elif long_return < -0.2:
            signals.append(
                WarningSignal(
                    name=f"Severe Downtrend: {ticker}",
                    severity=SignalSeverity.CRITICAL,
                    signal_type="momentum",
                    description=f"{ticker} has fallen {long_return:.1%} over 3 months",
                    reasoning="A 20%+ decline over 3 months indicates sustained selling pressure. This could be "
                    "fundamental (earnings deterioration, sector headwinds) or technical (institutional unwinding). "
                    "Without a clear catalyst for reversal, downtrends tend to persist.",
                    affected_holdings=[ticker],
                    suggested_action=f"URGENT: Fundamental review of {ticker} required. Consider stopping loss if thesis is broken.",
                )
            )

    return signals


def detect_all_warnings(
    prices: pd.DataFrame,
    returns: pd.DataFrame | None = None,
    corr_matrix: pd.DataFrame | None = None,
) -> WarningReport:
    """
    Run all early-warning detectors and compile a comprehensive warning report.

    Checks:
    1. Moving average crossovers (death/golden cross)
    2. RSI overbought/oversold extremes
    3. Volatility regime shifts
    4. Correlation breakdown (diversification failure)
    5. Momentum divergences

    Args:
        prices: Daily closing prices
        returns: Daily returns (computed if not provided)
        corr_matrix: Correlation matrix (computed if not provided)

    Returns:
        WarningReport with all detected signals
    """
    if prices.empty:
        return _empty_warning_report()

    if returns is None:
        returns = prices.pct_change().dropna()
    if corr_matrix is None:
        corr_matrix = returns.corr()

    all_signals = []
    all_signals.extend(_detect_ma_crossover(prices))
    all_signals.extend(_detect_rsi_extremes(prices))
    all_signals.extend(_detect_volatility_regime_shift(returns))
    all_signals.extend(_detect_correlation_breakdown(corr_matrix))
    all_signals.extend(_detect_momentum_divergence(prices))

    # Count by severity
    severity_counts = {"info": 0, "warning": 0, "critical": 0}
    for sig in all_signals:
        severity_counts[sig.severity.value] = severity_counts.get(sig.severity.value, 0) + 1

    # Overall warning level
    if severity_counts["critical"] > 0:
        overall = "red"
    elif severity_counts["warning"] > 0:
        overall = "amber"
    else:
        overall = "green"

    # Summary
    critical = severity_counts["critical"]
    warnings = severity_counts["warning"]
    infos = severity_counts["info"]
    parts = []
    if critical > 0:
        parts.append(f"{critical} critical signal(s) require immediate attention.")
    if warnings > 0:
        parts.append(f"{warnings} warning(s) should be monitored closely.")
    if infos > 0:
        parts.append(f"{infos} informational signal(s) detected.")
    if not parts:
        parts.append("No early-warning signals detected. Portfolio appears stable.")

    return WarningReport(
        signals=all_signals,
        overall_warning_level=overall,
        signal_count_by_severity=severity_counts,
        summary=" ".join(parts),
    )


def _empty_warning_report() -> WarningReport:
    return WarningReport(
        signals=[],
        overall_warning_level="green",
        signal_count_by_severity={"info": 0, "warning": 0, "critical": 0},
        summary="No price data available for signal detection.",
    )
