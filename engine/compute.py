"""
Computation pipeline for NSE Portfolio Risk Scanner.

Pure functions — zero Streamlit imports, zero side effects beyond logging.
All intelligence modules orchestrated via engine.intelligence_registry with
consistent error handling.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from data.prices import fetch_benchmark, fetch_prices, fetch_prices_refreshed
from engine import AnalysisReport, Portfolio
from engine.__init__ import RISK_PROFILES
from engine._log import logger
from engine.benchmark import compare_to_benchmark
from engine.fundamentals import compute_all_zscores
from engine.garch_var import estimate_garch_var
from engine.narrative import generate_narrative
from engine.optimization import (
    optimize_hrp,
    optimize_max_sharpe,
    optimize_min_volatility,
    suggest_rebalance,
)
from engine.optimization_advanced import optimize_advanced
from engine.pelve import compute_pelve
from engine.performance import compute_portfolio_returns
from engine.portfolio import validate_portfolio
from engine.regime import detect_regimes
from engine.risk import (
    compute_correlation_matrix,
    compute_risk_metrics,
    denoise_correlation,
    monte_carlo_simulation,
)
from engine.scenario import run_default_scenarios
from engine.sector import classify_holdings, compute_sector_exposure, load_sector_map


@dataclass
class ComputeContext:
    """All intermediate values needed for rendering."""

    prices: pd.DataFrame
    portfolio_returns: pd.Series
    portfolio_cum: pd.Series
    benchmark_returns: pd.Series | None
    benchmark_cum: pd.Series
    raw_corr: pd.DataFrame
    denoised_corr: pd.DataFrame | None
    mc_paths: np.ndarray | None
    stock_betas: dict[str, float]
    scenarios: list
    rebalance: object | None
    risk: object
    sector: object
    benchmark: object | None
    opt_result: object | None
    mc_result: object | None
    regime_result: object | None
    factor_report: object | None
    macro_drivers: object | None
    macro_scenarios: list
    institutional_scores: object | None
    early_warnings: object | None
    recommendations: object | None
    zscore: object | None
    var_backtest: object | None
    garch_var: object | None
    pelve: object | None
    opt_advanced: object | None
    weights: list[float]
    portfolio: Portfolio
    benchmark_choice: str
    risk_profile_key: str
    risk_free_rate: float
    profile: object
    narrative: str


def compute_input_hash(
    portfolio: Portfolio,
    benchmark: str,
    risk_profile: str,
    risk_free_rate: float,
) -> str:
    """Generate deterministic hash for cache invalidation (public, used by orchestrator)."""
    return _input_hash(portfolio, benchmark, risk_profile, risk_free_rate)


def _input_hash(
    portfolio: Portfolio,
    benchmark: str,
    risk_profile: str,
    risk_free_rate: float,
) -> str:
    """Generate deterministic hash for cache invalidation."""
    return hashlib.sha256(
        json.dumps(
            {
                "holdings": [(h.ticker, h.quantity, h.avg_price) for h in portfolio.holdings],
                "benchmark": benchmark,
                "risk_profile": risk_profile,
                "risk_free_rate": round(risk_free_rate, 4),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:16]


def _fetch_prices(portfolio: Portfolio, force_refresh: bool) -> pd.DataFrame:
    """Fetch prices with error handling."""
    if force_refresh:
        return fetch_prices_refreshed(portfolio.holdings, period="1y")
    return fetch_prices(portfolio.holdings, period="1y")


def _align_portfolio(portfolio: Portfolio, prices: pd.DataFrame) -> Portfolio:
    """Remove holdings with missing or zero price data."""
    clean = [h for h in portfolio.holdings if h.ticker in prices.columns and h.current_price > 0.0]
    return Portfolio(holdings=clean, name=portfolio.name)


def _fetch_benchmark(benchmark_choice: str) -> tuple[pd.Series | None, pd.Series]:
    """Fetch benchmark prices and compute returns. Returns (returns, cum)."""
    try:
        benchmark_prices = fetch_benchmark(benchmark_choice, period="1y")
    except Exception as e:  # noqa: BLE001
        logger.warning("Benchmark fetch failed: {e}", e=e)
        benchmark_prices = pd.Series(dtype=float)

    if not benchmark_prices.empty and len(benchmark_prices) > 1:
        benchmark_returns = benchmark_prices.pct_change().dropna()
        benchmark_cum = (1 + benchmark_returns).cumprod()
        return benchmark_returns, benchmark_cum
    return None, pd.Series(dtype=float)


def _compute_stock_betas(prices: pd.DataFrame, benchmark_returns: pd.Series | None) -> dict[str, float]:
    """Compute per-holding betas vs benchmark."""
    if benchmark_returns is None or prices.empty:
        return {}
    rets = prices.pct_change().dropna()
    extended = pd.concat([rets, benchmark_returns], axis=1, join="inner").dropna()
    if len(extended) <= 5:
        return {c: 1.0 for c in rets.columns}
    cov_matrix = extended.cov()
    bm_var = cov_matrix.iloc[-1, -1]
    if bm_var <= 0:
        return {c: 1.0 for c in rets.columns}
    betas = (cov_matrix.iloc[:-1, -1] / bm_var).round(2).to_dict()
    return betas if betas else {c: 1.0 for c in rets.columns}


def _run_intelligence_modules(
    prices: pd.DataFrame,
    weights: list[float],
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series | None,
    risk: object,
    sector: object,
    benchmark: object | None,
    raw_corr: pd.DataFrame,
    stock_betas: dict[str, float],
    regime_result: object | None,
    profile: object,
    portfolio: Portfolio,
) -> dict:
    """Run all intelligence modules with consistent error handling."""
    from engine.intelligence_registry import run_intelligence_modules

    context = {
        "prices": prices,
        "weights": weights,
        "portfolio_returns": portfolio_returns,
        "benchmark_returns": benchmark_returns,
        "risk": risk,
        "sector": sector,
        "benchmark": benchmark,
        "raw_corr": raw_corr,
        "stock_betas": stock_betas,
        "regime_result": regime_result,
        "profile": profile,
        "portfolio": portfolio,
    }
    return run_intelligence_modules(context)


def compute_all(
    portfolio: Portfolio,
    benchmark_choice: str,
    risk_profile_key: str,
    risk_free_rate: float,
    force_refresh: bool = False,
) -> tuple[AnalysisReport, ComputeContext]:
    """
    Main computation pipeline.

    Args:
        portfolio: User portfolio with holdings
        benchmark_choice: Benchmark ticker (e.g., "^NSEI")
        risk_profile_key: "conservative" | "moderate" | "aggressive"
        risk_free_rate: Annual risk-free rate (e.g., 0.065)
        force_refresh: Skip cache, fetch fresh prices

    Returns:
        (AnalysisReport for rendering, ComputeContext with all intermediates)
    """
    profile = RISK_PROFILES[risk_profile_key]

    # ── Fetch prices ──
    try:
        prices = _fetch_prices(portfolio, force_refresh)
    except ValueError as e:
        raise ValueError(f"Could not fetch price data: {e}") from e
    except Exception as e:  # noqa: BLE001
        logger.error("Price fetch failed: {e}", e=e)
        raise RuntimeError(f"An unexpected error occurred while fetching prices: {e}") from e

    portfolio = _align_portfolio(portfolio, prices)
    if not portfolio.holdings:
        raise ValueError("All holdings failed to fetch. No price data available for analysis.")

    # Validate portfolio (now that current_price is set)
    for w in validate_portfolio(portfolio):
        logger.warning("Portfolio validation: {w}", w=w)

    # Sector classification
    sector_map = load_sector_map()
    portfolio.holdings = classify_holdings(portfolio.holdings, sector_map)

    # Returns
    weights = portfolio.weight
    portfolio_returns = compute_portfolio_returns(prices, weights)
    portfolio_cum = (1 + portfolio_returns).cumprod()

    # Benchmark
    benchmark_returns, benchmark_cum = _fetch_benchmark(benchmark_choice)

    # Core metrics
    risk = compute_risk_metrics(
        prices,
        weights,
        risk_free_rate=risk_free_rate,
        benchmark_returns=benchmark_returns,
        portfolio_returns=portfolio_returns,
    )
    sector = compute_sector_exposure(portfolio.holdings)
    benchmark = (
        compare_to_benchmark(portfolio_returns, benchmark_returns) if benchmark_returns is not None else None
    )

    # Correlation matrix (needed for denoising)
    raw_corr = compute_correlation_matrix(prices) if not prices.empty else pd.DataFrame()

    # Portfolio Optimization (method selected by risk profile)
    opt_result = None
    if len(weights) >= 2:
        rets = prices.pct_change().dropna()
        method_map = {
            "min_volatility": lambda: optimize_min_volatility(
                rets, max_single_weight=profile.max_single_weight
            ),
            "hrp": lambda: optimize_hrp(rets, max_single_weight=profile.max_single_weight),
            "max_sharpe": lambda: optimize_max_sharpe(rets, max_single_weight=profile.max_single_weight),
        }
        opt_result = method_map.get(profile.method, method_map["hrp"])()

    # Monte Carlo simulation (stats + chart paths from single run)
    mc_result = None
    mc_paths = None
    if not portfolio_returns.empty:
        mc_data = monte_carlo_simulation(portfolio_returns, return_paths=True, n_paths=200)
        if mc_data:
            mc_result, mc_paths = mc_data

    # HMM Regime detection
    regime_result = detect_regimes(portfolio_returns) if not portfolio_returns.empty else None

    # Correlation denoising
    denoised_corr = (
        denoise_correlation(raw_corr, len(portfolio_returns)) if not portfolio_returns.empty else None
    )

    # Per-holding betas (vectorized via single covariance matrix)
    stock_betas = _compute_stock_betas(prices, benchmark_returns)

    # Scenarios & rebalance
    scenarios = run_default_scenarios(portfolio.holdings, stock_betas) if stock_betas else []
    rebalance = (
        suggest_rebalance(portfolio.holdings, profile=profile) if portfolio.holding_count >= 1 else None
    )

    # Intelligence modules (registry-based, consistent error handling)
    intel = _run_intelligence_modules(
        prices=prices,
        weights=weights,
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        risk=risk,
        sector=sector,
        benchmark=benchmark,
        raw_corr=raw_corr,
        stock_betas=stock_betas,
        regime_result=regime_result,
        profile=profile,
        portfolio=portfolio,
    )
    factor_report = intel.get("factor_report")
    macro_drivers = intel.get("macro_drivers")
    macro_scenarios = intel.get("macro_scenarios", [])
    institutional_scores = intel.get("institutional_scores")
    early_warnings = intel.get("early_warnings")
    recommendations = intel.get("recommendations")

    # ── Advanced modules (each guarded) ──
    zscore = None
    try:
        ticker_list = list(prices.columns)
        zscore = compute_all_zscores(ticker_list) if ticker_list else []
    except Exception as e:  # noqa: BLE001
        logger.warning("Altman Z-Score failed: {e}", e=e)

    var_backtest = None
    try:
        if not portfolio_returns.empty:
            from engine.backtesting import rolling_historical_var_backtest

            # Rolling (expanding-window) historical VaR backtest — each day's VaR is
            # estimated from the trailing window and tested against the NEXT day's return.
            # This is a genuine out-of-sample Kupiec test (can legitimately FAIL),
            # unlike a constant forecast pinned to the in-sample 5th percentile.
            var_backtest = rolling_historical_var_backtest(portfolio_returns.values.flatten())
    except Exception as e:  # noqa: BLE001
        logger.warning("VaR backtest failed: {e}", e=e)

    garch_var = None
    try:
        if not portfolio_returns.empty:
            garch_var = estimate_garch_var(portfolio_returns.values.flatten())
    except Exception as e:  # noqa: BLE001
        logger.warning("GARCH VaR failed: {e}", e=e)

    pelve = None
    try:
        if not portfolio_returns.empty:
            pelve = compute_pelve(portfolio_returns.values.flatten(), epsilon=0.01)
    except Exception as e:  # noqa: BLE001
        logger.warning("PELVE failed: {e}", e=e)

    opt_advanced = None
    try:
        if not prices.empty and len(weights) >= 2:
            rets = prices.pct_change().dropna()
            if not rets.empty:
                opt_advanced = optimize_advanced(rets)
    except Exception as e:  # noqa: BLE001
        logger.warning("Advanced optimization failed: {e}", e=e)

    # Narrative (pure function, no IO)
    report = AnalysisReport(
        portfolio=portfolio,
        risk=risk,
        sector=sector,
        benchmark=benchmark,
        optimization=opt_result,
        monte_carlo=mc_result,
        regime=regime_result,
        factor_report=factor_report,
        macro_drivers=macro_drivers,
        institutional_scores=institutional_scores,
        macro_scenarios=macro_scenarios,
        recommendations=recommendations,
        warnings=early_warnings,
        zscore=zscore,
        var_backtest=var_backtest,
        garch_var=garch_var,
        pelve=pelve,
        optimization_advanced=opt_advanced,
    )
    narrative = generate_narrative(report)

    ctx = ComputeContext(
        prices=prices,
        portfolio_returns=portfolio_returns,
        portfolio_cum=portfolio_cum,
        benchmark_returns=benchmark_returns,
        benchmark_cum=benchmark_cum,
        raw_corr=raw_corr,
        denoised_corr=denoised_corr,
        mc_paths=mc_paths,
        stock_betas=stock_betas,
        scenarios=scenarios,
        rebalance=rebalance,
        risk=risk,
        sector=sector,
        benchmark=benchmark,
        opt_result=opt_result,
        mc_result=mc_result,
        regime_result=regime_result,
        factor_report=factor_report,
        macro_drivers=macro_drivers,
        macro_scenarios=macro_scenarios,
        institutional_scores=institutional_scores,
        early_warnings=early_warnings,
        recommendations=recommendations,
        zscore=zscore,
        var_backtest=var_backtest,
        garch_var=garch_var,
        pelve=pelve,
        opt_advanced=opt_advanced,
        weights=weights,
        portfolio=portfolio,
        benchmark_choice=benchmark_choice,
        risk_profile_key=risk_profile_key,
        risk_free_rate=risk_free_rate,
        profile=profile,
        narrative=narrative,
    )
    return report, ctx
