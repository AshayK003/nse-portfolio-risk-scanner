#!/usr/bin/env python3
"""Run current Ashay & Rishu books through NSE Portfolio Risk Scanner (live 18 Aug 2026)."""

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from engine import Holding  # noqa: E402
from engine.compute import compute_all  # noqa: E402

# Current holdings as of 18 Aug 2026 (from vault revaluation). qty, avg_price, sector
ASHAY = [
    ("HDFCBANK", 24, 765.36, "Banking"),
    ("NEXT50IETF", 180, 74.73, "Large-cap Blend"),
    ("NIFTYBEES", 60, 257.11, "Large-cap Blend"),
    ("VEDL", 25, 276.40, "Metals"),
    ("MIDCAPETF", 500, 20.51, "Mid-cap Blend"),
    ("ENERGY", 279, 40.49, "Energy"),
    ("GOLDBEES", 65, 126.29, "Gold"),
    ("MODEFENCE", 70, 101.21, "Defence"),
    ("MONIFTY500", 280, 23.61, "Broad Market"),
    ("MAKEINDIA", 40, 161.49, "Manufacturing"),
    ("POWERGRID", 45, 278.55, "Power/Utility"),
    ("MASPTOP50", 64, 79.00, "US Large-cap"),
    ("COALINDIA", 9, 430.85, "Coal/Mining"),
    ("GROWW", 15, 192.10, "Fintech"),
    ("SILVERBEES", 10, 208.92, "Silver"),
    ("METAL", 20, 13.64, "Metals"),
    ("CASTROLIND", 30, 192.50, "Lubricants"),
    ("NMDC", 50, 86.70, "Metals & Mining"),
    ("LIQUIDCASE", 42, 114.80, "Cash Eq"),
]
RISHU = [
    ("SBIN", 100, 881.35, "Banking"),
    ("MONIFTY500", 9246, 23.62, "Broad Market"),
    ("TMCV", 225, 319.60, "Auto"),
    ("EXIDEIND", 70, 562.67, "Auto Components"),
    ("NMDC", 566, 88.37, "Metals & Mining"),
    ("GOLDBEES", 324, 120.33, "Gold"),
    ("ENERGY", 1484, 40.44, "Energy"),
    ("CASTROLIND", 135, 185.29, "Lubricants"),
    ("POWERGRID", 286, 284.72, "Power/Utility"),
    ("MIDCAPETF", 989, 20.42, "Mid-cap Blend"),
    ("NEXT50IETF", 198, 75.51, "Large-cap Blend"),
    ("COALINDIA", 22, 452.70, "Coal/Mining"),
    ("HDFCSML250", 65, 150.67, "Small-cap Blend"),
    ("SRF", 4, 2312.09, "Chemicals"),
    ("IEX", 45, 198.36, "Power Exchange"),
    ("NIFTYBEES", 90, 275.90, "Large-cap Blend"),
    ("LIQUIDCASE", 431, 114.89, "Cash Eq"),
    ("MAFANG", 103, 194.20, "US Tech"),
]


def build(rows, name):
    hs = []
    for t, q, a, s in rows:
        hs.append(Holding(ticker=t, name=t, quantity=q, avg_price=a, sector=s, current_price=None))
    from engine import Portfolio

    return compute_all(
        Portfolio(holdings=hs), benchmark_choice="^NSEI", risk_profile_key="moderate", risk_free_rate=0.065
    )


def dump(report, name, prices):
    r = report.risk
    mc = report.monte_carlo
    ins = report.institutional_scores
    rec = report.recommendations
    print(f"\n{'=' * 72}\n  {name.upper()} — RISK SCANNER (moderate profile, rf=6.5%, ^NSEI)\n{'=' * 72}")
    tot = report.portfolio.total_current
    print(f"Holdings: {report.portfolio.holding_count}  | Current value: ₹{tot:,.0f}")
    print("\n-- RISK METRICS --")
    print(f"  Annual Volatility:      {r.volatility_annual:.2f}%")
    print(f"  VaR 95% (1d):           {r.var_95:.2f}%  (₹{tot * r.var_95 / 100:,.0f})")
    print(f"  CVaR 95% (1d):          {r.cvar_95:.2f}%  (₹{tot * r.cvar_95 / 100:,.0f})")
    print(f"  VaR 99% (1d):           {r.var_99:.2f}%")
    print(f"  Max Drawdown (1y):      {r.max_drawdown:.2f}%  ({r.max_drawdown_start} → {r.max_drawdown_end})")
    print(f"  Sharpe:                 {r.sharpe:.2f}")
    print(f"  Sortino:                {r.sortino:.2f}")
    print(f"  Calmar:                 {r.calmar_ratio:.2f}")
    print(f"  CAGR:                   {r.cagr:.2f}%")
    print(f"  Beta (vs Nifty):        {r.beta:.2f}")
    print(f"  Corr to Nifty:          {r.correlation_to_benchmark:.2f}")
    if mc:
        print("\n-- MONTE CARLO (10k paths, 1y) --")
        print(f"  Median return:          {mc.median_return:.2f}%")
        print(f"  Expected return:        {mc.expected_return:.2f}%")
        print(f"  1y VaR 95%:             {mc.var_95:.2f}%  (₹{tot * mc.var_95 / 100:,.0f})")
        print(f"  1y CVaR 95%:            {mc.cvar_95:.2f}%  (₹{tot * mc.cvar_95 / 100:,.0f})")
        print(f"  Prob of Profit:         {mc.prob_profit:.1f}%")
        print(f"  95% CI:                 [{mc.ci_lower:.1f}%, {mc.ci_upper:.1f}%]")
    if ins:
        print("\n-- INSTITUTIONAL SCORES (P×I×C) --")
        for attr in [
            "overall_risk_score",
            "probability_rating",
            "impact_rating",
            "composite_rating",
            "risk_tier",
            "diversification_score",
            "concentration_risk",
            "liquidity_risk",
            "tail_risk",
        ]:
            v = getattr(ins, attr, None)
            if v is not None:
                print(f"  {attr:24s}: {v}")
    if rec:
        print("\n-- RECOMMENDATIONS --")
        for a in getattr(rec, "actions", []) or []:
            print(
                f"  [{a.severity if hasattr(a, 'severity') else ''}] {a.ticker if hasattr(a, 'ticker') else ''}: {a.rationale if hasattr(a, 'rationale') else a}"
            )
        top = getattr(rec, "top_actions", None)
        if top:
            for a in top:
                print("  TOP:", a)


ra, pa = build(ASHAY, "Ashay")
dump(ra, "Ashay", pa)
rr, pr = build(RISHU, "Rishu")
dump(rr, "Rishu", pr)
