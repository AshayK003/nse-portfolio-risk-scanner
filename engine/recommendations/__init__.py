# engine/recommendations/__init__.py
from __future__ import annotations

from engine.recommendations.orchestrator import (
    MarketData,
    PortfolioSnapshot,
    UserProfile,
    build_recommendation_context,
    generate_recommendation_cards,
    run_recommendation_engine,
)
from engine.recommendations.rules import (
    RULES,
    apply_recommendation_rules,
    rule_breadth_confirmation,
    rule_cash_floor,
    rule_concentration_sector,
    rule_concentration_single_name,
    rule_etf_overlap,
    rule_expiry_week,
    rule_fii_dii_confluence,
    rule_regime_adx_doldrums,
    rule_regime_vix_spike,
    rule_sharpe_underperformance,
    rule_tax_loss_harvest,
)
from engine.recommendations.types import (
    ActionType,
    FiiDiiBias,
    ImpactEstimate,
    RecommendationCard,
    RecommendationContext,
    RecommendationReport,
    RegimeContext,
    RuleVerdict,
    TaxLot,
    Urgency,
)

__all__ = [
    # Types
    "Urgency",
    "ActionType",
    "RegimeContext",
    "FiiDiiBias",
    "TaxLot",
    "ImpactEstimate",
    "RuleVerdict",
    "RecommendationCard",
    "RecommendationContext",
    "RecommendationReport",
    # Rules
    "apply_recommendation_rules",
    "RULES",
    "rule_concentration_single_name",
    "rule_concentration_sector",
    "rule_sharpe_underperformance",
    "rule_regime_vix_spike",
    "rule_regime_adx_doldrums",
    "rule_breadth_confirmation",
    "rule_fii_dii_confluence",
    "rule_expiry_week",
    "rule_tax_loss_harvest",
    "rule_cash_floor",
    "rule_etf_overlap",
    # Orchestrator
    "PortfolioSnapshot",
    "MarketData",
    "UserProfile",
    "build_recommendation_context",
    "generate_recommendation_cards",
    "run_recommendation_engine",
]
