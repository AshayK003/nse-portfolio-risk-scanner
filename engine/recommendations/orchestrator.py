# engine/recommendations/orchestrator.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from engine.recommendations.rules import apply_recommendation_rules
from engine.recommendations.types import (
    ActionType,
    FiiDiiBias,
    RecommendationCard,
    RecommendationContext,
    RecommendationReport,
    RegimeContext,
    RuleVerdict,
    TaxLot,
    Urgency,
)


@dataclass
class PortfolioSnapshot:
    """Raw portfolio data from the engine"""

    holdings: list[dict]  # [{ticker, name, qty, avg_price, current_price, ...}]
    total_value: float
    cash_available: float
    sector_weights: dict[str, float]
    asset_class_weights: dict[str, float]


@dataclass
class MarketData:
    """Market regime data from data engine"""

    vix: float
    adx: float
    nifty_ma200_dist_pct: float
    breadth_ad_ratio: float
    fii_dii_bias: FiiDiiBias
    is_expiry_week: bool
    regime: RegimeContext


@dataclass
class UserProfile:
    """User constraints from profile/settings"""

    max_stcg_budget: float = 100000
    max_ltcg_budget: float = 500000
    max_single_trade_pct: float = 10.0
    max_sector_weight: float = 20.0
    max_single_name_weight: float = 15.0
    min_cash_floor: float = 50000
    tax_loss_harvest_enabled: bool = True
    horizon_years: int = 5


def build_tax_lots(snapshot: PortfolioSnapshot) -> dict[str, TaxLot]:
    """Convert portfolio holdings to TaxLot objects with computed fields"""
    lots = {}
    for h in snapshot.holdings:
        ticker = h["ticker"]
        qty = h["quantity"]
        avg_price = h["avg_price"]
        current_price = h.get("current_price", avg_price)
        purchase_date = _parse_purchase_date(h)

        unrealized_pnl = (current_price - avg_price) * qty
        holding_days = (date.today() - purchase_date).days
        is_ltcg = holding_days > 365

        lots[ticker] = TaxLot(
            ticker=ticker,
            qty=qty,
            avg_price=avg_price,
            purchase_date=purchase_date,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            holding_days=holding_days,
            is_ltcg=is_ltcg,
            stcg_tax=0.15,
            ltcg_tax=0.10,
        )
    return lots


def build_recommendation_context(
    snapshot: PortfolioSnapshot,
    market_data: MarketData,
    user_profile: UserProfile,
) -> RecommendationContext:
    """Assemble full context for rule engine"""
    tax_lots = build_tax_lots(snapshot)

    return RecommendationContext(
        holdings=tax_lots,
        sector_weights=snapshot.sector_weights,
        asset_class_weights=snapshot.asset_class_weights,
        total_value=snapshot.total_value,
        cash_available=snapshot.cash_available,
        regime=market_data.regime,
        vix=market_data.vix,
        adx=market_data.adx,
        nifty_ma200_dist_pct=market_data.nifty_ma200_dist_pct,
        breadth_ad_ratio=market_data.breadth_ad_ratio,
        fii_dii_bias=market_data.fii_dii_bias,
        is_expiry_week=market_data.is_expiry_week,
        max_stcg_budget=user_profile.max_stcg_budget,
        max_ltcg_budget=user_profile.max_ltcg_budget,
        max_single_trade_pct=user_profile.max_single_trade_pct,
        max_sector_weight=user_profile.max_sector_weight,
        max_single_name_weight=user_profile.max_single_name_weight,
        min_cash_floor=user_profile.min_cash_floor,
        tax_loss_harvest_enabled=user_profile.tax_loss_harvest_enabled,
        horizon_years=user_profile.horizon_years,
        portfolio_sharpe=0.0,  # computed elsewhere
        portfolio_vol_annual=0.0,
        portfolio_var_95=0.0,
    )


