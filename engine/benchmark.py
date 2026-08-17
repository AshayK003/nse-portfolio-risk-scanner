"""
Benchmark comparison engine.
Compares portfolio returns against Nifty 50 or other benchmark indices.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import BenchmarkComparison

# Common NSE benchmark tickers for yfinance
BENCHMARK_TICKERS = {
    "NIFTY 50": "^NSEI",
    "NIFTY BANK": "^NSEBANK",
    "SENSEX": "^BSESN",
    "NIFTY IT": "^CNXIT",
    "NIFTY PHARMA": "^CNXPHARMA",
    "NIFTY AUTO": "^CNXAUTO",
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY METAL": "^CNXMETAL",
    "NIFTY ENERGY": "^CNXENERGY",
    "NIFTY REALTY": "^CNXREALTY",
    "NIFTY MIDCAP 100": "^CNXMIDCAP",
    "NIFTY SMALLCAP 100": "^CNXSC",
}


def compare_to_benchmark(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.065,
) -> BenchmarkComparison | None:
    """
    Compare portfolio performance against a benchmark index.

    Args:
        portfolio_returns: Daily returns series for the portfolio
        benchmark_returns: Daily returns series for the benchmark
        risk_free_rate: Indian risk-free rate (default 6.5%)

    Returns:
        BenchmarkComparison dataclass
    """
    # Ensure both series have correct names for proper alignment
    if portfolio_returns.name != "portfolio":
        portfolio_returns = portfolio_returns.copy()
        portfolio_returns.name = "portfolio"
    if benchmark_returns.name != "benchmark":
        benchmark_returns = benchmark_returns.copy()
        benchmark_returns.name = "benchmark"

    # Normalize timezone so a tz-aware benchmark (from yfinance on some
    # environments) still aligns on date with a tz-naive portfolio series.
    # Mismatched tz yields 0 overlapping rows -> meaningless comparison.
    if isinstance(portfolio_returns.index, pd.DatetimeIndex) and portfolio_returns.index.tz is not None:
        portfolio_returns = portfolio_returns.tz_localize(None)
    if isinstance(benchmark_returns.index, pd.DatetimeIndex) and benchmark_returns.index.tz is not None:
        benchmark_returns = benchmark_returns.tz_localize(None)

    # Align on dates
    aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1, join="inner").dropna()

    if len(aligned) < 5:
        # Not enough overlapping data to compute a meaningful comparison.
        # Return None so the UI shows an explicit "data unavailable" notice
        # instead of fake all-zero metrics (which an investor could misread).
        return None

    port_ret = aligned["portfolio"]
    bench_ret = aligned["benchmark"]

    # Total returns
    port_cum = (1 + port_ret).cumprod()
    bench_cum = (1 + bench_ret).cumprod()

    port_total_return = (port_cum.iloc[-1] - 1) * 100
    bench_total_return = (bench_cum.iloc[-1] - 1) * 100
    alpha_total = port_total_return - bench_total_return

    # Beta
    cov = port_ret.cov(bench_ret)
    var = bench_ret.var()
    beta = cov / var if var > 0 else 1.0

    # Correlation
    correlation = float(port_ret.corr(bench_ret))

    # Tracking error
    diff = port_ret - bench_ret
    tracking_error = diff.std() * np.sqrt(252) * 100

    # Information ratio
    information_ratio = (diff.mean() * 252) / (diff.std() * np.sqrt(252)) if diff.std() > 0 else 0.0

    # Rolling alpha (6-month)
    rolling_window = min(126, len(aligned) // 2)
    rolling_port = port_ret.rolling(rolling_window).mean() * 252
    rolling_bench = bench_ret.rolling(rolling_window).mean() * 252
    rolling_alpha = (rolling_port - rolling_bench).iloc[-1] * 100 if len(aligned) > rolling_window else 0.0

    # Monthly outperformance
    monthly_port = port_ret.resample("ME").apply(lambda x: (1 + x).prod() - 1)
    monthly_bench = bench_ret.resample("ME").apply(lambda x: (1 + x).prod() - 1)
    outperformance = (monthly_port > monthly_bench).sum()
    total_months = len(monthly_port)

    # Up/Down capture ratios
    # Up capture: portfolio return / benchmark return when benchmark > 0
    # Down capture: portfolio return / benchmark return when benchmark < 0
    up_mask = bench_ret > 0
    down_mask = bench_ret < 0
    up_capture = (port_ret[up_mask].mean() / bench_ret[up_mask].mean()) * 100 if up_mask.any() else 100.0
    down_capture = (
        (port_ret[down_mask].mean() / bench_ret[down_mask].mean()) * 100 if down_mask.any() else 100.0
    )

    return BenchmarkComparison(
        portfolio_return=round(port_total_return, 2),
        benchmark_return=round(bench_total_return, 2),
        alpha=round(alpha_total, 2),
        tracking_error=round(tracking_error, 2),
        information_ratio=round(information_ratio, 3),
        beta=round(beta, 2),
        correlation=round(correlation, 3),
        up_capture=round(up_capture, 2),
        down_capture=round(down_capture, 2),
        rolling_alpha_6m=round(rolling_alpha, 2),
        outperformance_months=int(outperformance),
        total_months=int(total_months),
        portfolio_returns=port_ret,
        benchmark_returns=bench_ret,
    )
