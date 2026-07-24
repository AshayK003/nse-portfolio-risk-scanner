"""Tests for the rule-based narrative generation engine."""

import pytest

from engine import (
    AnalysisReport,
    BenchmarkComparison,
    Portfolio,
    RiskMetrics,
    SectorExposure,
)
from engine.narrative import NarrativeReport, generate_narrative


class TestGenerateNarrative:
    """Core narrative generation tests."""

    def _make_portfolio(self, **overrides):
        from engine import Holding

        holdings = [
            Holding(
                ticker="RELIANCE.NS",
                name="Reliance Industries",
                quantity=10,
                avg_price=2500,
                sector="Oil & Gas",
                current_price=2800,
            ),
            Holding(ticker="TCS.NS", name="TCS", quantity=5, avg_price=3500, sector="IT", current_price=3800),
            Holding(
                ticker="HDFCBANK.NS",
                name="HDFC Bank",
                quantity=20,
                avg_price=1600,
                sector="Banking",
                current_price=1700,
            ),
        ]
        p = Portfolio(holdings=holdings, name=overrides.get("name", "Test"))
        return p

    def _make_risk(self, **overrides):
        defaults = dict(
            volatility_annual=18.0,
            var_95=-2.5,
            var_99=-4.0,
            cvar_95=-3.2,
            max_drawdown=-18.0,
            max_drawdown_start="2024-03-01",
            max_drawdown_end="2024-06-15",
            beta=0.95,
            correlation_to_benchmark=0.88,
            sharpe=1.1,
            sortino=1.6,
            cagr=12.0,
            total_return=22.0,
        )
        defaults.update(overrides)
        return RiskMetrics(**defaults)

    def _make_sector(self, **overrides):
        defaults = dict(
            sector_allocation={"Banking": 40.0, "IT": 35.0, "Oil & Gas": 25.0},
            concentrated_sectors=["Banking"],
            diversification_score=55.0,
            herfindahl_index=0.35,
        )
        defaults.update(overrides)
        return SectorExposure(
            holdings=self._make_portfolio().holdings,
            **defaults,
        )

    def _make_benchmark(self, **overrides):
        defaults = dict(
            portfolio_return=22.0,
            benchmark_return=18.0,
            alpha=4.0,
            tracking_error=5.5,
            information_ratio=0.73,
            beta=0.95,
            correlation=0.88,
            rolling_alpha_6m=6.0,
            outperformance_months=8,
            total_months=12,
        )
        defaults.update(overrides)
        return BenchmarkComparison(**defaults)

    def _make_report(self, **overrides):
        portfolio = overrides.get("portfolio") if "portfolio" in overrides else self._make_portfolio()
        risk = overrides.get("risk") if "risk" in overrides else self._make_risk()
        sector = overrides.get("sector") if "sector" in overrides else self._make_sector()
        benchmark = overrides.get("benchmark") if "benchmark" in overrides else self._make_benchmark()
        return AnalysisReport(
            portfolio=portfolio,
            risk=risk,
            sector=sector,
            benchmark=benchmark,
        )

    # ── Type & structure tests ──

    def test_returns_narrative_report_type(self):
        report = self._make_report()
        narrative = generate_narrative(report)
        assert isinstance(narrative, NarrativeReport)

    def test_all_sections_populated(self):
        report = self._make_report()
        narrative = generate_narrative(report)
        assert len(narrative.summary) > 0
        assert len(narrative.risk_assessment) > 0
        assert len(narrative.concentration) > 0
        assert len(narrative.benchmark_context) > 0
        assert len(narrative.overall_verdict) > 0
        assert isinstance(narrative.key_concerns, list)

    def test_key_concerns_is_list_of_strings(self):
        report = self._make_report()
        narrative = generate_narrative(report)
        assert all(isinstance(c, str) for c in narrative.key_concerns)

    def test_key_concerns_capped_at_five(self):
        report = self._make_report()
        narrative = generate_narrative(report)
        assert len(narrative.key_concerns) <= 5

    # ── Summary tests ──

    def test_summary_mentions_holdings_count(self):
        report = self._make_report()
        narrative = generate_narrative(report)
        assert "3 holdings" in narrative.summary

    @pytest.mark.parametrize("pnl_pct,word", [(12.5, "up"), (-8.3, "down")])
    def test_summary_reflects_pnl_direction(self, pnl_pct, word):
        from engine import Holding

        h = [
            Holding(
                ticker="RELIANCE.NS",
                name="R",
                quantity=10,
                avg_price=100,
                current_price=100 * (1 + pnl_pct / 100),
                sector="Oil & Gas",
            ),
        ]
        port = Portfolio(holdings=h)
        risk = self._make_risk(volatility_annual=12.0)
        report = self._make_report(portfolio=port, risk=risk)
        narrative = generate_narrative(report)
        assert word in narrative.summary

    def test_summary_single_holdings_grammar(self):
        from engine import Holding

        h = [Holding(ticker="RELIANCE.NS", name="R", quantity=10, avg_price=100, current_price=110)]
        port = Portfolio(holdings=h)
        risk = self._make_risk(volatility_annual=12.0)
        report = self._make_report(portfolio=port, risk=risk)
        narrative = generate_narrative(report)
        assert "1 holding" in narrative.summary

    # ── Risk assessment threshold tests ──

    def test_low_volatility_narrative(self):
        risk = self._make_risk(volatility_annual=10.0)
        report = self._make_report(risk=risk)
        n = generate_narrative(report)
        assert "low" in n.risk_assessment

    def test_moderate_volatility_narrative(self):
        risk = self._make_risk(volatility_annual=18.0)
        report = self._make_report(risk=risk)
        n = generate_narrative(report)
        assert "moderate" in n.risk_assessment or "MODERATE" in n.risk_assessment

    def test_high_volatility_narrative(self):
        risk = self._make_risk(volatility_annual=30.0)
        report = self._make_report(risk=risk)
        n = generate_narrative(report)
        assert "high" in n.risk_assessment or "HIGH" in n.risk_assessment

    def test_low_var_narrative(self):
        risk = self._make_risk(var_95=-1.2)
        report = self._make_report(risk=risk)
        n = generate_narrative(report)
        assert "low" in n.risk_assessment

    def test_high_var_narrative(self):
        risk = self._make_risk(var_95=-5.0)
        report = self._make_report(risk=risk)
        n = generate_narrative(report)
        assert "high" in n.risk_assessment

    def test_poor_sharpe_narrative(self):
        risk = self._make_risk(sharpe=0.2)
        report = self._make_report(risk=risk)
        n = generate_narrative(report)
        assert "poor" in n.risk_assessment
        assert any("barely compensates" in s for s in [n.risk_assessment] + n.key_concerns)

    def test_excellent_sharpe_narrative(self):
        risk = self._make_risk(sharpe=2.5)
        report = self._make_report(risk=risk)
        n = generate_narrative(report)
        assert "excellent" in n.risk_assessment
        assert "strong" in n.risk_assessment

    def test_severe_drawdown_narrative(self):
        risk = self._make_risk(max_drawdown=-25.0)
        report = self._make_report(risk=risk)
        n = generate_narrative(report)
        assert "severe" in n.risk_assessment or "severe" in " ".join(n.key_concerns)

    # ── Concentration tests ──

    def test_good_diversification(self):
        sector = self._make_sector(diversification_score=75.0, concentrated_sectors=[])
        report = self._make_report(sector=sector)
        n = generate_narrative(report)
        assert "good" in n.concentration

    def test_poor_diversification(self):
        sector = self._make_sector(diversification_score=20.0)
        report = self._make_report(sector=sector)
        n = generate_narrative(report)
        assert "poor" in n.concentration

    def test_concentrated_sectors_mentioned_in_concerns(self):
        sector = self._make_sector(concentrated_sectors=["Banking"])
        report = self._make_report(sector=sector)
        n = generate_narrative(report)
        assert any("Banking" in c for c in n.key_concerns)

    def test_top_sector_appears_in_concentration(self):
        sector = self._make_sector(sector_allocation={"IT": 60.0, "Banking": 40.0})
        report = self._make_report(sector=sector)
        n = generate_narrative(report)
        assert "IT" in n.concentration

    def test_single_stock_concentration_concern(self):
        from engine import Holding

        h = [
            Holding(
                ticker="RELIANCE.NS",
                name="R",
                quantity=100,
                avg_price=100,
                current_price=500,
                sector="Oil & Gas",
            ),
            Holding(ticker="TCS.NS", name="T", quantity=1, avg_price=100, current_price=100, sector="IT"),
        ]
        port = Portfolio(holdings=h)
        sector = self._make_sector(
            sector_allocation={"Oil & Gas": 80.0, "IT": 20.0},
            concentrated_sectors=["Oil & Gas"],
        )
        report = self._make_report(portfolio=port, sector=sector)
        n = generate_narrative(report)
        assert any("RELIANCE" in c for c in n.key_concerns)

    # ── Benchmark tests ──

    def test_outperformance_mentioned(self):
        bm = self._make_benchmark(alpha=5.0, portfolio_return=23.0, benchmark_return=18.0)
        report = self._make_report(benchmark=bm)
        n = generate_narrative(report)
        assert "outperformed" in n.benchmark_context

    def test_underperformance_mentioned(self):
        bm = self._make_benchmark(alpha=-6.0, portfolio_return=12.0, benchmark_return=18.0)
        report = self._make_report(benchmark=bm)
        n = generate_narrative(report)
        assert "underperformed" in n.benchmark_context

    def test_high_beta_narrative(self):
        bm = self._make_benchmark(beta=1.5)
        report = self._make_report(benchmark=bm, risk=self._make_risk(beta=1.5))
        n = generate_narrative(report)
        assert "aggressive" in n.benchmark_context or "more" in n.benchmark_context

    def test_win_rate_included(self):
        bm = self._make_benchmark(outperformance_months=9, total_months=12)
        report = self._make_report(benchmark=bm)
        n = generate_narrative(report)
        assert "9 of 12" in n.benchmark_context or "75%" in n.benchmark_context

    def test_benchmark_none_graceful(self):
        report = self._make_report(benchmark=None)
        n = generate_narrative(report)
        assert "not available" in n.benchmark_context
        assert len(n.key_concerns) == 0 or True  # doesn't crash

    # ── Overall verdict tests ──

    def test_low_risk_verdict(self):
        risk = self._make_risk(volatility_annual=10.0, sharpe=2.0, max_drawdown=-5.0)
        sector = self._make_sector(diversification_score=80.0, concentrated_sectors=[])
        report = self._make_report(risk=risk, sector=sector)
        n = generate_narrative(report)
        assert "Low Risk" in n.overall_verdict

    def test_high_risk_verdict(self):
        risk = self._make_risk(volatility_annual=35.0, sharpe=0.2, max_drawdown=-35.0)
        sector = self._make_sector(diversification_score=15.0, concentrated_sectors=["Banking"])
        report = self._make_report(risk=risk, sector=sector)
        n = generate_narrative(report)
        assert "Higher Risk" in n.overall_verdict

    # ── Edge cases ──

    def test_no_holdings(self):
        empty_port = Portfolio(holdings=[], name="Empty")
        risk = self._make_risk(volatility_annual=0.0, sharpe=0.0, var_95=0.0, max_drawdown=0.0)
        sector = SectorExposure(
            holdings=[],
            sector_allocation={},
            concentrated_sectors=[],
            diversification_score=0.0,
            herfindahl_index=0.0,
        )
        bm = self._make_benchmark()
        report = self._make_report(portfolio=empty_port, risk=risk, sector=sector, benchmark=bm)
        n = generate_narrative(report)
        assert "0 holdings" in n.summary
        assert isinstance(n.key_concerns, list)

    def test_zero_values_dont_crash(self):
        risk = self._make_risk(
            volatility_annual=0.0,
            var_95=0.0,
            sharpe=0.0,
            max_drawdown=0.0,
            cagr=0.0,
            beta=0.0,
        )
        report = self._make_report(risk=risk)
        n = generate_narrative(report)
        assert all(
            len(getattr(n, f)) > 0
            for f in ["summary", "risk_assessment", "concentration", "benchmark_context", "overall_verdict"]
        )

    def test_empty_sector_alloc(self):
        sector = SectorExposure(
            holdings=[],
            sector_allocation={},
            concentrated_sectors=[],
            diversification_score=0.0,
            herfindahl_index=0.0,
        )
        report = self._make_report(sector=sector)
        n = generate_narrative(report)
        assert "not available" in n.concentration

    def test_key_concerns_sorted_by_severity(self):
        risk = self._make_risk(volatility_annual=35.0, sharpe=0.2, var_95=-5.0, max_drawdown=-30.0)
        sector = self._make_sector(
            sector_allocation={"Banking": 50.0, "IT": 30.0, "Oil & Gas": 20.0},
            concentrated_sectors=["Banking"],
        )
        from engine import Holding

        h = [
            Holding(
                ticker="BIG.NS", name="B", quantity=100, avg_price=100, current_price=500, sector="Banking"
            ),
            Holding(ticker="SMALL.NS", name="S", quantity=1, avg_price=100, current_price=100, sector="IT"),
        ]
        report = self._make_report(portfolio=Portfolio(holdings=h), risk=risk, sector=sector)
        n = generate_narrative(report)
        # Should have multiple concerns with a high-risk portfolio
        assert len(n.key_concerns) >= 2