def generate_recommendation_cards(
    verdicts: list[RuleVerdict],
    ctx: RecommendationContext,
) -> list[RecommendationCard]:
    """Convert rule verdicts into deduplicated, prioritized recommendation cards"""
    # Group verdicts by action + ticker
    groups = {}
    block_verdicts = []

    for v in verdicts:
        if v.action == ActionType.BLOCK:
            block_verdicts.append(v)
            continue
        key = (v.action, v.ticker)
        if key not in groups:
            groups[key] = []
        groups[key].append(v)

    # Attach relevant BLOCK verdicts to each group
    for key, group_verdicts in groups.items():
        action, ticker = key
        for block_v in block_verdicts:
            # Attach BLOCK verdicts that are portfolio-wide or match this ticker
            if block_v.ticker == "PORTFOLIO" or block_v.ticker == ticker:
                group_verdicts.append(block_v)

    cards = []
    for i, ((action, ticker), group_verdicts) in enumerate(groups.items()):
        # Aggregate quantities (max across rules)
        total_qty = max(v.qty for v in group_verdicts)
        avg_price = ctx.holdings[ticker].current_price if ticker in ctx.holdings else 0

        # Compute net benefit
        net_risk_reduction = sum(v.risk_delta_bps for v in group_verdicts)
        total_tax = sum(v.tax_cost for v in group_verdicts)
        total_impact = sum(v.impact_cost for v in group_verdicts)
        net_benefit = net_risk_reduction - int((total_tax + total_impact) / ctx.total_value * 10000)

        # Weighted confidence
        total_weight = sum(v.confidence for v in group_verdicts)
        weighted_conf = (
            sum(v.confidence * v.confidence for v in group_verdicts) / total_weight if total_weight > 0 else 0
        )

        # Guardrails
        guardrails = _build_guardrails(action, ticker, group_verdicts, ctx)

        # Alternatives
        alternatives = _build_alternatives(action, ticker, ctx)

        card = RecommendationCard(
            id=f"{action.value}_{ticker}_{i}",
            title=_card_title(action, ticker),
            priority=i + 1,
            urgency=max((v.urgency for v in group_verdicts), key=lambda u: u.value),
            action=action,
            tickers=[ticker] if ticker != "PORTFOLIO" else [],
            qtys={ticker: total_qty} if ticker != "PORTFOLIO" else {},
            prices={ticker: avg_price} if ticker != "PORTFOLIO" else {},
            reason=group_verdicts[0].reason,
            regime_context=ctx.regime,
            rule_verdicts=group_verdicts,
            tax_breakdown={ticker: sum(v.tax_cost for v in group_verdicts)},
            impact_breakdown={ticker: sum(v.impact_cost for v in group_verdicts)},
            net_risk_reduction_bps=net_benefit,
            confidence=weighted_conf,
            guardrails=guardrails,
            alternatives=alternatives,
        )
        cards.append(card)

    # Also create a card for any remaining BLOCK verdicts that didn't match
    if block_verdicts:
        # Check if any BLOCK verdicts weren't attached
        attached = set()
        for v in block_verdicts:
            if v.ticker != "PORTFOLIO":
                attached.add(v.ticker)
        for v in block_verdicts:
            if v.ticker == "PORTFOLIO" or v.ticker not in attached:
                # Create a generic portfolio-level block card
                card = RecommendationCard(
                    id=f"block_{v.rule_name}",
                    title=f"Blocked: {v.rule_name}",
                    priority=0,
                    urgency=v.urgency,
                    action=ActionType.BLOCK,
                    tickers=[],
                    qtys={},
                    prices={},
                    reason=v.reason,
                    regime_context=ctx.regime,
                    rule_verdicts=[v],
                    tax_breakdown={},
                    impact_breakdown={},
                    net_risk_reduction_bps=0,
                    confidence=v.confidence,
                    guardrails=_build_guardrails(ActionType.BLOCK, "PORTFOLIO", [v], ctx),
                    alternatives=[],
                )
                cards.append(card)

    # Sort by priority (urgency + confidence + net benefit)
    cards.sort(
        key=lambda c: (
            c.urgency == Urgency.IMMEDIATE,
            c.urgency == Urgency.NEAR_TERM,
            c.confidence,
            c.net_risk_reduction_bps,
        ),
        reverse=True,
    )

    return cards


