#!/usr/bin/env python3
"""
Institutional-grade analysis of Ashay & Rishu portfolios using NSE Portfolio Risk Scanner engine.
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from data.prices import fetch_prices  # noqa: E402
from engine import RISK_PROFILES, Holding  # noqa: E402
from engine.factors import compute_factor_exposures, estimate_macro_sensitivities  # noqa: E402
from engine.optimization import optimize_hrp, optimize_min_volatility  # noqa: E402
from engine.recommendations import generate_recommendations  # noqa: E402
from engine.regime import detect_regimes  # noqa: E402
from engine.risk import (  # noqa: E402
    compute_correlation_matrix,
    compute_risk_metrics,
    compute_stock_risk_attribution,
    denoise_correlation,
    monte_carlo_simulation,
)
from engine.scenario import run_default_scenarios  # noqa: E402
from engine.scoring import compute_institutional_scores  # noqa: E402
from engine.sector import classify_holdings, compute_sector_exposure  # noqa: E402


def _score_to_tier(score: float) -> str:
    """Convert overall risk score to risk tier."""
    if score >= 70:
        return "HIGH"
    elif score >= 45:
        return "MODERATE"
    elif score >= 25:
        return "LOW"
    return "VERY LOW"


# ─── Portfolio Data ──────────────────────────────────────────────
ASHAY_HOLDINGS = [
    {"ticker": "HDFCBANK", "name": "HDFC Bank Ltd", "quantity": 24, "avg_price": 765.36, "sector": "Banking"},
    {
        "ticker": "NEXT50IETF",
        "name": "ICICI Prudential Nifty Next 50 ETF",
        "quantity": 250,
        "avg_price": 74.73,
        "sector": "Large-cap Blend",
    },
    {
        "ticker": "NIFTYBEES",
        "name": "Nippon India ETF Nifty 50 BeES",
        "quantity": 60,
        "avg_price": 257.11,
        "sector": "Large-cap Blend",
    },
    {"ticker": "VEDL", "name": "Vedanta Ltd", "quantity": 55, "avg_price": 293.92, "sector": "Metals"},
    {
        "ticker": "MIDCAPETF",
        "name": "Mirae Asset Nifty Midcap 150 ETF",
        "quantity": 500,
        "avg_price": 20.51,
        "sector": "Mid-cap Blend",
    },
    {
        "ticker": "ENERGY",
        "name": "Mirae Asset Nifty Energy ETF",
        "quantity": 279,
        "avg_price": 40.49,
        "sector": "Energy",
    },
    {
        "ticker": "GOLDBEES",
        "name": "Nippon India ETF Gold BeES",
        "quantity": 65,
        "avg_price": 126.29,
        "sector": "Gold",
    },
    {
        "ticker": "MODEFENCE",
        "name": "Motilal Oswal Nifty India Defence ETF",
        "quantity": 70,
        "avg_price": 101.21,
        "sector": "Defence",
    },
    {
        "ticker": "LIQUIDCASE",
        "name": "Zerodha Nifty 1D Rate Liquid ETF",
        "quantity": 62,
        "avg_price": 114.80,
        "sector": "Cash Eq",
    },
    {
        "ticker": "MONIFTY500",
        "name": "Motilal Oswal Nifty 500 ETF",
        "quantity": 280,
        "avg_price": 23.61,
        "sector": "Broad Market",
    },
    {
        "ticker": "MAKEINDIA",
        "name": "Mirae Asset Nifty India Manufacturing ETF",
        "quantity": 40,
        "avg_price": 161.49,
        "sector": "Manufacturing",
    },
    {
        "ticker": "POWERGRID",
        "name": "Power Grid Corporation of India Ltd",
        "quantity": 21,
        "avg_price": 287.87,
        "sector": "Power/Utility",
    },
    {
        "ticker": "MASPTOP50",
        "name": "Mirae Asset S&P 500 Top 50 ETF",
        "quantity": 64,
        "avg_price": 79.00,
        "sector": "US Large-cap",
    },
    {
        "ticker": "COALINDIA",
        "name": "Coal India Ltd",
        "quantity": 9,
        "avg_price": 430.85,
        "sector": "Coal/Mining",
    },
    {
        "ticker": "GROWW",
        "name": "Billionbrains Garage Ventures Ltd",
        "quantity": 15,
        "avg_price": 192.10,
        "sector": "Fintech",
    },
    {
        "ticker": "SILVERBEES",
        "name": "Nippon India Silver ETF",
        "quantity": 10,
        "avg_price": 208.92,
        "sector": "Silver",
    },
    {
        "ticker": "METAL",
        "name": "Mirae Asset Nifty Metal ETF",
        "quantity": 20,
        "avg_price": 13.64,
        "sector": "Metals",
    },
]

RISHU_HOLDINGS = [
    {
        "ticker": "SBIN",
        "name": "State Bank of India",
        "quantity": 120,
        "avg_price": 881.35,
        "sector": "Banking",
    },
    {
        "ticker": "MONIFTY500",
        "name": "Motilal Oswal Nifty 500 ETF",
        "quantity": 9246,
        "avg_price": 23.62,
        "sector": "Broad Market",
    },
    {"ticker": "TMCV", "name": "Tata Motors Ltd", "quantity": 225, "avg_price": 319.60, "sector": "Auto"},
    {
        "ticker": "EXIDEIND",
        "name": "Exide Industries Ltd",
        "quantity": 70,
        "avg_price": 562.67,
        "sector": "Auto Components",
    },
    {"ticker": "NMDC", "name": "NMDC Ltd", "quantity": 566, "avg_price": 88.37, "sector": "Metals & Mining"},
    {
        "ticker": "GOLDBEES",
        "name": "Nippon India ETF Gold BeES",
        "quantity": 324,
        "avg_price": 120.33,
        "sector": "Gold",
    },
    {
        "ticker": "ENERGY",
        "name": "Mirae Asset Nifty Energy ETF",
        "quantity": 1484,
        "avg_price": 40.44,
        "sector": "Energy",
    },
    {
        "ticker": "CASTROLIND",
        "name": "Castrol India Ltd",
        "quantity": 135,
        "avg_price": 185.29,
        "sector": "Lubricants",
    },
    {
        "ticker": "POWERGRID",
        "name": "Power Grid Corporation of India Ltd",
        "quantity": 216,
        "avg_price": 289.39,
        "sector": "Power/Utility",
    },
    {
        "ticker": "MIDCAPETF",
        "name": "Mirae Asset Nifty Midcap 150 ETF",
        "quantity": 989,
        "avg_price": 20.42,
        "sector": "Mid-cap Blend",
    },
    {
        "ticker": "NEXT50IETF",
        "name": "ICICI Prudential Nifty Next 50 ETF",
        "quantity": 198,
        "avg_price": 75.51,
        "sector": "Large-cap Blend",
    },
    {
        "ticker": "COALINDIA",
        "name": "Coal India Ltd",
        "quantity": 22,
        "avg_price": 452.70,
        "sector": "Coal/Mining",
    },
    {
        "ticker": "HDFCSML250",
        "name": "HDFC NIFTY Smallcap 250 ETF",
        "quantity": 65,
        "avg_price": 150.67,
        "sector": "Small-cap Blend",
    },
    {"ticker": "SRF", "name": "SRF Ltd", "quantity": 4, "avg_price": 2312.09, "sector": "Chemicals"},
    {
        "ticker": "IEX",
        "name": "Indian Energy Exchange Ltd",
        "quantity": 45,
        "avg_price": 198.36,
        "sector": "Power Exchange",
    },
    {
        "ticker": "NIFTYBEES",
        "name": "Nippon India ETF Nifty 50 BeES",
        "quantity": 90,
        "avg_price": 275.90,
        "sector": "Large-cap Blend",
    },
    {
        "ticker": "LIQUIDCASE",
        "name": "Zerodha Nifty 1D Rate Liquid ETF",
        "quantity": 431,
        "avg_price": 114.89,
        "sector": "Cash Eq",
    },
    {
        "ticker": "MAFANG",
        "name": "Mirae Asset NYSE FANG+ ETF",
        "quantity": 103,
        "avg_price": 194.20,
        "sector": "US Tech",
    },
]

# Current prices (Jul 28, 2026 - live)
CURRENT_PRICES = {
    "HDFCBANK": 735.05,
    "NEXT50IETF": 76.11,
    "NIFTYBEES": 273.47,
    "VEDL": 259.25,
    "MIDCAPETF": 23.44,
    "ENERGY": 38.40,
    "GOLDBEES": 116.88,
    "MODEFENCE": 101.30,
    "LIQUIDCASE": 115.20,
    "MONIFTY500": 23.65,
    "MAKEINDIA": 162.13,
    "POWERGRID": 285.30,
    "MASPTOP50": 77.90,
    "COALINDIA": 410.45,
    "GROWW": 195.35,
    "SILVERBEES": 206.04,
    "METAL": 12.53,
    "SBIN": 1010.10,
    "TMCV": 417.20,
    "EXIDEIND": 425.30,
    "NMDC": 83.70,
    "CASTROLIND": 184.19,
    "HDFCSML250": 179.02,
    "SRF": 2639.40,
    "IEX": 132.11,
    "MAFANG": 191.12,
}

# Proposed trades
PROPOSED_TRADES_ASHAY = {
    "BUY": {"CASTROLIND": 27, "POWERGRID": 35, "NMDC": 114},
    "TRIM": {"GROWW": 7},
}
PROPOSED_TRADES_RISHU = {
    "BUY": {"NMDC": 66, "CASTROLIND": 25, "COALINDIA": 13},
    "TRIM": {"TMCV": 15},
}


def build_holdings(holdings_data):
    """Convert holdings data to engine Holding objects with current prices."""
    holdings = []
    for h in holdings_data:
        ticker = h["ticker"]
        current_price = CURRENT_PRICES.get(ticker, 0.0)
        holding = Holding(
            ticker=ticker,
            name=h["name"],
            quantity=h["quantity"],
            avg_price=h["avg_price"],
            sector=h["sector"],
            current_price=current_price,
            change_pct=0.0,
        )
        holdings.append(holding)
    return holdings


def apply_proposed_trades(holdings, trades):
    """Apply proposed trades to holdings for what-if analysis."""
    holdings = [h for h in holdings]  # copy
    h_dict = {h.ticker: h for h in holdings}

    for action, tickers in trades.items():
        for ticker, qty in tickers.items():
            if ticker in h_dict:
                if action == "BUY":
                    h_dict[ticker].quantity += qty
                elif action == "TRIM":
                    h_dict[ticker].quantity = max(0, h_dict[ticker].quantity - qty)
            elif action == "BUY":
                # New position - need to add
                h_dict[ticker] = Holding(
                    ticker=ticker,
                    name=ticker,
                    quantity=qty,
                    avg_price=CURRENT_PRICES.get(ticker, 0),
                    sector="",
                    current_price=CURRENT_PRICES.get(ticker, 0),
                    change_pct=0.0,
                )
    return list(h_dict.values())


def analyze_portfolio(holdings, portfolio_name, profile_name="moderate", proposed_trades=None):
    """Run full institutional analysis on a portfolio."""
    profile = RISK_PROFILES[profile_name]

    print(f"\n{'=' * 70}")
    print(f"  {portfolio_name.upper()} PORTFOLIO — INSTITUTIONAL ANALYSIS ({profile.name})")
    if proposed_trades:
        print("  [WITH PROPOSED TRADES APPLIED]")
    print(f"{'=' * 70}")

    # Apply proposed trades if given
    if proposed_trades:
        holdings = apply_proposed_trades(holdings, proposed_trades)

    # ─── Basic Metrics ─────────────────────────────────────────────
    total_invested = sum(h.invested_value for h in holdings)
    total_current = sum(h.current_value for h in holdings)
    total_pnl = total_current - total_invested
    total_return = (total_pnl / total_invested) * 100 if total_invested > 0 else 0

    print("\n📊 PORTFOLIO SUMMARY")
    print(f"   Holdings: {len(holdings)}")
    print(f"   Invested: ₹{total_invested:,.0f}")
    print(f"   Current:  ₹{total_current:,.0f}")
    print(f"   P&L:      ₹{total_pnl:+,.0f} ({total_return:+.2f}%)")

    # ─── Sector Classification ─────────────────────────────────────
    holdings = classify_holdings(holdings)
    sector_exposure = compute_sector_exposure(holdings)

    print("\n🏭 SECTOR ALLOCATION (by current value)")
    for sector, pct in sorted(sector_exposure.sector_allocation.items(), key=lambda x: -x[1]):
        flag = " ⚠️ CONCENTRATED" if sector in sector_exposure.concentrated_sectors else ""
        print(f"   {sector:22s}: {pct:6.2f}%{flag}")
    print(f"   Diversification Score: {sector_exposure.diversification_score:.1f}/100")
    print(f"   Herfindahl Index: {sector_exposure.herfindahl_index:.3f}")

    # ─── Fetch Price History ───────────────────────────────────────
    print(f"\n📈 Fetching 1Y price history for {len(holdings)} holdings...")
    try:
        prices_df = fetch_prices(holdings, period="1y")
        if prices_df.empty:
            print("   ❌ No price data returned")
            return
        print(f"   ✅ Got {len(prices_df)} days × {len(prices_df.columns)} tickers")
        valid_tickers = [t for t in prices_df.columns]
    except Exception as e:
        print(f"   ❌ Price fetch failed: {e}")
        return

    # Align holdings with price data
    holdings = [h for h in holdings if h.ticker in valid_tickers]

    if len(holdings) < 2:
        print("   ❌ Need at least 2 holdings with price data")
        return

    weights = np.array([h.current_value / total_current for h in holdings])
    weights = weights / weights.sum()

    # ─── Risk Metrics ──────────────────────────────────────────────
    print("\n⚠️  RISK METRICS (1Y, 252 trading days, rf=7%)")
    risk = compute_risk_metrics(prices_df[valid_tickers], weights, risk_free_rate=0.07)

    print(f"   Annualized Volatility:     {risk.volatility_annual:6.2f}%")
    print(f"   VaR (95%, 1D):             {risk.var_95:6.2f}%")
    print(f"   CVaR (95%, 1D):            {risk.cvar_95:6.2f}%")
    print(f"   VaR (99%, 1D):             {risk.var_99:6.2f}%")
    print(f"   Sharpe Ratio:              {risk.sharpe:6.2f}")
    print(f"   Sortino Ratio:             {risk.sortino:6.2f}")
    print(f"   Calmar Ratio:              {risk.calmar_ratio:6.2f}")
    print(f"   Max Drawdown:              {risk.max_drawdown:6.2f}%")
    print(f"   Portfolio Beta (vs Nifty): {risk.beta:6.2f}")
    print(f"   Correlation to Nifty:      {risk.correlation_to_benchmark:6.2f}")

    # Portfolio-level VaR in rupees
    var_95_1d_rs = total_current * risk.var_95 / 100
    cvar_95_1d_rs = total_current * risk.cvar_95 / 100
    var_95_1y_rs = total_current * risk.var_95 * np.sqrt(252) / 100
    print("\n   💰 PORTFOLIO VaR IN RUPEES")
    print(f"      1-Day 95% VaR:  ₹{var_95_1d_rs:,.0f}")
    print(f"      1-Day 95% CVaR: ₹{cvar_95_1d_rs:,.0f}")
    print(f"      1-Year 95% VaR: ₹{var_95_1y_rs:,.0f}")

    # ─── Monte Carlo (10K paths) ───────────────────────────────────
    print("\n🎲 MONTE CARLO SIMULATION (10,000 paths, 1Y horizon)")
    returns = prices_df[valid_tickers].pct_change().dropna()
    portfolio_returns = returns.dot(weights)
    mc = monte_carlo_simulation(portfolio_returns, n_simulations=10000, horizon_days=252)
    print(f"   Expected Return (median):  {mc.median_return:6.2f}%")
    print(f"   VaR 95% (1Y):              {mc.var_95:6.2f}%")
    print(f"   CVaR 95% (1Y):             {mc.cvar_95:6.2f}%")
    print(f"   Probability of Profit:     {mc.prob_profit:6.2f}%")
    print(f"   CI Lower (5%):             {mc.ci_lower:6.2f}%")
    print(f"   CI Upper (95%):            {mc.ci_upper:6.2f}%")

    mc_var_rs = total_current * mc.var_95 / 100
    mc_cvar_rs = total_current * mc.cvar_95 / 100
    print(f"   💰 1Y 95% VaR:  ₹{mc_var_rs:,.0f}")
    print(f"   💰 1Y 95% CVaR: ₹{mc_cvar_rs:,.0f}")

    # ─── Regime Detection (HMM) ────────────────────────────────────
    print("\n🔄 REGIME DETECTION (HMM, 3 states)")
    regime = detect_regimes(portfolio_returns, n_states=3)
    if regime:
        current_regime = regime.state_sequence[-1] if regime.state_sequence else "Unknown"
        print(f"   Current Regime:            {current_regime}")
        print(f"   Regime Labels:             {regime.labels}")
        # Calculate regime probabilities from recent state sequence
        recent_states = (
            regime.state_sequence[-60:] if len(regime.state_sequence) >= 60 else regime.state_sequence
        )
        probs = {label: recent_states.count(label) / len(recent_states) for label in regime.labels}
        print(f"   Regime Probabilities (60D): {probs}")
        mean_returns = [f"{s['mean_return']:.1f}%" for s in regime.stats]
        annual_vols = [f"{s['annual_vol']:.1f}%" for s in regime.stats]
        print(f"   Regime Means (annual):     {mean_returns}")
        print(f"   Regime Vols (annual):      {annual_vols}")
    else:
        print("   ❌ Regime detection failed (insufficient data)")

    # ─── Factor Exposures ──────────────────────────────────────────
    print("\n📐 FACTOR EXPOSURES (Fama-French 5-factor + Momentum)")
    factor_report = compute_factor_exposures(prices_df[valid_tickers], weights)
    for factor in factor_report.factors:
        print(f"   {factor.name:15s}: {factor.exposure:+.3f}  Risk%: {factor.risk_contribution_pct:.1f}%")
    print(f"   R² (Factor Model): {factor_report.total_factor_risk_pct:.1f}%")
    print(f"   Idiosyncratic Risk: {factor_report.idiosyncratic_risk_pct:.1f}%")
    print(f"   Dominant Factor: {factor_report.dominant_factor}")

    # ─── Macro Sensitivities ───────────────────────────────────────
    print("\n🌍 MACRO SENSITIVITIES")
    macro = estimate_macro_sensitivities(portfolio_returns, prices_df[valid_tickers], weights)
    for driver in macro:
        print(
            f"   {driver.name:20s}: {driver.sensitivity:+.3f} | Regime: {driver.current_regime} | Risk: {driver.risk_level}"
        )
        print(f"      → {driver.reasoning}")

    # ─── Institutional Scoring ─────────────────────────────────────
    print("\n🏛️  INSTITUTIONAL RISK SCORES (P×I×C)")
    # Build sector allocation dict
    sector_allocation = {sector: pct for sector, pct in sector_exposure.sector_allocation.items()}
    # Correlation matrix for hidden correlation scoring
    corr_matrix = compute_correlation_matrix(prices_df[valid_tickers])
    scores = compute_institutional_scores(
        risk=risk,
        prices=prices_df[valid_tickers],
        weights=weights,
        sector_allocation=sector_allocation,
        corr_matrix=corr_matrix,
    )
    print(f"   Overall Risk Score:         {scores.overall_risk_score:.1f}/100")
    print(f"   Conviction Score:           {scores.conviction_score:.1f}/100")
    print(f"   Portfolio Stress Score:     {scores.portfolio_stress_score:.1f}/100")
    print(f"   Hidden Correlation Score:   {scores.hidden_correlation_score:.1f}/100")
    print(f"   Tail Risk Score:            {scores.tail_risk_score:.1f}/100")
    print(f"   Risk Tier:                  {_score_to_tier(scores.overall_risk_score)}")
    print(f"   Interpretation:             {scores.score_interpretation}")
    print("   Top 5 Risk Factors:")
    for i, rf in enumerate(scores.top_5_insights, 1):
        print(f"      {i}. {rf.name}: {rf.composite:.1f} — {rf.reasoning[:80]}...")

    # ─── Stock Risk Attribution ────────────────────────────────────
    print("\n🎯 STOCK RISK ATTRIBUTION (top 7 contributors)")
    attribution = compute_stock_risk_attribution(prices_df[valid_tickers], weights)
    if not attribution.empty:
        for idx, row in attribution.head(7).iterrows():
            pct = (row["Risk Contrib (%)"] / risk.volatility_annual) * 100
            h = next((h for h in holdings if h.ticker == row["Ticker"]), None)
            w = h.current_value / total_current * 100 if h else 0
            print(
                f"   {idx + 1}. {row['Ticker']:12s}: {row['Risk Contrib (%)']:+.3f}% vol ({pct:+.1f}% of total) | wt: {w:.1f}%"
            )
    else:
        print("   No attribution data available")

    # ─── Correlation (denoised) ────────────────────────────────────
    print("\n🔗 HIGH CORRELATIONS (denoised, >0.7)")
    corr = compute_correlation_matrix(prices_df[valid_tickers])
    n_samples = len(prices_df[valid_tickers].pct_change().dropna())
    try:
        corr_denoised = denoise_correlation(corr, n_samples=n_samples)
    except Exception as e:
        print(f"   ⚠️ Denoising failed ({e}), using raw correlation matrix")
        corr_denoised = corr
    high_corr = []
    for i in range(len(valid_tickers)):
        for j in range(i + 1, len(valid_tickers)):
            c = corr_denoised.iloc[i, j]
            if c > 0.7:
                high_corr.append((valid_tickers[i], valid_tickers[j], c))
    if high_corr:
        for a, b, c in sorted(high_corr, key=lambda x: -x[2])[:10]:
            print(f"   {a:12s} ↔ {b:12s}: {c:.2f}")
    else:
        print("   No pairs > 0.7 correlation")

    # ─── Optimization ──────────────────────────────────────────────
    print("\n⚖️  OPTIMIZATION")
    hrp = optimize_hrp(prices_df[valid_tickers])
    minvol = optimize_min_volatility(prices_df[valid_tickers])

    print("   HRP Weights (top 7):")
    for t, w in sorted(hrp.weights.items(), key=lambda x: -x[1])[:7]:
        curr_w = next((h.current_value / total_current * 100 for h in holdings if h.ticker == t), 0)
        diff = w * 100 - curr_w
        print(f"      {t:12s}: HRP={w * 100:5.1f}% | Current={curr_w:5.1f}% | Δ={diff:+.1f}%")

    print("   Min-Vol Weights (top 7):")
    for t, w in sorted(minvol.weights.items(), key=lambda x: -x[1])[:7]:
        curr_w = next((h.current_value / total_current * 100 for h in holdings if h.ticker == t), 0)
        diff = w * 100 - curr_w
        print(f"      {t:12s}: MinVol={w * 100:5.1f}% | Current={curr_w:5.1f}% | Δ={diff:+.1f}%")

    # ─── Scenario Analysis ─────────────────────────────────────────
    print("\n🌪️  SCENARIO ANALYSIS (standard scenarios)")
    # Compute betas for scenario analysis
    returns = prices_df[valid_tickers].pct_change().dropna()
    portfolio_returns = returns.dot(weights)
    betas = {}
    if "NIFTYBEES" in returns.columns:
        bench_returns = returns["NIFTYBEES"]
        aligned = pd.concat([portfolio_returns, bench_returns], axis=1, join="inner").dropna()
        if len(aligned) > 20:
            for t in valid_tickers:
                if t in returns.columns:
                    cov_val = returns[t].cov(bench_returns)
                    var_val = bench_returns.var()
                    betas[t] = float(cov_val / var_val) if var_val > 0 else 1.0
    scenarios = run_default_scenarios(holdings, betas)
    for result in scenarios:
        pnl_pct = result.portfolio_impact_pct
        pnl_rs = total_current * pnl_pct / 100
        print(f"   {result.name:25s}: {pnl_pct:+.2f}%  (₹{pnl_rs:+,.0f})")

    # ─── Recommendations ───────────────────────────────────────────
    print("\n🎯 INSTITUTIONAL RECOMMENDATIONS")
    # Create a proper portfolio object for recommendations
    from engine import Portfolio

    portfolio_obj = Portfolio(holdings=holdings, name=portfolio_name)
    recs = generate_recommendations(
        risk=risk,
        sector=sector_exposure,
        benchmark=type("obj", (object,), {"excess_return": 0, "tracking_error": 0, "information_ratio": 0})(),
        portfolio=portfolio_obj,
        profile=profile,
    )

    print(f"   Summary: {recs.summary}")
    print(f"   Total Risk Reduction Potential: {recs.risk_reduction_potential:.1f}%")
    print("   Priority Actions:")
    for i, r in enumerate(recs.priority_actions[:5], 1):
        print(f"      {i}. [{r.urgency.upper()}] {r.action.value.upper()} {r.target}")
        print(f"         Confidence: {r.confidence:.0%} | Risk Reduction: {r.expected_risk_reduction:.1f}%")
        print(f"         Reason: {r.reasoning}")
        print(f"         Trade-off: {r.trade_off}")
        if r.details:
            print(f"         Details: {r.details}")

    # ─── What-if: Proposed Trades Impact ───────────────────────────
    if proposed_trades:
        print("\n🔮 WHAT-IF: PROPOSED TRADES IMPACT")
        # Current risk
        curr_var = total_current * risk.var_95 / 100
        curr_sharpe = risk.sharpe
        curr_cvar = total_current * risk.cvar_95 / 100

        print(f"   Current 1D 95% VaR:  ₹{curr_var:,.0f}")
        print(f"   Current 1D 95% CVaR: ₹{curr_cvar:,.0f}")
        print(f"   Current Sharpe:      {curr_sharpe:.2f}")

        # Simulate proposed portfolio
        new_holdings = apply_proposed_trades(holdings, proposed_trades)
        new_total = sum(h.current_value for h in new_holdings)
        new_weights = np.array([h.current_value / new_total for h in new_holdings])
        new_valid = [h.ticker for h in new_holdings if h.ticker in prices_df.columns]
        new_holdings_aligned = [h for h in new_holdings if h.ticker in new_valid]
        new_weights = np.array(
            [
                h.current_value / sum(h.current_value for h in new_holdings_aligned)
                for h in new_holdings_aligned
            ]
        )
        new_weights = new_weights / new_weights.sum()

        try:
            new_risk = compute_risk_metrics(prices_df[new_valid], new_weights, risk_free_rate=0.07)
            new_var = new_total * new_risk.var_95 / 100
            new_cvar = new_total * new_risk.cvar_95 / 100
            new_sharpe = new_risk.sharpe

            print(f"   Proposed 1D 95% VaR:  ₹{new_var:,.0f}  (Δ ₹{new_var - curr_var:+,.0f})")
            print(f"   Proposed 1D 95% CVaR: ₹{new_cvar:,.0f}  (Δ ₹{new_cvar - curr_cvar:+,.0f})")
            print(f"   Proposed Sharpe:      {new_sharpe:.2f}  (Δ {new_sharpe - curr_sharpe:+.2f})")
            print(f"   Portfolio Value:      ₹{new_total:,.0f}  (Δ ₹{new_total - total_current:+,.0f})")
        except Exception as e:
            print(f"   ❌ What-if failed: {e}")

    return {
        "holdings": holdings,
        "risk": risk,
        "mc": mc,
        "regime": regime,
        "factor_report": factor_report,
        "macro": macro,
        "scores": scores,
        "sector": sector_exposure,
        "recs": recs,
        "hrp": hrp,
        "minvol": minvol,
        "total_current": total_current,
        "total_invested": total_invested,
    }


# ─── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("  NSE PORTFOLIO RISK SCANNER — INSTITUTIONAL ANALYSIS")
    print("  Ashay & Rishu Portfolios | Jul 28, 2026 | Live Prices")
    print("=" * 70)

    # Build holdings
    ashay_holdings = build_holdings(ASHAY_HOLDINGS)
    rishu_holdings = build_holdings(RISHU_HOLDINGS)

    # Analyze current portfolios
    ashay_result = analyze_portfolio(ashay_holdings, "ASHAY", "moderate")
    rishu_result = analyze_portfolio(rishu_holdings, "RISHU", "moderate")

    # Analyze with proposed trades
    print(f"\n\n{'=' * 70}")
    print("  WHAT-IF ANALYSIS: PROPOSED TRADES")
    print(f"{'=' * 70}")

    ashay_proposed = analyze_portfolio(ashay_holdings, "ASHAY (PROPOSED)", "moderate", PROPOSED_TRADES_ASHAY)
    rishu_proposed = analyze_portfolio(rishu_holdings, "RISHU (PROPOSED)", "moderate", PROPOSED_TRADES_RISHU)

    # Summary comparison
    print(f"\n\n{'=' * 70}")
    print("  SUMMARY COMPARISON")
    print(f"{'=' * 70}")
    print(
        f"\n{'Metric':30s} | {'Ashay Current':>15s} | {'Ashay Proposed':>15s} | {'Rishu Current':>15s} | {'Rishu Proposed':>15s}"
    )
    print(f"{'-' * 95}")

    def get_val(r, key, fmt="{:.2f}"):
        if key == "var_rs":
            return fmt.format(r["total_current"] * r["risk"].var_95 / 100)
        if key == "cvar_rs":
            return fmt.format(r["total_current"] * r["risk"].cvar_95 / 100)
        if key == "sharpe":
            return fmt.format(r["risk"].sharpe)
        if key == "sortino":
            return fmt.format(r["risk"].sortino)
        if key == "max_dd":
            return fmt.format(r["risk"].max_drawdown * 100) + "%"
        if key == "vol":
            return fmt.format(r["risk"].volatility_annual * 100) + "%"
        if key == "beta":
            return fmt.format(r["risk"].beta)
        if key == "composite":
            return fmt.format(r["scores"].overall_risk_score)
        if key == "tier":
            return _score_to_tier(r["scores"].overall_risk_score)
        if key == "value":
            return "₹{:,.0f}".format(r["total_current"])
        return "N/A"

    for key, label in [
        ("value", "Portfolio Value"),
        ("var_rs", "1D 95% VaR (₹)"),
        ("cvar_rs", "1D 95% CVaR (₹)"),
        ("sharpe", "Sharpe Ratio"),
        ("sortino", "Sortino Ratio"),
        ("max_dd", "Max Drawdown"),
        ("vol", "Ann. Volatility"),
        ("beta", "Beta"),
        ("composite", "Risk Score"),
        ("tier", "Risk Tier"),
    ]:
        a_c = get_val(ashay_result, key)
        a_p = get_val(ashay_proposed, key)
        r_c = get_val(rishu_result, key)
        r_p = get_val(rishu_proposed, key)
        print(f"{label:30s} | {a_c:>15s} | {a_p:>15s} | {r_c:>15s} | {r_p:>15s}")

    print("\n✅ Analysis complete. Engine: NSE Portfolio Risk Scanner v2.10+")
