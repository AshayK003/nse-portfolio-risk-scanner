#!/usr/bin/env python3
import sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from engine import Holding, Portfolio
from engine.compute import compute_all
from engine.risk import compute_stock_risk_attribution

# Independent live prices I pulled earlier today via yfinance (18 Aug 2026) — cross-check source
INDEPENDENT = {
    "HDFCBANK":725.05,"NEXT50IETF":78.85,"NIFTYBEES":276.38,"VEDL":267.15,"MIDCAPETF":23.91,
    "ENERGY":39.00,"GOLDBEES":126.42,"MODEFENCE":108.80,"MONIFTY500":24.09,"MAKEINDIA":169.05,
    "POWERGRID":266.85,"MASPTOP50":81.02,"COALINDIA":410.80,"GROWW":193.75,"SILVERBEES":222.09,
    "METAL":13.20,"CASTROLIND":187.59,"NMDC":83.73,"LIQUIDCASE":115.40,
    "SBIN":1060.00,"TMCV":472.20,"EXIDEIND":469.10,"NMDC":83.73,"HDFCSML250":184.89,
    "SRF":2631.00,"IEX":125.25,"MAFANG":209.43,
}

ASHAY = [
    ("HDFCBANK",24,765.36,"Banking"),("NEXT50IETF",180,74.73,"Large-cap Blend"),
    ("NIFTYBEES",60,257.11,"Large-cap Blend"),("VEDL",25,276.40,"Metals"),
    ("MIDCAPETF",500,20.51,"Mid-cap Blend"),("ENERGY",279,40.49,"Energy"),
    ("GOLDBEES",65,126.29,"Gold"),("MODEFENCE",70,101.21,"Defence"),
    ("MONIFTY500",280,23.61,"Broad Market"),("MAKEINDIA",40,161.49,"Manufacturing"),
    ("POWERGRID",45,278.55,"Power/Utility"),("MASPTOP50",64,79.00,"US Large-cap"),
    ("COALINDIA",9,430.85,"Coal/Mining"),("GROWW",15,192.10,"Fintech"),
    ("SILVERBEES",10,208.92,"Silver"),("METAL",20,13.64,"Metals"),
    ("CASTROLIND",30,192.50,"Lubricants"),("NMDC",50,86.70,"Metals & Mining"),
    ("LIQUIDCASE",42,114.80,"Cash Eq"),
]
RISHU = [
    ("SBIN",100,881.35,"Banking"),("MONIFTY500",9246,23.62,"Broad Market"),
    ("TMCV",225,319.60,"Auto"),("EXIDEIND",70,562.67,"Auto Components"),
    ("NMDC",566,88.37,"Metals & Mining"),("GOLDBEES",324,120.33,"Gold"),
    ("ENERGY",1484,40.44,"Energy"),("CASTROLIND",135,185.29,"Lubricants"),
    ("POWERGRID",286,284.72,"Power/Utility"),("MIDCAPETF",989,20.42,"Mid-cap Blend"),
    ("NEXT50IETF",198,75.51,"Large-cap Blend"),("COALINDIA",22,452.70,"Coal/Mining"),
    ("HDFCSML250",65,150.67,"Small-cap Blend"),("SRF",4,2312.09,"Chemicals"),
    ("IEX",45,198.36,"Power Exchange"),("NIFTYBEES",90,275.90,"Large-cap Blend"),
    ("LIQUIDCASE",431,114.89,"Cash Eq"),("MAFANG",103,194.20,"US Tech"),
]

def build(rows):
    hs=[Holding(ticker=t,name=t,quantity=q,avg_price=a,sector=s,current_price=None) for t,q,a,s in rows]
    # force_refresh=True -> bypass 24h disk cache, fetch live
    return compute_all(Portfolio(holdings=hs), benchmark_choice="^NSEI", risk_profile_key="moderate", risk_free_rate=0.065, force_refresh=True)

for nm, rows in [("ASHAY",ASHAY),("RISHU",RISHU)]:
    rep, ctx = build(rows)
    print("\n"+"="*72); print(nm); print("="*72)
    # ---- INPUT VALIDATION: engine's fetched latest price vs independent pull ----
    print("\n[INPUT CROSS-CHECK] engine latest Close vs my earlier yfinance pull:")
    prices = ctx.prices
    bad=0
    for tk in prices.columns:
        eng = float(prices[tk].iloc[-1])
        ind = INDEPENDENT.get(tk)
        if ind is None:
            print(f"  {tk:14s} engine={eng:9.2f}  (no independent ref)")
            continue
        diff = (eng-ind)/ind*100
        flag = "  OK" if abs(diff)<1.0 else "  <-- MISMATCH"
        if abs(diff)>=1.0: bad+=1
        print(f"  {tk:14s} engine={eng:9.2f}  indep={ind:9.2f}  diff={diff:+5.2f}%{flag}")
    print(f"  -> mismatches>1%: {bad}")
    # ---- INSTITUTIONAL SCORES (full) ----
    ins = rep.institutional_scores
    print("\n[INSTITUTIONAL SCORES]")
    if ins:
        for k,v in vars(ins).items():
            print(f"  {k}: {v}")
    else:
        print("  NONE (module returned None — check for silent failure)")
    # ---- RECOMMENDATIONS (full) ----
    rec = rep.recommendations
    print("\n[RECOMMENDATIONS]")
    if rec:
        for k,v in vars(rec).items():
            if isinstance(v,list):
                print(f"  {k}: [{len(v)} items]")
                for it in v[:20]:
                    print("    -", it)
            else:
                print(f"  {k}: {v}")
    else:
        print("  NONE")
    # ---- REGIME ----
    reg = rep.regime
    print("\n[REGIME]")
    if reg:
        for k,v in vars(reg).items():
            if k!="state_sequence": print(f"  {k}: {v}")
    # ---- FACTOR REPORT ----
    fr = rep.factor_report
    print("\n[FACTOR REPORT]")
    if fr:
        for k,v in vars(fr).items():
            if k!="factors": print(f"  {k}: {v}")
        for f in getattr(fr,"factors",[]):
            print(f"    factor {f.name}: exp={f.exposure} risk%={f.risk_contribution_pct}")
    # ---- RISK ATTRIBUTION ----
    print("\n[RISK ATTRIBUTION — top contributors]")
    ra = compute_stock_risk_attribution(prices, ctx.weights, ctx.stock_betas)
    if not ra.empty:
        ra = ra.sort_values("Risk Contrib (%)", ascending=False)
        for _,row in ra.head(8).iterrows():
            print(f"  {row['Ticker']:14s} wt={row['Weight (%)']:5.1f}%  risk%={row['Risk Contrib (%)']:5.1f}%  beta={row['Beta']}  vol={row['Ann. Vol (%)']}%")
    # ---- EARLY WARNINGS ----
    print("\n[EARLY WARNINGS]")
    w = rep.warnings
    if w and getattr(w, "signals", None):
        print(f"  overall_level: {getattr(w,'overall_warning_level','?')}  | counts: {getattr(w,'signal_count_by_severity',{})}")
        for s in w.signals:
            print(f"  [{s.severity.value}] {s.name}: {s.description} -> {s.suggested_action}")
    else:
        print("  none")
