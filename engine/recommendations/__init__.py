# engine/recommendations/__init__.py
from __future__ import annotations

from engine.recommendations.types import (
    Urgency,
    ActionType,
    RegimeContext,
    FiiDiiBias,
    TaxLot,
    ImpactEstimate,
    RuleVerdict,
    RecommendationCard,
    RecommendationContext,
    RecommendationReport,
)

from engine.recommendations.rules import (
    apply_recommendation_rules,
    RULES,
    rule_concentration_single_name,
    rule_concentration_sector,
    rule_sharpe_underperformance,
    rule_regime_vix_spike,
    rule_regime_adx_doldrums,
    rule_breadth_confirmation,
    rule_fii_dii_confluence,
    rule_expiry_week,
    rule_tax_loss_harvest,
    rule_cash_floor,
    rule_etf_overlap,
)

from engine.recommendations.orchestrator import (
    PortfolioSnapshot,
    MarketData,
    UserProfile,
    build_recommendation_context,
    generate_recommendation_cards,
    run_recommendation_engine,
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