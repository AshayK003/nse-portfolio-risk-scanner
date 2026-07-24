"""Tests for scenario / stress testing module."""

from engine import Holding
from engine.scenario import run_default_scenarios, run_scenario


class TestRunScenario:
    def test_single_holding(self):
        holdings = [
            Holding(ticker="RELIANCE.NS", name="RIL", quantity=10, avg_price=2500, current_price=2600)
        ]
        betas = {"RELIANCE.NS": 1.2}
        result = run_scenario(holdings, betas, -10, "Test Crash")
        assert result.name == "Test Crash"
        assert result.portfolio_impact_pct < 0  # market drop
        assert len(result.holding_impacts) == 1

    def test_multiple_holdings(self):
        holdings = [
            Holding(ticker="RELIANCE.NS", name="RIL", quantity=10, avg_price=2500, current_price=2600),
            Holding(ticker="TCS.NS", name="TCS", quantity=5, avg_price=3500, current_price=3400),
        ]
        betas = {"RELIANCE.NS": 1.2, "TCS.NS": 0.8}
        result = run_scenario(holdings, betas, -10)
        assert len(result.holding_impacts) == 2
        assert result.market_change == -10

    def test_positive_scenario(self):
        holdings = [
            Holding(ticker="RELIANCE.NS", name="RIL", quantity=10, avg_price=2500, current_price=2600)
        ]
        betas = {"RELIANCE.NS": 1.0}
        result = run_scenario(holdings, betas, +15)
        assert result.portfolio_impact_pct > 0

    def test_zero_value_portfolio(self):
        holdings = [Holding(ticker="X.NS", name="X", quantity=0, avg_price=0, current_price=0)]
        betas = {"X.NS": 1.0}
        result = run_scenario(holdings, betas, -10)
        assert result.portfolio_impact_pct == 0.0

    def test_holding_impact_structure(self):
        holdings = [Holding(ticker="SBIN.NS", name="SBI", quantity=100, avg_price=800, current_price=900)]
        betas = {"SBIN.NS": 1.5}
        result = run_scenario(holdings, betas, -20)
        imp = result.holding_impacts[0]
        assert "ticker" in imp
        assert "beta" in imp
        assert imp["beta"] == 1.5
        assert imp["impact_pct"] == -30.0  # 100% weight * 1.5 beta * -20%


class TestRunDefaultScenarios:
    def test_returns_five_scenarios(self):
        holdings = [
            Holding(ticker="RELIANCE.NS", name="RIL", quantity=10, avg_price=2500, current_price=2600)
        ]
        betas = {"RELIANCE.NS": 1.0}
        results = run_default_scenarios(holdings, betas)
        assert len(results) == 5

    def test_ordered_by_severity(self):
        holdings = [
            Holding(ticker="RELIANCE.NS", name="RIL", quantity=10, avg_price=2500, current_price=2600)
        ]
        betas = {"RELIANCE.NS": 1.0}
        results = run_default_scenarios(holdings, betas)
        impacts = [s.portfolio_impact_pct for s in results]
        assert impacts[0] < impacts[3]  # -5% < +10%
