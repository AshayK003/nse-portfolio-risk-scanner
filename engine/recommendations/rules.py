# engine/recommendations/rules.py
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from engine.recommendations.types import (
    ActionType,
    RegimeContext,
    RuleVerdict,
    TaxLot,
    Urgency,
)


class FiiDiiBias(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


# ─── Context passed to every rule ──────────────────────────────────


@dataclass(frozen=True)
class RecommendationContext:
    # Portfolio state
    holdings: dict[str, TaxLot]  # ticker -> TaxLot
    sector_weights: dict[str, float]  # sector -> weight %
    asset_class_weights: dict[str, float]  # equity/etf/gold/cash
    total_value: float
    cash_available: float

    # Market regime
    regime: RegimeContext
    vix: float
    adx: float
    nifty_ma200_dist_pct: float
    breadth_ad_ratio: float
    fii_dii_bias: FiiDiiBias
    is_expiry_week: bool

    # User constraints (from profile)
    max_stcg_budget: float  # ₹ willing to realize STCG
    max_ltcg_budget: float  # ₹ willing to realize LTCG
    max_single_trade_pct: float  # max % of portfolio per trade
    max_sector_weight: float  # sector cap
    max_single_name_weight: float  # single stock cap
    min_cash_floor: float  # emergency cash
    tax_loss_harvest_enabled: bool
    horizon_years: int  # investment horizon

    # Derived
    portfolio_sharpe: float
    portfolio_vol_annual: float
    portfolio_var_95: float


# ─── Rule function signature ───────────────────────────────────────

RuleFn = Callable[[RecommendationContext], list[RuleVerdict]]


# ─── Individual Rules ──────────────────────────────────────────────


def rule_concentration_single_name(ctx: RecommendationContext) -> list[RuleVerdict]:
    """Any holding > max_single_name_weight → TRIM excess"""
    verdicts = []
    for ticker, lot in ctx.holdings.items():
        weight = (lot.qty * lot.current_price) / ctx.total_value * 100
        if weight > ctx.max_single_name_weight:
            excess_weight = weight - ctx.max_single_name_weight
            excess_qty = max(0, int(excess_weight * ctx.total_value / lot.current_price))
            if excess_qty > 0:
                verdicts.append(
                    RuleVerdict(
                        rule_name="concentration_single_name",
                        action=ActionType.TRIM,
                        ticker=ticker,
                        qty=excess_qty,
                        urgency=Urgency.NEAR_TERM,
                        confidence=0.95,
                        reason=f"{ticker} at {weight:.1f}% > {ctx.max_single_name_weight:.1f}% cap",
                        risk_delta_bps=int(excess_weight * 50),
                        tax_cost=_estimate_tax(lot, excess_qty),
                        impact_cost=_estimate_impact(ticker, excess_qty, lot.current_price, ctx),
                        net_benefit_bps=0,
                    )
                )
    return verdicts


def rule_concentration_sector(ctx: RecommendationContext) -> list[RuleVerdict]:
    """Any sector > max_sector_weight → TRIM largest holding in sector"""
    verdicts = []
    for sector, weight in ctx.sector_weights.items():
        if weight > ctx.max_sector_weight:
            sector_holdings = [(t, lot) for t, lot in ctx.holdings.items() if _get_sector(t) == sector]
            if sector_holdings:
                ticker, lot = max(sector_holdings, key=lambda x: x[1].qty * x[1].current_price)
                excess_weight = weight - ctx.max_sector_weight
                excess_qty = max(0, int(excess_weight * ctx.total_value / lot.current_price))
                if excess_qty > 0:
                    verdicts.append(
                        RuleVerdict(
                            rule_name="concentration_sector",
                            action=ActionType.TRIM,
                            ticker=ticker,
                            qty=excess_qty,
                            urgency=Urgency.NEAR_TERM,
                            confidence=0.9,
                            reason=f"{sector} at {weight:.1f}% > {ctx.max_sector_weight:.1f}% cap",
                            risk_delta_bps=int(excess_weight * 30),
                            tax_cost=_estimate_tax(lot, excess_qty),
                            impact_cost=_estimate_impact(ticker, excess_qty, lot.current_price, ctx),
                            net_benefit_bps=0,
                        )
                    )
    return verdicts


def rule_sharpe_underperformance(ctx: RecommendationContext) -> list[RuleVerdict]:
    """Portfolio Sharpe < 0.5 → flag for rebalance"""
    if ctx.portfolio_sharpe >= 0.5:
        return []

    return [
        RuleVerdict(
            rule_name="sharpe_underperformance",
            action=ActionType.BUY,
            ticker="PORTFOLIO",
            qty=0,
            urgency=Urgency.ROUTINE,
            confidence=0.7,
            reason=f"Portfolio Sharpe {ctx.portfolio_sharpe:.2f} < 0.5 target",
            risk_delta_bps=-200,
            tax_cost=0,
            impact_cost=0,
            net_benefit_bps=0,
        )
    ]


def rule_regime_vix_spike(ctx: RecommendationContext) -> list[RuleVerdict]:
    """VIX > 28 → block new SHORT, reduce LONG size by 50%"""
    if ctx.vix <= 28:
        return []

    verdicts = []
    for ticker, lot in ctx.holdings.items():
        if _is_short_candidate(lot, ctx):
            verdicts.append(
                RuleVerdict(
                    rule_name="regime_vix_spike",
                    action=ActionType.BLOCK,
                    ticker=ticker,
                    qty=lot.qty,
                    urgency=Urgency.IMMEDIATE,
                    confidence=0.95,
                    reason=f"VIX {ctx.vix:.1f} > 28 — panic regime, no new shorts",
                    risk_delta_bps=0,
                    tax_cost=0,
                    impact_cost=0,
                    net_benefit_bps=0,
                )
            )
        else:
            trim_qty = int(lot.qty * 0.5)
            if trim_qty > 0:
                verdicts.append(
                    RuleVerdict(
                        rule_name="regime_vix_spike",
                        action=ActionType.TRIM,
                        ticker=ticker,
                        qty=trim_qty,
                        urgency=Urgency.IMMEDIATE,
                        confidence=0.8,
                        reason=f"VIX {ctx.vix:.1f} > 28 — reduce long exposure 50%",
                        risk_delta_bps=-100,
                        tax_cost=_estimate_tax(lot, trim_qty),
                        impact_cost=_estimate_impact(ticker, trim_qty, lot.current_price, ctx),
                        net_benefit_bps=0,
                    )
                )
    return verdicts


def rule_regime_adx_doldrums(ctx: RecommendationContext) -> list[RuleVerdict]:
    """ADX < 15 → range-bound, block breakout strategies"""
    if ctx.adx >= 15:
        return []

    return [
        RuleVerdict(
            rule_name="regime_adx_doldrums",
            action=ActionType.BLOCK,
            ticker="PORTFOLIO",
            qty=0,
            urgency=Urgency.NEAR_TERM,
            confidence=0.85,
            reason=f"ADX {ctx.adx:.1f} < 15 — range-bound, breakout signals unreliable",
            risk_delta_bps=0,
            tax_cost=0,
            impact_cost=0,
            net_benefit_bps=0,
        )
    ]


def rule_breadth_confirmation(ctx: RecommendationContext) -> list[RuleVerdict]:
    """A/D ratio misaligned with portfolio bias"""
    verdicts = []
    portfolio_bias = _portfolio_net_bias(ctx.holdings)

    if portfolio_bias > 0 and ctx.breadth_ad_ratio < 0.7:
        # Portfolio long but breadth weak
        for ticker, lot in ctx.holdings.items():
            if lot.unrealized_pnl > 0:
                trim_qty = int(lot.qty * 0.3)
                if trim_qty > 0:
                    verdicts.append(
                        RuleVerdict(
                            rule_name="breadth_confirmation",
                            action=ActionType.TRIM,
                            ticker=ticker,
                            qty=trim_qty,
                            urgency=Urgency.NEAR_TERM,
                            confidence=0.7,
                            reason=f"A/D ratio {ctx.breadth_ad_ratio:.2f} < 0.7 — breadth contradicts long bias",
                            risk_delta_bps=-50,
                            tax_cost=_estimate_tax(lot, trim_qty),
                            impact_cost=_estimate_impact(ticker, trim_qty, lot.current_price, ctx),
                            net_benefit_bps=0,
                        )
                    )
    elif portfolio_bias < 0 and ctx.breadth_ad_ratio > 1.5:
        # Portfolio short but breadth strong
        for ticker, lot in ctx.holdings.items():
            if lot.unrealized_pnl < 0:
                trim_qty = int(lot.qty * 0.3)
                if trim_qty > 0:
                    verdicts.append(
                        RuleVerdict(
                            rule_name="breadth_confirmation",
                            action=ActionType.TRIM,
                            ticker=ticker,
                            qty=trim_qty,
                            urgency=Urgency.NEAR_TERM,
                            confidence=0.7,
                            reason=f"A/D ratio {ctx.breadth_ad_ratio:.2f} > 1.5 — breadth contradicts short bias",
                            risk_delta_bps=-50,
                            tax_cost=_estimate_tax(lot, trim_qty),
                            impact_cost=_estimate_impact(ticker, trim_qty, lot.current_price, ctx),
                            net_benefit_bps=0,
                        )
                    )
    return verdicts


def rule_fii_dii_confluence(ctx: RecommendationContext) -> list[RuleVerdict]:
    """FII/DII bias contradicts portfolio direction"""
    verdicts = []
    portfolio_bias = _portfolio_net_bias(ctx.holdings)

    # Handle both enum and string
    fii_dii = ctx.fii_dii_bias
    if hasattr(fii_dii, "value"):
        fii_dii = fii_dii.value
    is_bearish = fii_dii == "bearish"
    is_bullish = fii_dii == "bullish"

    if portfolio_bias > 0 and is_bearish:
        for ticker, lot in ctx.holdings.items():
            trim_qty = int(lot.qty * 0.5)
            if trim_qty > 0:
                verdicts.append(
                    RuleVerdict(
                        rule_name="fii_dii_confluence",
                        action=ActionType.TRIM,
                        ticker=ticker,
                        qty=trim_qty,
                        urgency=Urgency.NEAR_TERM,
                        confidence=0.75,
                        reason="FII/DII bearish contradicts long portfolio bias",
                        risk_delta_bps=-75,
                        tax_cost=_estimate_tax(lot, trim_qty),
                        impact_cost=_estimate_impact(ticker, trim_qty, lot.current_price, ctx),
                        net_benefit_bps=0,
                    )
                )
    elif portfolio_bias < 0 and is_bullish:
        for ticker, lot in ctx.holdings.items():
            trim_qty = int(lot.qty * 0.5)
            if trim_qty > 0:
                verdicts.append(
                    RuleVerdict(
                        rule_name="fii_dii_confluence",
                        action=ActionType.TRIM,
                        ticker=ticker,
                        qty=trim_qty,
                        urgency=Urgency.NEAR_TERM,
                        confidence=0.75,
                        reason="FII/DII bullish contradicts short portfolio bias",
                        risk_delta_bps=-75,
                        tax_cost=_estimate_tax(lot, trim_qty),
                        impact_cost=_estimate_impact(ticker, trim_qty, lot.current_price, ctx),
                        net_benefit_bps=0,
                    )
                )
    return verdicts


def rule_expiry_week(ctx: RecommendationContext) -> list[RuleVerdict]:
    """Expiry week → reduce all position sizes by 20%"""
    if not ctx.is_expiry_week:
        return []

    verdicts = []
    for ticker, lot in ctx.holdings.items():
        trim_qty = int(lot.qty * 0.2)
        if trim_qty > 0:
            verdicts.append(
                RuleVerdict(
                    rule_name="expiry_week",
                    action=ActionType.TRIM,
                    ticker=ticker,
                    qty=trim_qty,
                    urgency=Urgency.IMMEDIATE,
                    confidence=0.6,
                    reason="Expiry week — reduce all position sizes 20%",
                    risk_delta_bps=-30,
                    tax_cost=_estimate_tax(lot, trim_qty),
                    impact_cost=_estimate_impact(ticker, trim_qty, lot.current_price, ctx),
                    net_benefit_bps=0,
                )
            )
    return verdicts


def rule_tax_loss_harvest(ctx: RecommendationContext) -> list[RuleVerdict]:
    """Harvest losses > ₹5,000 unrealized → SELL for STCG offset"""
    if not ctx.tax_loss_harvest_enabled:
        return []

    verdicts = []
    for ticker, lot in ctx.holdings.items():
        if lot.unrealized_pnl < -5000 and lot.is_ltcg is False and ctx.max_stcg_budget > 0:
            verdicts.append(
                RuleVerdict(
                    rule_name="tax_loss_harvest",
                    action=ActionType.SELL,
                    ticker=ticker,
                    qty=lot.qty,
                    urgency=Urgency.NEAR_TERM,
                    confidence=0.85,
                    reason=f"Tax loss harvest: ₹{abs(lot.unrealized_pnl):,.0f} STCL available",
                    risk_delta_bps=0,
                    tax_cost=0,  # saves tax
                    impact_cost=_estimate_impact(ticker, lot.qty, lot.current_price, ctx),
                    net_benefit_bps=0,
                )
            )
    return verdicts


def rule_cash_floor(ctx: RecommendationContext) -> list[RuleVerdict]:
    """Cash below min_cash_floor → SELL lowest conviction to raise cash"""
    if ctx.cash_available >= ctx.min_cash_floor:
        return []

    deficit = ctx.min_cash_floor - ctx.cash_available
    # Sort by worst risk-adjusted return (placeholder: lowest unrealized P&L %)
    sorted_holdings = sorted(
        ctx.holdings.items(), key=lambda x: x[1].unrealized_pnl / (x[1].qty * x[1].avg_price)
    )

    verdicts = []
    raised = 0.0
    for ticker, lot in sorted_holdings:
        if raised >= deficit:
            break
        sell_qty = min(lot.qty, int((deficit - raised) / lot.current_price))
        if sell_qty > 0:
            verdicts.append(
                RuleVerdict(
                    rule_name="cash_floor",
                    action=ActionType.SELL,
                    ticker=ticker,
                    qty=sell_qty,
                    urgency=Urgency.IMMEDIATE,
                    confidence=0.9,
                    reason=f"Cash ₹{ctx.cash_available:,.0f} < floor ₹{ctx.min_cash_floor:,.0f} — raise ₹{deficit:,.0f}",
                    risk_delta_bps=0,
                    tax_cost=_estimate_tax(lot, sell_qty),
                    impact_cost=_estimate_impact(ticker, sell_qty, lot.current_price, ctx),
                    net_benefit_bps=0,
                )
            )
            raised += sell_qty * lot.current_price
    return verdicts


def rule_etf_overlap(ctx: RecommendationContext) -> list[RuleVerdict]:
    """Multiple ETFs tracking same index → consolidate"""
    verdicts = []
    # Detect Nifty 50 overlap: NIFTYBEES, MONIFTY500, NEXT50IETF, etc.
    nifty50_etfs = [t for t in ctx.holdings if any(x in t for x in ["NIFTYBEES", "MONIFTY500", "NEXT50IETF"])]
    if len(nifty50_etfs) > 1:
        # Keep largest, trim others
        sorted_etfs = sorted(
            nifty50_etfs, key=lambda t: ctx.holdings[t].qty * ctx.holdings[t].current_price, reverse=True
        )
        keep = sorted_etfs[0]
        for ticker in sorted_etfs[1:]:
            lot = ctx.holdings[ticker]
            verdicts.append(
                RuleVerdict(
                    rule_name="etf_overlap",
                    action=ActionType.TRIM,
                    ticker=ticker,
                    qty=lot.qty,
                    urgency=Urgency.NEAR_TERM,
                    confidence=0.8,
                    reason=f"ETF overlap: {ticker} duplicates {keep} (Nifty 50 exposure)",
                    risk_delta_bps=-20,
                    tax_cost=_estimate_tax(lot, lot.qty),
                    impact_cost=_estimate_impact(ticker, lot.qty, lot.current_price, ctx),
                    net_benefit_bps=0,
                )
            )
    return verdicts


# ─── Rule Registry (Governance Pattern) ────────────────────────────

RULES: list[tuple[str, RuleFn]] = [
    ("VIX Spike", rule_regime_vix_spike),
    ("ADX Doldrums", rule_regime_adx_doldrums),
    ("Breadth Confirmation", rule_breadth_confirmation),
    ("FII/DII Confluence", rule_fii_dii_confluence),
    ("Expiry Week", rule_expiry_week),
    ("Concentration: Single Name", rule_concentration_single_name),
    ("Concentration: Sector", rule_concentration_sector),
    ("ETF Overlap", rule_etf_overlap),
    ("Sharpe Underperformance", rule_sharpe_underperformance),
    ("Tax Loss Harvest", rule_tax_loss_harvest),
    ("Cash Floor", rule_cash_floor),
]


def apply_recommendation_rules(ctx: RecommendationContext) -> list[RuleVerdict]:
    """Apply all rules. Strictest override wins (governance pattern)."""
    all_verdicts = []

    for rule_name, rule_fn in RULES:
        try:
            result = rule_fn(ctx)
            if result:
                all_verdicts.extend(result)
        except Exception as e:
            # Log and continue — one bad rule doesn't crash pipeline
            import logging

            logging.getLogger(__name__).warning(f"Rule '{rule_name}' failed: {e}")
            continue

    # Deduplicate by (ticker, action) — keep highest confidence
    seen = {}
    for v in all_verdicts:
        key = (v.ticker, v.action)
        if key not in seen or v.confidence > seen[key].confidence:
            seen[key] = v

    return list(seen.values())


# ─── Helpers ────────────────────────────────────────────────────────


def _get_sector(ticker: str) -> str:
    """Map ticker to sector — in production, load from sector mapping file"""
    sector_map = {
        "HDFCBANK": "Banking",
        "ICICIBANK": "Banking",
        "SBIN": "Banking",
        "NIFTYBEES": "Broad Market",
        "MONIFTY500": "Broad Market",
        "MIDCAPETF": "Broad Market",
        "NEXT50IETF": "Broad Market",
        "POWERGRID": "Power",
        "ENERGY": "Energy",
        "GOLDBEES": "Gold",
        "SILVERBEES": "Gold",
        "VEDL": "Metals",
        "NMDC": "Metals",
        "METAL": "Metals",
        "COALINDIA": "Mining",
        "CASTROLIND": "Lubricants",
        "LIQUIDCASE": "Cash",
        "MAFANG": "International",
        "MASPTOP50": "International",
        "MAKEINDIA": "Manufacturing",
        "SRF": "Chemicals",
        "EXIDEIND": "Auto",
        "TMCV": "Auto",
        "GROWW": "Fintech",
        "HDFCSML250": "Small Cap",
        "IEX": "Power",
        "MODEFENCE": "Defence",
    }
    base = ticker.replace(".NS", "").replace(".BO", "")
    return sector_map.get(base, "Other")


def _portfolio_net_bias(holdings: dict[str, TaxLot]) -> float:
    """Net portfolio directional bias: +1 long, -1 short, 0 neutral"""
    long_val = sum(lot.qty * lot.current_price for lot in holdings.values() if lot.unrealized_pnl >= 0)
    short_val = sum(lot.qty * lot.current_price for lot in holdings.values() if lot.unrealized_pnl < 0)
    total = long_val + short_val
    if total == 0:
        return 0.0
    return (long_val - short_val) / total


def _is_short_candidate(lot: TaxLot, ctx: RecommendationContext) -> bool:
    """Heuristic: is this holding a short candidate?"""
    # Simplified: if unrealized loss > 10% and sector weak
    return lot.unrealized_pnl / (lot.qty * lot.avg_price) < -0.10


def _estimate_tax(lot: TaxLot, qty: int) -> float:
    """Estimate tax on selling qty shares"""
    if qty <= 0:
        return 0.0
    gain_per_share = lot.current_price - lot.avg_price
    total_gain = gain_per_share * qty
    if total_gain <= 0:
        return 0.0  # loss — no tax
    if lot.is_ltcg:
        return max(0.0, (total_gain - 100000) * 0.10)  # LTCG 10% > 1L
    else:
        return total_gain * 0.15  # STCG 15%


def _estimate_impact(ticker: str, qty: int, price: float, ctx: RecommendationContext) -> float:
    """Estimate market impact cost"""
    # Placeholder: use 0.1% for liquid, 0.5% for illiquid
    adv = _get_adv_20d(ticker)
    if adv == 0:
        return 0.0
    participation = (qty * price) / adv
    if participation < 0.01:
        slippage_bps = 5
    elif participation < 0.05:
        slippage_bps = 20
    else:
        slippage_bps = 50
    return (qty * price) * (slippage_bps / 10000)


def _get_adv_20d(ticker: str) -> float:
    """Get 20-day average daily volume (₹) — placeholder"""
    # In production, fetch from data engine
    adv_map = {
        "HDFCBANK": 500_000_000,
        "SBIN": 300_000_000,
        "NIFTYBEES": 200_000_000,
        "MONIFTY500": 100_000_000,
        "POWERGRID": 100_000_000,
        "VEDL": 50_000_000,
        "NMDC": 30_000_000,
        "COALINDIA": 100_000_000,
    }
    base = ticker.replace(".NS", "").replace(".BO", "")
    return adv_map.get(base, 10_000_000)
