# engine/recommendations/types.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Literal


class Urgency(Enum):
    IMMEDIATE = "immediate"      # < 1 trading day
    NEAR_TERM = "near_term"      # 1-5 days
    ROUTINE = "routine"          # next rebalance window


class ActionType(Enum):
    BUY = "buy"
    SELL = "sell"
    TRIM = "trim"
    HOLD = "hold"
    BLOCK = "block"              # governance veto


class RegimeContext(Enum):
    BULL = "bull"                # Nifty > MA200, VIX < 15
    NEUTRAL = "neutral"          # Range-bound
    BEAR = "bear"                # Nifty < MA200, VIX > 25
    CRISIS = "crisis"            # VIX > 35, circuit breakers


class FiiDiiBias(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class TaxLot:
    ticker: str
    qty: int
    avg_price: float
    purchase_date: date
    current_price: float
    unrealized_pnl: float
    holding_days: int
    is_ltcg: bool                # > 365 days
    stcg_tax: float              # 15% if STCG
    ltcg_tax: float              # 10% > 1L if LTCG


@dataclass(frozen=True)
class ImpactEstimate:
    ticker: str
    side: Literal["buy", "sell"]
    qty: int
    adv_20d: float               # average daily volume
    participation_pct: float     # qty / adv_20d
    est_slippage_bps: float      # based on participation
    est_impact_cost: float       # slippage * qty * price
    stamp_duty: float
    stt: float
    brokerage: float
    total_cost: float


@dataclass(frozen=True)
class RuleVerdict:
    rule_name: str
    action: ActionType
    ticker: str
    qty: int
    urgency: Urgency
    confidence: float            # 0.0 - 1.0
    reason: str
    risk_delta_bps: int          # portfolio risk change in bps
    tax_cost: float
    impact_cost: float
    net_benefit_bps: int         # risk_delta - tax_cost - impact_cost


@dataclass(frozen=True)
class RecommendationCard:
    id: str
    title: str
    priority: int                # 1 = highest
    urgency: Urgency
    action: ActionType
    tickers: list[str]
    qtys: dict[str, int]
    prices: dict[str, float]
    reason: str
    regime_context: RegimeContext
    rule_verdicts: list[RuleVerdict]   # all rules that fired
    tax_breakdown: dict[str, float]    # per-ticker STCG/LTCG
    impact_breakdown: dict[str, float] # per-ticker slippage+costs
    net_risk_reduction_bps: int
    confidence: float            # weighted avg of rule confidences
    guardrails: list[str]        # "don't if..." conditions
    alternatives: list[str]      # what else was considered


@dataclass(frozen=True)
class RecommendationContext:
    # Portfolio state
    holdings: dict[str, TaxLot]           # ticker -> TaxLot
    sector_weights: dict[str, float]      # sector -> weight %
    asset_class_weights: dict[str, float] # equity/etf/gold/cash
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
    max_stcg_budget: float                # ₹ willing to realize STCG
    max_ltcg_budget: float                # ₹ willing to realize LTCG
    max_single_trade_pct: float           # max % of portfolio per trade
    max_sector_weight: float              # sector cap
    max_single_name_weight: float         # single stock cap
    min_cash_floor: float                 # emergency cash
    tax_loss_harvest_enabled: bool
    horizon_years: int                    # investment horizon

    # Derived
    portfolio_sharpe: float
    portfolio_vol_annual: float
    portfolio_var_95: float


@dataclass(frozen=True)
class RecommendationReport:
    """Complete recommendation report for a portfolio"""
    cards: list[RecommendationCard]
    generated_at: str
    regime_context: RegimeContext
    total_risk_reduction_bps: int
    total_tax_cost: float
    total_impact_cost: float
    confidence: float
    summary: str
    priority_actions: list[RecommendationCard] | None = None  # For backward compatibility with PDF generator
