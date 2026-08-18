from __future__ import annotations

from engine.recommendations.orchestrator import (
    MarketData,
    PortfolioSnapshot,
    UserProfile,
)
from engine.recommendations.orchestrator import (
    run_recommendation_engine as run_rec_engine,
)
from engine.recommendations.types import (
    FiiDiiBias,
    RecommendationReport,
    RegimeContext,
)


def generate_recommendations(
    risk,
    sector,
    benchmark,
    portfolio,
    factor_report=None,
    institutional_scores=None,
    macro_drivers=None,
    corr_matrix=None,
    regime_result=None,
    profile=None,
) -> RecommendationReport | None:
    """
    Generate recommendations for the intelligence registry.

    This is a thin wrapper around run_recommendation_engine that converts
    the various context objects into the format expected by the recommendation engine.
    """
    try:
        # Build snapshot from portfolio
        holdings = []
        for h in portfolio.holdings:
            holdings.append({
                "ticker": h.ticker,
                "name": h.name,
                "quantity": h.quantity,
                "avg_price": h.avg_price,
                "current_price": getattr(h, 'current_price', h.avg_price),
            })

        # Get sector weights from sector object
        _ = sector.sector_allocation if sector else {}

        snapshot = PortfolioSnapshot(
            holdings=[{
                "ticker": h.ticker,
                "name": h.name,
                "quantity": h.quantity,
                "avg_price": h.avg_price,
                "current_price": getattr(h, 'current_price', h.avg_price),
            } for h in portfolio.holdings],
            total_value=sum(
                h.quantity * getattr(h, 'current_price', h.avg_price)
                for h in portfolio.holdings
            ),
            cash_available=0.0,  # Would need to be passed in
            sector_weights=sector.sector_allocation if sector else {},
            asset_class_weights={"Equity": 100.0},
        )

        # Build market data from regime result and other context
        # Extract VIX/ADX from regime_result if available
        vix = 13.5
        adx = 25.0
        if regime_result and hasattr(regime_result, 'vix') and regime_result.vix:
            vix = regime_result.vix
        if regime_result and hasattr(regime_result, 'adx') and regime_result.adx:
            adx = regime_result.adx

        market_data = MarketData(
            vix=vix,
            adx=adx,
            nifty_ma200_dist_pct=5.2,
            breadth_ad_ratio=1.2,
            fii_dii_bias=FiiDiiBias.NEUTRAL,
            is_expiry_week=False,
            regime=RegimeContext.BULL,
        )

        # Default user profile
        user_profile = UserProfile(
            max_stcg_budget=100000,
            max_ltcg_budget=500000,
            max_single_trade_pct=10.0,
            max_sector_weight=20.0,
            max_single_name_weight=15.0,
            min_cash_floor=50000,
            tax_loss_harvest_enabled=True,
            horizon_years=5,
        )

        # Run the recommendation engine
        _, report = run_rec_engine(
            snapshot=snapshot,
            market_data=market_data,
            user_profile=user_profile,
        )

        return report

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Recommendation generation failed: {e}")
        return None
