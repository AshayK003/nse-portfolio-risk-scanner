"""Tests for the factor risk decomposition module."""

import numpy as np
import pandas as pd

from engine.factors import (
    FactorRiskReport,
    MacroDriver,
    compute_factor_exposures,
    estimate_macro_sensitivities,
)


class TestComputeFactorExposures:
    def test_returns_report_type(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        result = compute_factor_exposures(sample_prices, weights)
        assert isinstance(result, FactorRiskReport)

    def test_has_all_factors(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        result = compute_factor_exposures(sample_prices, weights)
        factor_names = {f.name for f in result.factors}
        expected = {"Market (Beta)", "Size", "Momentum", "Volatility", "Liquidity", "Concentration"}
        assert expected.issubset(factor_names)

    def test_factor_exposures_in_range(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        result = compute_factor_exposures(sample_prices, weights)
        for factor in result.factors:
            assert isinstance(factor.exposure, float)
            assert isinstance(factor.risk_contribution_pct, float)
            assert factor.risk_contribution_pct >= 0
            assert factor.risk_contribution_pct <= 100

    def test_idiosyncratic_risk_non_negative(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        result = compute_factor_exposures(sample_prices, weights)
        assert result.idiosyncratic_risk_pct >= 0

    def test_dominant_factor_populated(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        result = compute_factor_exposures(sample_prices, weights)
        assert result.dominant_factor != "N/A"

    def test_empty_prices(self):
        result = compute_factor_exposures(pd.DataFrame(), [])
        assert isinstance(result, FactorRiskReport)
        assert len(result.factors) == 0

    def test_single_stock(self):
        dates = pd.date_range(end="2024-01-01", periods=252, freq="B")
        np.random.seed(42)
        prices = pd.DataFrame(
            {"A.NS": 100 * np.cumprod(1 + np.random.normal(0.001, 0.02, 252))},
            index=dates,
        )
        result = compute_factor_exposures(prices, [1.0])
        assert isinstance(result, FactorRiskReport)
        assert len(result.factors) > 0

    def test_with_benchmark(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        returns = sample_prices.pct_change().dropna()
        benchmark = returns.mean(axis=1) + np.random.normal(0, 0.001, len(returns))
        result = compute_factor_exposures(sample_prices, weights, benchmark_returns=benchmark)
        market_factor = next(f for f in result.factors if f.name == "Market (Beta)")
        assert abs(market_factor.exposure) < 5  # reasonable beta range

    def test_concentration_reflects_weights(self, sample_prices):
        # Highly concentrated: 100% in one stock
        result = compute_factor_exposures(sample_prices, [1.0, 0.0, 0.0])
        conc_factor = next(f for f in result.factors if f.name == "Concentration")
        assert conc_factor.exposure > 0.5  # high concentration

    def test_diversification_by_factor_populated(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        result = compute_factor_exposures(sample_prices, weights)
        assert len(result.diversification_by_factor) > 0

    def test_factor_descriptions_populated(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        result = compute_factor_exposures(sample_prices, weights)
        for factor in result.factors:
            assert len(factor.description) > 0


class TestEstimateMacroSensitivities:
    def test_returns_list(self, sample_prices, sample_holdings):
        weights = [0.4, 0.3, 0.3]
        returns = sample_prices.pct_change().dropna()
        portfolio_returns = returns.dot(np.array(weights))
        result = estimate_macro_sensitivities(portfolio_returns, sample_prices, weights)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_all_macro_drivers_have_required_fields(self, sample_prices, sample_holdings):
        weights = [0.4, 0.3, 0.3]
        returns = sample_prices.pct_change().dropna()
        portfolio_returns = returns.dot(np.array(weights))
        result = estimate_macro_sensitivities(portfolio_returns, sample_prices, weights)
        for driver in result:
            assert isinstance(driver, MacroDriver)
            assert driver.name != ""
            assert driver.sensitivity >= 0
            assert driver.current_regime in ("favorable", "neutral", "unfavorable")
            assert driver.risk_level in ("low", "medium", "high")
            assert len(driver.reasoning) > 0

    def test_empty_prices(self):
        result = estimate_macro_sensitivities(pd.Series(dtype=float), pd.DataFrame(), [])
        assert result == []

    def test_global_beta_driver_present(self, sample_prices):
        weights = [0.4, 0.3, 0.3]
        returns = sample_prices.pct_change().dropna()
        portfolio_returns = returns.dot(np.array(weights))
        benchmark = returns.mean(axis=1)
        result = estimate_macro_sensitivities(
            portfolio_returns, sample_prices, weights, benchmark_returns=benchmark
        )
        names = [d.name for d in result]
        assert "Global Risk Sentiment" in names
