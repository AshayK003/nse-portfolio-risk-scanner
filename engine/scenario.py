"""
Scenario / stress testing — estimate portfolio impact under market scenarios.

Includes both basic market-move scenarios and macro-driven stress tests
with sector-specific multipliers and causal reasoning.
Pure functions — zero IO, zero Streamlit imports.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScenarioResult:
    name: str
    market_change: float
    portfolio_impact_pct: float
    holding_impacts: list[dict]  # ticker, weight, beta, impact_pct


@dataclass
class MacroScenarioResult:
    """Enhanced scenario with sector-specific impacts and causal reasoning."""

    name: str
    description: str
    market_change: float  # overall market expected move
    portfolio_impact_pct: float
    holding_impacts: list[dict]
    sector_impacts: dict[str, float]  # sector -> expected % impact
    reasoning: str  # causal chain explaining why this scenario matters
    probability: str  # "low", "medium", "high"
    severity: str  # "mild", "moderate", "severe", "extreme"


# Sector-specific multipliers for macro scenarios.
# Maps scenario -> sector -> relative impact multiplier (1.0 = market average).
SECTOR_MULTIPLIERS: dict[str, dict[str, float]] = {
    "Crude Oil Spike (+50%)": {
        "Oil & Gas": -0.3,  # O&G benefits from high crude (upstream)
        "Power": -0.15,  # power companies face higher fuel costs
        "Construction Materials": -0.08,  # transportation cost increase
        "Chemicals": -0.1,  # petrochemical input costs
        "Automobile": -0.05,  # margin pressure from input costs
        "FMCG": -0.03,  # mild pass-through to consumers
        "IT": 0.0,  # negligible direct impact
        "Banking": -0.05,  # inflation fears → rate hike pressure
    },
    "INR Depreciation (-10% vs USD)": {
        "IT": 0.15,  # IT exporters benefit from weak INR
        "Pharma": 0.08,  # pharma exporters benefit
        "FMCG": -0.05,  # imported raw material costs rise
        "Automobile": -0.08,  # imported component costs
        "Oil & Gas": -0.12,  # India imports 85% of crude; INR crash = import bill surge
        "Banking": -0.06,  # INR depreciation → FII outflows → rate pressure
        "Metals & Mining": -0.03,  # mixed — commodity prices in USD
    },
    "Rate Hike (+100bps)": {
        "Banking": 0.08,  # banks benefit from wider NIM
        "Financial Services": -0.1,  # NBFCs face higher borrowing costs
        "Real Estate": -0.15,  # rate-sensitive; demand destruction
        "Construction": -0.08,  # project financing costs rise
        "Automobile": -0.06,  # vehicle loan costs rise → demand hit
        "IT": 0.0,  # minimal direct impact
        "Power": -0.05,  # capex financing costs
    },
    "Rate Cut (-100bps)": {
        "Banking": -0.05,  # NIM compression
        "Financial Services": 0.1,  # lower borrowing costs
        "Real Estate": 0.12,  # demand recovery
        "Construction": 0.08,  # cheaper project financing
        "Automobile": 0.06,  # cheaper loans → demand boost
        "IT": 0.0,  # minimal
    },
    "Global Risk-Off (S&P -15%)": {
        "Banking": -0.15,  # FII-driven selling, credit fears
        "IT": -0.12,  # global demand slowdown, FII exits
        "Financial Services": -0.12,  # risk-off hits financials
        "FMCG": -0.03,  # defensive; mild FII selling
        "Pharma": -0.02,  # defensive; healthcare resilient
        "Oil & Gas": -0.1,  # demand destruction
        "Metals & Mining": -0.18,  # commodity crash in risk-off
    },
    "Recession (GDP -2%)": {
        "Banking": -0.2,  # NPA surge, credit freeze
        "Financial Services": -0.18,  # lending contraction
        "IT": -0.15,  # global enterprise spending cut
        "Automobile": -0.12,  # discretionary spending collapse
        "Real Estate": -0.15,  # demand evaporation
        "Consumer Durables": -0.1,  # discretionary cut
        "FMCG": -0.03,  # defensive; staples resilient
        "Pharma": -0.02,  # healthcare inelastic
        "Oil & Gas": -0.1,  # demand destruction
    },
    "Black Swan (-35%)": {
        # Most sectors hit hard; degree varies by cyclicality
        "Banking": -0.35,  # worst hit — credit freeze
        "Financial Services": -0.32,
        "IT": -0.25,
        "Metals & Mining": -0.35,
        "Real Estate": -0.35,
        "Automobile": -0.3,
        "Construction": -0.28,
        "Consumer Durables": -0.25,
        "FMCG": -0.12,  # defensive floor
        "Pharma": -0.1,  # defensive floor
        "Power": -0.15,  # regulated, somewhat defensive
        "Oil & Gas": -0.25,
    },
}

# Macro scenario definitions: (market_change, name, description, probability, severity)
MACRO_SCENARIOS: list[tuple[float, str, str, str, str]] = [
    (
        -30,
        "Crude Oil Spike (+50%)",
        "Crude surges to $120+/bbl. Import bill spikes, INR weakens, inflation re-accelerates. "
        "RBI forced to hike rates. O&G upstream benefits but consumers and power companies suffer.",
        "medium",
        "severe",
    ),
    (
        -15,
        "INR Depreciation (-10% vs USD)",
        "INR weakens sharply against USD. IT/pharma exporters benefit but import-dependent sectors "
        "(O&G, FMCG, auto) face margin pressure. FII outflows accelerate.",
        "medium",
        "moderate",
    ),
    (
        -12,
        "Rate Hike (+100bps)",
        "RBI raises rates by 100bps to combat inflation. Banks benefit from wider NIM but NBFCs, "
        "real estate, and rate-sensitive sectors face demand destruction.",
        "high",
        "moderate",
    ),
    (
        +8,
        "Rate Cut (-100bps)",
        "RBI cuts rates by 100bps to stimulate growth. Real estate and financial services benefit "
        "but bank NIMs compress. Mixed impact on overall market.",
        "medium",
        "mild",
    ),
    (
        -20,
        "Global Risk-Off (S&P -15%)",
        "US/European markets crash 15%. FII selling pressure intensifies in India. "
        "Cyclical sectors (metals, banking) hit hardest. Defensive sectors (pharma, FMCG) relatively resilient.",
        "medium",
        "severe",
    ),
    (
        -25,
        "Recession (GDP -2%)",
        "India GDP contracts 2%. Credit cycle turns, NPAs rise, corporate earnings decline 20-30%. "
        "Banking and financial sectors bear the brunt. Consumer staples provide floor.",
        "low",
        "severe",
    ),
    (
        -35,
        "Black Swan (-35%)",
        "Extreme tail event: pandemic, war, or systemic financial crisis. All sectors crash. "
        "Only the most defensive (pharma, FMCG) provide partial shelter. Recovery takes 12-18 months.",
        "low",
        "extreme",
    ),
]


def run_scenario(
    holdings: list,
    betas: dict[str, float],
    market_change: float,
    scenario_name: str = "",
) -> ScenarioResult:
    """
    Estimate portfolio impact under a market move scenario.

    For each holding: impact = weight * beta * market_change.
    Market_change is the expected % move (e.g. -10 for a 10% drop).
    """
    total_value = sum(h.current_value for h in holdings)
    if total_value <= 0:
        return ScenarioResult(
            name=scenario_name or f"Market {market_change:+.0f}%",
            market_change=market_change,
            portfolio_impact_pct=0.0,
            holding_impacts=[],
        )

    holding_impacts = []
    weighted_impact = 0.0

    for h in holdings:
        weight = h.current_value / total_value
        beta = betas.get(h.ticker, 1.0)
        impact_pct = weight * beta * market_change
        weighted_impact += impact_pct
        holding_impacts.append(
            {
                "ticker": h.ticker.replace(".NS", ""),
                "name": h.name,
                "weight_pct": round(weight * 100, 1),
                "beta": round(beta, 2),
                "impact_pct": round(impact_pct, 2),
                "impact_rs": round(impact_pct / 100 * total_value, 0),
            }
        )

    return ScenarioResult(
        name=scenario_name or f"Market {market_change:+.0f}%",
        market_change=market_change,
        portfolio_impact_pct=round(weighted_impact, 2),
        holding_impacts=holding_impacts,
    )


def run_default_scenarios(
    holdings: list,
    betas: dict[str, float],
) -> list[ScenarioResult]:
    """Run a set of predefined stress scenarios."""
    scenarios = [
        (-5, "Mild Correction (-5%)"),
        (-10, "Moderate Crash (-10%)"),
        (-20, "Severe Crash (-20%)"),
        (+10, "Strong Rally (+10%)"),
        (+20, "Bull Run (+20%)"),
    ]
    return [run_scenario(holdings, betas, pct, name) for pct, name in scenarios]


def run_macro_scenarios(
    holdings: list,
    betas: dict[str, float],
) -> list[MacroScenarioResult]:
    """
    Run macro-driven stress tests with sector-specific multipliers.

    Each scenario models a real-world macro event with:
    - Sector-specific impact multipliers (not just beta × market move)
    - Causal reasoning explaining the transmission mechanism
    - Probability and severity assessments
    - Per-holding impacts adjusted for sector exposure
    """
    total_value = sum(h.current_value for h in holdings)
    if total_value <= 0:
        return []

    results = []
    for market_change, name, description, probability, severity in MACRO_SCENARIOS:
        sector_multipliers = SECTOR_MULTIPLIERS.get(name, {})

        holding_impacts = []
        sector_impacts: dict[str, float] = {}
        sector_values: dict[str, float] = {}
        weighted_impact = 0.0

        for h in holdings:
            weight = h.current_value / total_value
            beta = betas.get(h.ticker, 1.0)
            sector = h.sector or "Unknown"

            # Base impact from beta
            base_impact = beta * market_change

            # Sector-specific adjustment
            sector_adj = sector_multipliers.get(sector, 0.0)
            adjusted_impact = base_impact + (sector_adj * 100)  # scale adj to percentage

            impact_pct = weight * adjusted_impact
            weighted_impact += impact_pct

            # Accumulate sector values for sector-level impact
            sector_values[sector] = sector_values.get(sector, 0) + h.current_value

            holding_impacts.append(
                {
                    "ticker": h.ticker.replace(".NS", ""),
                    "name": h.name,
                    "weight_pct": round(weight * 100, 1),
                    "beta": round(beta, 2),
                    "sector": sector,
                    "sector_adjustment": round(sector_adj * 100, 2),
                    "impact_pct": round(impact_pct, 2),
                    "impact_rs": round(impact_pct / 100 * total_value, 0),
                }
            )

        # Compute sector-level impacts
        for sector, sv in sector_values.items():
            sector_weight = sv / total_value
            sector_adj = sector_multipliers.get(sector, 0.0)
            sector_impacts[sector] = (
                round(
                    sector_weight
                    * (betas.get(list(betas.keys())[0], 1.0) * market_change + sector_adj * 100),
                    2,
                )
                if betas
                else 0.0
            )

        # Build causal reasoning
        reasoning = _build_scenario_reasoning(name, description, sector_impacts, holdings, total_value)

        results.append(
            MacroScenarioResult(
                name=name,
                description=description,
                market_change=market_change,
                portfolio_impact_pct=round(weighted_impact, 2),
                holding_impacts=holding_impacts,
                sector_impacts=sector_impacts,
                reasoning=reasoning,
                probability=probability,
                severity=severity,
            )
        )

    return results


def _build_scenario_reasoning(
    scenario_name: str,
    description: str,
    sector_impacts: dict[str, float],
    holdings: list,
    total_value: float,
) -> str:
    """Build causal reasoning for why this scenario matters for this portfolio."""
    parts = [description]

    # Identify most exposed sectors
    if sector_impacts:
        worst_sector = min(sector_impacts, key=sector_impacts.get)
        worst_impact = sector_impacts[worst_sector]
        if worst_impact < -5:
            sector_exposure = (
                sum(h.current_value for h in holdings if (h.sector or "Unknown") == worst_sector)
                / total_value
                * 100
            )
            parts.append(
                f"Your portfolio has {sector_exposure:.1f}% exposure to {worst_sector}, "
                f"which would face an estimated {worst_impact:.1f}% impact."
            )

    # Count affected holdings
    severely_affected = sum(1 for h in sector_impacts.values() if h < -10)
    if severely_affected > 0:
        parts.append(f"{severely_affected} sector(s) in your portfolio would face double-digit losses.")

    return " ".join(parts)