def run_recommendation_engine(
    snapshot: PortfolioSnapshot,
    market_data: MarketData,
    user_profile: UserProfile,
) -> tuple[list[RecommendationCard], RecommendationReport]:
    """Main entry point: snapshot + market data + user profile → recommendation cards + report"""
    ctx = build_recommendation_context(snapshot, market_data, user_profile)
    verdicts = apply_recommendation_rules(ctx)
    cards = generate_recommendation_cards(verdicts, ctx)

    # Build priority_actions for backward compatibility with PDF generator
    priority_cards = [
        c for c in cards if c.priority > 0 and c.urgency in (Urgency.IMMEDIATE, Urgency.NEAR_TERM)
    ]

    report = RecommendationReport(
        cards=cards,
        generated_at=datetime.now().isoformat(),
        regime_context=ctx.regime,
        total_risk_reduction_bps=sum(c.net_risk_reduction_bps for c in cards),
        total_tax_cost=sum(
            c.tax_breakdown.get(list(c.tax_breakdown.keys())[0], 0) if c.tax_breakdown else 0 for c in cards
        ),
        total_impact_cost=sum(
            c.impact_breakdown.get(list(c.impact_breakdown.keys())[0], 0) if c.impact_breakdown else 0
            for c in cards
        ),
        confidence=sum(c.confidence for c in cards) / len(cards) if cards else 0,
        summary=f"{len(cards)} recommendations generated for {ctx.regime.value} regime",
        priority_actions=priority_cards[:5],
    )
    return cards, report


# ─── Helpers ──────────────────────────────────────────────────────


def _parse_purchase_date(holding: dict) -> date:
    """Extract purchase date from holding data"""
    # Try multiple fields
    for key in ["purchase_date", "avg_date", "buy_date", "acquired_date"]:
        if key in holding and holding[key]:
            try:
                return date.fromisoformat(str(holding[key])[:10])
            except (ValueError, TypeError):
                pass
    # Fallback: assume 1 year ago for LTCG
    from datetime import timedelta

    return date.today() - timedelta(days=400)


def _card_title(action: ActionType, ticker: str) -> str:
    titles = {
        ActionType.BUY: f"Add to {ticker}",
        ActionType.SELL: f"Exit {ticker}",
        ActionType.TRIM: f"Reduce {ticker}",
        ActionType.HOLD: f"Hold {ticker}",
    }
    return titles.get(action, f"{action.value.title()} {ticker}")


def _build_guardrails(
    action: ActionType, ticker: str, verdicts: list[RuleVerdict], ctx: RecommendationContext
) -> list[str]:
    """Build 'don't if...' conditions for the card"""
    guardrails = []

    # Regime guardrails
    if ctx.vix > 28:
        guardrails.append(f"Don't add longs if VIX > 28 (currently {ctx.vix:.1f})")
    if ctx.adx < 15:
        guardrails.append(f"Don't chase breakouts if ADX < 15 (currently {ctx.adx:.1f})")

    # Tax guardrails
    if ticker in ctx.holdings:
        lot = ctx.holdings[ticker]
        if not lot.is_ltcg:
            guardrails.append(f"Triggers STCG (15%) — holding period {lot.holding_days} days")
        if lot.unrealized_pnl > 0 and action == ActionType.SELL:
            guardrails.append(f"Realizes ₹{lot.unrealized_pnl:,.0f} gain — check STCG budget")

    # Market hours
    guardrails.append("Execute only during market hours (9:15-15:30 IST)")

    # Rule-specific
    for v in verdicts:
        if v.rule_name == "expiry_week":
            guardrails.append("Expiry week — higher volatility, wider SL")
        if v.rule_name == "tax_loss_harvest":
            guardrails.append("Only if STCG budget available this FY")

    return guardrails


def _build_alternatives(action: ActionType, ticker: str, ctx: RecommendationContext) -> list[str]:
    """What else was considered"""
    alternatives = []

    if action == ActionType.TRIM:
        alternatives.append(f"Full exit {ticker} instead of trim")
        alternatives.append("Hedge with PUT instead of reducing")
    elif action == ActionType.BUY:
        alternatives.append("Add to existing similar holding instead")
        alternatives.append("Wait for pullback to MA20")
    elif action == ActionType.SELL:
        alternatives.append("Trim 50% instead of full exit")
        alternatives.append("Set trailing stop instead of hard exit")

    return alternatives
