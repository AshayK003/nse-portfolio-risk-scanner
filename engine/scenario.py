"""
Scenario / stress testing — estimate portfolio impact under market scenarios.
Pure functions — zero IO, zero Streamlit imports.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ScenarioResult:
    name: str
    market_change: float
    portfolio_impact_pct: float
    holding_impacts: list[dict]  # ticker, weight, beta, impact_pct


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
        holding_impacts.append({
            "ticker": h.ticker.replace(".NS", ""),
            "name": h.name,
            "weight_pct": round(weight * 100, 1),
            "beta": round(beta, 2),
            "impact_pct": round(impact_pct, 2),
            "impact_rs": round(impact_pct / 100 * total_value, 0),
        })

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
