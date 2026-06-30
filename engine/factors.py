"""
Multi-factor risk decomposition.

Decomposes portfolio risk into factor exposures using price-derived proxies.
Covers: market, size, value, momentum, volatility, liquidity, and sector factors.
Pure functions — zero IO, zero Streamlit imports.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class FactorExposure:
    """Single factor exposure and its risk contribution."""

    name: str
    exposure: float  # portfolio loading on this factor (-3 to +3 typical)
    risk_contribution_pct: float  # % of total risk attributable to this factor
    description: str  # human-readable explanation


@dataclass
class FactorRiskReport:
    """Complete factor decomposition of portfolio risk."""

    factors: list[FactorExposure]
    idiosyncratic_risk_pct: float  # % of risk not explained by factors
    total_factor_risk_pct: float  # % explained by factor model
    dominant_factor: str  # name of the factor with highest contribution
    diversification_by_factor: dict[str, float]  # factor -> diversification score


@dataclass
class MacroDriver:
    """A macroeconomic driver and its estimated portfolio sensitivity."""

    name: str
    sensitivity: float  # estimated % portfolio move per 1% move in driver
    current_regime: str  # "favorable", "neutral", "unfavorable"
    risk_level: str  # "low", "medium", "high"
    reasoning: str  # causal explanation


def _compute_rolling_beta(series: pd.Series, benchmark: pd.Series, window: int = 63) -> pd.Series:
    """Rolling beta of series vs benchmark."""
    cov = series.rolling(window).cov(benchmark)
    var = benchmark.rolling(window).var()
    return cov / var.replace(0, np.nan)


def _compute_momentum_score(returns: pd.Series, lookback: int = 252) -> float:
    """Price momentum score (annualized return over lookback)."""
    if len(returns) < lookback:
        lookback = len(returns)
    if lookback < 21:
        return 0.0
    cumulative = (1 + returns.iloc[-lookback:]).prod() - 1
    return float(cumulative)


def _compute_vol_regime(returns: pd.Series, window: int = 63) -> str:
    """Classify current volatility regime relative to history."""
    if len(returns) < window * 2:
        return "normal"
    recent_vol = returns.iloc[-window:].std() * np.sqrt(252)
    historical_vol = returns.iloc[-window * 2 : -window].std() * np.sqrt(252)
    if historical_vol == 0:
        return "normal"
    ratio = recent_vol / historical_vol
    if ratio > 1.5:
        return "elevated"
    elif ratio < 0.6:
        return "compressed"
    return "normal"


def compute_factor_exposures(
    prices: pd.DataFrame,
    weights: list[float],
    benchmark_returns: pd.Series | None = None,
) -> FactorRiskReport:
    """
    Decompose portfolio risk into factor exposures using price-derived proxies.

    Factors estimated from cross-sectional and time-series properties:
    - Market: broad market sensitivity (beta)
    - Size: relative performance of large vs small (large-cap proxy)
    - Momentum: recent price trend strength
    - Volatility: sensitivity to volatility changes
    - Liquidity: inverse of price volatility as liquidity proxy
    - Concentration: portfolio concentration risk

    Args:
        prices: Daily closing prices (columns = tickers, index = Date)
        weights: Portfolio weights aligned with price columns
        benchmark_returns: Market benchmark returns for beta estimation

    Returns:
        FactorRiskReport with per-factor exposures and risk attribution
    """
    if prices.empty or len(weights) == 0 or len(prices.columns) < 1:
        return _empty_factor_report()

    returns = prices.pct_change().dropna()
    if returns.empty:
        return _empty_factor_report()

    weights_arr = np.array(weights, dtype=float)
    if abs(weights_arr.sum() - 1.0) > 0.01:
        weights_arr = weights_arr / weights_arr.sum()

    portfolio_returns = returns.dot(weights_arr)
    n_stocks = len(prices.columns)

    # ── Factor 1: Market (beta) ──
    market_exposure = 0.0
    if benchmark_returns is not None and len(benchmark_returns) > 0:
        aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1, join="inner").dropna()
        if len(aligned) > 20:
            cov_val = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])
            var_val = aligned.iloc[:, 1].var()
            market_exposure = cov_val / var_val if var_val > 0 else 1.0

    # ── Factor 2: Size (large-cap tilt) ──
    # Proxy: average market cap rank via price level (higher price = larger cap proxy)
    avg_prices = prices.mean()
    size_tilt = 0.0
    if n_stocks > 1:
        price_weights = np.array([avg_prices.get(c, 0) for c in prices.columns])
        total_price = price_weights.sum()
        if total_price > 0:
            normalized = price_weights / total_price
            # Herfindahl of price-weighted allocation: higher = more large-cap concentrated
            size_tilt = (
                float(np.sum((weights_arr * normalized) ** 2) / np.sum(weights_arr**2))
                if np.sum(weights_arr**2) > 0
                else 0.0
            )

    # ── Factor 3: Momentum ──
    stock_momentum = {}
    for col in returns.columns:
        stock_momentum[col] = _compute_momentum_score(returns[col])
    momentum_exposure = sum(
        weights_arr[i] * stock_momentum.get(returns.columns[i], 0) for i in range(n_stocks)
    )

    # ── Factor 4: Volatility ──
    stock_vols = returns.std() * np.sqrt(252)
    vol_exposure = float(np.dot(weights_arr, stock_vols.values)) if len(stock_vols) > 0 else 0.0

    # ── Factor 5: Liquidity (inverse vol as proxy) ──
    # Higher volatility = lower liquidity proxy
    avg_vol = stock_vols.mean() if len(stock_vols) > 0 else 1.0
    liquidity_scores = 1.0 / (stock_vols / avg_vol + 0.01)  # avoid div by zero
    liquidity_exposure = (
        float(np.dot(weights_arr, liquidity_scores.values)) if len(liquidity_scores) > 0 else 1.0
    )

    # ── Factor 6: Concentration ──
    concentration = float(np.sum(weights_arr**2))

    # ── Risk contribution estimation ──
    total_var = portfolio_returns.var()
    if total_var == 0:
        return _empty_factor_report()

    # Estimate each factor's contribution to total variance
    # Market contribution: beta^2 * market_var
    market_var = (
        benchmark_returns.var()
        if benchmark_returns is not None and len(benchmark_returns) > 0
        else portfolio_returns.var()
    )
    market_contrib = (market_exposure**2) * market_var if market_var > 0 else 0.0

    # Size contribution: deviation from equal-weight
    size_contrib = abs(concentration - 1.0 / max(n_stocks, 1)) * total_var * 0.1

    # Momentum contribution: variance of momentum scores
    mom_values = list(stock_momentum.values())
    mom_contrib = np.var(mom_values) * 0.1 if len(mom_values) > 1 else 0.0

    # Volatility contribution: vol-of-vol
    rolling_vols = returns.rolling(21).std().mean(axis=1).dropna()
    vol_vol = rolling_vols.std() if len(rolling_vols) > 5 else 0.0
    vol_contrib = vol_vol * vol_exposure * 0.01

    # Liquidity contribution
    liq_contrib = (1.0 / max(liquidity_exposure, 0.1)) * total_var * 0.05

    # Concentration contribution
    conc_contrib = concentration * total_var * 0.1

    raw_contribs = {
        "Market (Beta)": abs(market_contrib),
        "Size": abs(size_contrib),
        "Momentum": abs(mom_contrib),
        "Volatility": abs(vol_contrib),
        "Liquidity": abs(liq_contrib),
        "Concentration": abs(conc_contrib),
    }

    total_raw = sum(raw_contribs.values())
    if total_raw > 0:
        risk_pcts = {k: (v / total_raw) * 100 for k, v in raw_contribs.items()}
    else:
        risk_pcts = {k: 100.0 / len(raw_contribs) for k in raw_contribs}

    # Idiosyncratic risk = remainder not explained by factor model
    total_factor_pct = sum(min(p, 100) for p in risk_pcts.values())
    idio_risk = max(0, 100 - min(total_factor_pct, 100))

    # Build factor exposures
    factors = [
        FactorExposure(
            name="Market (Beta)",
            exposure=round(market_exposure, 3),
            risk_contribution_pct=round(risk_pcts.get("Market (Beta)", 0), 1),
            description=_describe_market_exposure(market_exposure),
        ),
        FactorExposure(
            name="Size",
            exposure=round(size_tilt, 3),
            risk_contribution_pct=round(risk_pcts.get("Size", 0), 1),
            description=_describe_size_exposure(size_tilt, n_stocks),
        ),
        FactorExposure(
            name="Momentum",
            exposure=round(momentum_exposure, 4),
            risk_contribution_pct=round(risk_pcts.get("Momentum", 0), 1),
            description=_describe_momentum_exposure(momentum_exposure),
        ),
        FactorExposure(
            name="Volatility",
            exposure=round(vol_exposure, 4),
            risk_contribution_pct=round(risk_pcts.get("Volatility", 0), 1),
            description=_describe_vol_exposure(vol_exposure),
        ),
        FactorExposure(
            name="Liquidity",
            exposure=round(liquidity_exposure, 3),
            risk_contribution_pct=round(risk_pcts.get("Liquidity", 0), 1),
            description=_describe_liquidity_exposure(liquidity_exposure),
        ),
        FactorExposure(
            name="Concentration",
            exposure=round(concentration, 4),
            risk_contribution_pct=round(risk_pcts.get("Concentration", 0), 1),
            description=_describe_concentration(concentration, n_stocks),
        ),
    ]

    # Dominant factor
    dominant = max(factors, key=lambda f: f.risk_contribution_pct)

    # Diversification by factor
    div_by_factor = {
        "Market": max(0, 100 - abs(market_exposure - 1.0) * 50),
        "Size": max(0, 100 - size_tilt * 100),
        "Momentum": max(0, 100 - abs(momentum_exposure) * 500),
        "Concentration": max(0, (1 - concentration) * 100),
    }

    return FactorRiskReport(
        factors=factors,
        idiosyncratic_risk_pct=round(idio_risk, 1),
        total_factor_risk_pct=round(min(total_factor_pct, 100), 1),
        dominant_factor=dominant.name,
        diversification_by_factor=div_by_factor,
    )


def estimate_macro_sensitivities(
    portfolio_returns: pd.Series,
    prices: pd.DataFrame,
    weights: list[float],
    benchmark_returns: pd.Series | None = None,
) -> list[MacroDriver]:
    """
    Estimate portfolio sensitivity to key macroeconomic drivers.

    Uses proxy-based estimation from price behavior:
    - Crude Oil: via ONGC, BPCL, IOC (oil & gas stocks)
    - Interest Rates: via banking/financial stocks sensitivity
    - INR/USD: via IT export stocks (TCS, INFY, WIPRO)
    - Global Risk: via beta to benchmark (risk-on/risk-off)
    - Credit Quality: via financial sector weight

    Args:
        portfolio_returns: Portfolio daily returns
        prices: Price DataFrame
        weights: Portfolio weights
        benchmark_returns: Market benchmark returns

    Returns:
        List of MacroDriver with sensitivity estimates
    """
    if prices.empty or len(weights) == 0:
        return []

    weights_arr = np.array(weights, dtype=float)
    if abs(weights_arr.sum() - 1.0) > 0.01:
        weights_arr = weights_arr / weights_arr.sum()

    returns = prices.pct_change().dropna()
    if returns.empty:
        return []

    drivers = []

    # ── Crude Oil Sensitivity ──
    oil_tickers = [
        c for c in prices.columns if any(k in c.upper() for k in ["ONGC", "BPCL", "IOC", "GAIL", "RELIANCE"])
    ]
    oil_sensitivity = 0.0
    if oil_tickers:
        oil_idx = [list(prices.columns).index(t) for t in oil_tickers if t in prices.columns]
        oil_weight = sum(weights_arr[i] for i in oil_idx)
        oil_sensitivity = oil_weight * 0.8  # crude beta proxy for O&G names
    oil_regime = (
        "unfavorable" if oil_sensitivity > 0.15 else ("favorable" if oil_sensitivity < 0.05 else "neutral")
    )
    drivers.append(
        MacroDriver(
            name="Crude Oil",
            sensitivity=round(oil_sensitivity, 3),
            current_regime=oil_regime,
            risk_level="high" if oil_sensitivity > 0.2 else ("medium" if oil_sensitivity > 0.1 else "low"),
            reasoning=f"Portfolio has {oil_sensitivity * 100:.1f}% effective oil exposure through O&G holdings. "
            f"{'High oil dependence increases risk from energy price shocks.' if oil_sensitivity > 0.15 else 'Oil exposure is manageable.'}",
        )
    )

    # ── Interest Rate Sensitivity ──
    bank_tickers = [
        c
        for c in prices.columns
        if any(
            k in c.upper()
            for k in [
                "HDFCBANK",
                "ICICIBANK",
                "SBIN",
                "KOTAK",
                "AXIS",
                "INDUSINDB",
                "BANK",
                "FEDERAL",
                "AUBANK",
                "BANDHAN",
            ]
        )
    ]
    bank_sensitivity = 0.0
    if bank_tickers:
        bank_idx = [list(prices.columns).index(t) for t in bank_tickers if t in prices.columns]
        bank_weight = sum(weights_arr[i] for i in bank_idx)
        bank_sensitivity = bank_weight * 1.2  # banks are leveraged to rates
    rate_regime = (
        "unfavorable" if bank_sensitivity > 0.25 else ("favorable" if bank_sensitivity > 0.15 else "neutral")
    )
    drivers.append(
        MacroDriver(
            name="Interest Rates",
            sensitivity=round(bank_sensitivity, 3),
            current_regime=rate_regime,
            risk_level="high" if bank_sensitivity > 0.3 else ("medium" if bank_sensitivity > 0.15 else "low"),
            reasoning=f"Portfolio has {bank_sensitivity * 100:.1f}% effective rate exposure through banking/financial holdings. "
            f"{'Rate hikes benefit NIM but hurt loan growth and asset quality.' if bank_sensitivity > 0.2 else 'Rate sensitivity is moderate.'}",
        )
    )

    # ── INR/USD Sensitivity ──
    it_tickers = [
        c
        for c in prices.columns
        if any(
            k in c.upper()
            for k in ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "MPHASIS", "PERSISTENT", "COFORGE"]
        )
    ]
    it_sensitivity = 0.0
    if it_tickers:
        it_idx = [list(prices.columns).index(t) for t in it_tickers if t in prices.columns]
        it_weight = sum(weights_arr[i] for i in it_idx)
        it_sensitivity = it_weight * 0.6  # INR depreciation benefits IT exporters
    fx_regime = (
        "favorable" if it_sensitivity > 0.15 else ("unfavorable" if it_sensitivity < 0.05 else "neutral")
    )
    drivers.append(
        MacroDriver(
            name="INR/USD (Currency)",
            sensitivity=round(it_sensitivity, 3),
            current_regime=fx_regime,
            risk_level="medium" if it_sensitivity > 0.2 else ("low" if it_sensitivity > 0.1 else "medium"),
            reasoning=f"Portfolio has {it_sensitivity * 100:.1f}% effective FX exposure through IT/export holdings. "
            f"{'INR depreciation benefits these holdings; appreciation is a headwind.' if it_sensitivity > 0.1 else 'Limited currency hedge from IT stocks.'}",
        )
    )

    # ── Global Risk Sentiment ──
    global_beta = 1.0
    if benchmark_returns is not None and len(benchmark_returns) > 0:
        aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1, join="inner").dropna()
        if len(aligned) > 20:
            cov_val = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])
            var_val = aligned.iloc[:, 1].var()
            global_beta = cov_val / var_val if var_val > 0 else 1.0
    risk_regime = "unfavorable" if global_beta > 1.2 else ("favorable" if global_beta < 0.8 else "neutral")
    drivers.append(
        MacroDriver(
            name="Global Risk Sentiment",
            sensitivity=round(global_beta, 3),
            current_regime=risk_regime,
            risk_level="high" if global_beta > 1.3 else ("medium" if global_beta > 0.9 else "low"),
            reasoning=f"Portfolio beta to market is {global_beta:.2f}. "
            f"{'High beta means amplified losses during risk-off events.' if global_beta > 1.2 else 'Beta is within normal range.' if global_beta > 0.8 else 'Low beta provides defensive positioning.'}",
        )
    )

    # ── Credit Quality (financial sector dependence) ──
    fin_tickers = [
        c
        for c in prices.columns
        if any(
            k in c.upper()
            for k in [
                "HDFCBANK",
                "ICICIBANK",
                "SBIN",
                "KOTAK",
                "BAJFINANCE",
                "BAJAJFINSV",
                "SHRIRAM",
                "LICHSGFIN",
                "MUTHOOTFIN",
            ]
        )
    ]
    credit_weight = 0.0
    if fin_tickers:
        fin_idx = [list(prices.columns).index(t) for t in fin_tickers if t in prices.columns]
        credit_weight = sum(weights_arr[i] for i in fin_idx)
    credit_regime = (
        "unfavorable" if credit_weight > 0.3 else ("neutral" if credit_weight > 0.15 else "favorable")
    )
    drivers.append(
        MacroDriver(
            name="Credit Quality",
            sensitivity=round(credit_weight, 3),
            current_regime=credit_regime,
            risk_level="high" if credit_weight > 0.35 else ("medium" if credit_weight > 0.2 else "low"),
            reasoning=f"Portfolio has {credit_weight * 100:.1f}% exposure to financial/credit-sensitive sectors. "
            f"{'High credit exposure amplifies NPA cycle risk.' if credit_weight > 0.3 else 'Credit exposure is diversified.'}",
        )
    )

    return drivers


def _describe_market_exposure(beta: float) -> str:
    if beta > 1.3:
        return (
            f"High market sensitivity ({beta:.2f}x). Portfolio amplifies market moves — elevated crash risk."
        )
    elif beta > 1.0:
        return f"Above-market beta ({beta:.2f}x). Moves more than the benchmark in both directions."
    elif beta > 0.7:
        return f"Moderate market sensitivity ({beta:.2f}x). Balanced market exposure."
    elif beta > 0.3:
        return f"Below-market beta ({beta:.2f}x). Defensive positioning relative to benchmark."
    return f"Very low beta ({beta:.2f}x). Portfolio is largely uncorrelated with market moves."


def _describe_size_exposure(tilt: float, n_stocks: int) -> str:
    if tilt > 0.7:
        return (
            f"Strong large-cap tilt (concentration: {tilt:.2f}). Limited small-cap diversification benefit."
        )
    elif tilt > 0.4:
        return f"Moderate large-cap bias across {n_stocks} holdings."
    return f"Relatively balanced size distribution across {n_stocks} holdings."


def _describe_momentum_exposure(mom: float) -> str:
    if mom > 0.3:
        return f"Strong positive momentum ({mom:.1%} annualized). Stocks are in uptrends — momentum risk if trend reverses."
    elif mom > 0.05:
        return f"Moderate positive momentum ({mom:.1%}). Holdings are trending up."
    elif mom > -0.05:
        return f"Flat momentum ({mom:.1%}). No strong directional trend."
    elif mom > -0.2:
        return f"Negative momentum ({mom:.1%}). Holdings are trending down — potential value trap risk."
    return f"Strong negative momentum ({mom:.1%}). Significant downtrend across holdings."


def _describe_vol_exposure(vol: float) -> str:
    if vol > 0.4:
        return f"High volatility ({vol:.1%} annualized). Portfolio has significant tail risk."
    elif vol > 0.25:
        return f"Moderate volatility ({vol:.1%}). Within typical equity range."
    return f"Low volatility ({vol:.1%}). Relatively stable holdings."


def _describe_liquidity_exposure(score: float) -> str:
    if score > 1.5:
        return (
            "High liquidity proxy. Holdings have lower-than-average volatility, suggesting better liquidity."
        )
    elif score > 0.8:
        return "Moderate liquidity profile across holdings."
    return (
        "Lower liquidity proxy. Some holdings have elevated volatility which may indicate liquidity stress."
    )


def _describe_concentration(hhi: float, n: int) -> str:
    eq_hhi = 1.0 / max(n, 1)
    ratio = hhi / eq_hhi if eq_hhi > 0 else 1.0
    if ratio > 3:
        return f"High concentration (HHI: {hhi:.4f}, {ratio:.1f}x equal-weight). Few holdings dominate risk."
    elif ratio > 1.5:
        return f"Moderate concentration (HHI: {hhi:.4f}, {ratio:.1f}x equal-weight). Some holdings carry disproportionate risk."
    return f"Well-diversified (HHI: {hhi:.4f}, {ratio:.1f}x equal-weight). Risk is spread across holdings."


def _empty_factor_report() -> FactorRiskReport:
    return FactorRiskReport(
        factors=[],
        idiosyncratic_risk_pct=0.0,
        total_factor_risk_pct=0.0,
        dominant_factor="N/A",
        diversification_by_factor={},
    )
