"""Tests for macro-driven stress test scenarios."""

from engine import Holding
from engine.scenario import (
    MacroScenarioResult,
    run_macro_scenarios,
    run_scenario,
)


def _holdings_with_prices():
    """Create test holdings with non-zero current prices."""
    return [
        Holding(
            ticker="RELIANCE",
            name="Reliance",
            quantity=10,
            avg_price=2500,
            current_price=2700,
            sector="Oil & Gas",
        ),
        Holding(ticker="TCS", name="TCS", quantity=5, avg_price=3500, current_price=3800, sector="IT"),
        Holding(
            ticker="HDFCBANK",
            name="HDFC Bank",
            quantity=20,
            avg_price=1600,
            current_price=1700,
            sector="Banking",
        ),
    ]


class TestRunScenario:
    def test_returns_scenario_result(self):
        holdings = _holdings_with_prices()
        betas = {"RELIANCE": 1.1, "TCS": 0.8, "HDFCBANK": 1.0}
        result = run_scenario(holdings, betas, -10, "Test Crash")
        assert hasattr(result, "portfolio_impact_pct")

    def test_impact_proportional_to_market_change(self):
        holdings = _holdings_with_prices()
        betas = {"RELIANCE": 1.0, "TCS": 1.0, "HDFCBANK": 1.0}
        r1 = run_scenario(holdings, betas, -5, "Small")
        r2 = run_scenario(holdings, betas, -10, "Large")
        assert abs(r2.portfolio_impact_pct) > abs(r1.portfolio_impact_pct)

    def test_zero_value_portfolio(self):
        holdings = [Holding(ticker="A", name="A", quantity=0, avg_price=100, current_price=100)]
        result = run_scenario(holdings, {"A": 1.0}, -10, "Test")
        assert result.portfolio_impact_pct == 0.0

    def test_holding_impacts_populated(self):
        holdings = _holdings_with_prices()
        betas = {"RELIANCE": 1.1, "TCS": 0.8, "HDFCBANK": 1.0}
        result = run_scenario(holdings, betas, -10, "Test")
        assert len(result.holding_impacts) == 3


class TestRunMacroScenarios:
    def test_returns_list_of_macro_results(self):
        holdings = _holdings_with_prices()
        betas = {"RELIANCE": 1.1, "TCS": 0.8, "HDFCBANK": 1.0}
        result = run_macro_scenarios(holdings, betas)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_all_macro_results_have_required_fields(self):
        holdings = _holdings_with_prices()
        betas = {"RELIANCE": 1.1, "TCS": 0.8, "HDFCBANK": 1.0}
        result = run_macro_scenarios(holdings, betas)
        for scenario in result:
            assert isinstance(scenario, MacroScenarioResult)
            assert scenario.name != ""
            assert scenario.description != ""
            assert scenario.probability in ("low", "medium", "high")
            assert scenario.severity in ("mild", "moderate", "severe", "extreme")
            assert len(scenario.reasoning) > 0
            assert len(scenario.sector_impacts) > 0

    def test_sector_impacts_vary_by_scenario(self):
        holdings = _holdings_with_prices()
        betas = {"RELIANCE": 1.1, "TCS": 0.8, "HDFCBANK": 1.0}
        result = run_macro_scenarios(holdings, betas)
        names = [s.name for s in result]
        assert len(set(names)) == len(result)

    def test_empty_holdings(self):
        result = run_macro_scenarios([], {})
        assert result == []

    def test_zero_value_holdings(self):
        holdings = [Holding(ticker="A", name="A", quantity=0, avg_price=100, current_price=100, sector="IT")]
        result = run_macro_scenarios(holdings, {"A": 1.0})
        assert result == []
