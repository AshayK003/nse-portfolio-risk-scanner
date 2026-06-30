"""
Data models for the NSE Portfolio Risk Scanner.
Pure dataclasses — no business logic, no dependencies beyond stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Import types from their owning modules to keep each module self-contained.
# This avoids import-order edge cases on Streamlit Cloud's Linux environment.
from engine.optimization import OptimizationResult, RebalanceSuggestion  # noqa: F401
from engine.regime import RegimeResult  # noqa: F401
from engine.risk import MonteCarloResult, RiskMetrics  # noqa: F401
from engine.scenario import ScenarioResult  # noqa: F401


@dataclass
class Holding:
    """A single stock position in the portfolio."""

    ticker: str  # e.g. "RELIANCE"
    name: str  # e.g. "Reliance Industries Ltd"
    quantity: int
    avg_price: float  # average buy price
    sector: str = ""  # populated by sector mapper
    current_price: float = 0.0  # populated by price fetcher
    change_pct: float = 0.0  # populated after price fetch

    @property
    def invested_value(self) -> float:
        return self.quantity * self.avg_price

    @property
    def current_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def pnl(self) -> float:
        return self.current_value - self.invested_value

    @property
    def pnl_pct(self) -> float:
        if self.invested_value == 0:
            return 0.0
        return (self.pnl / self.invested_value) * 100


@dataclass
class Portfolio:
    """The user's full portfolio."""

    holdings: list[Holding] = field(default_factory=list)
    name: str = "My Portfolio"
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def total_invested(self) -> float:
        return sum(h.invested_value for h in self.holdings)

    @property
    def total_current(self) -> float:
        return sum(h.current_value for h in self.holdings)

    @property
    def total_pnl(self) -> float:
        return self.total_current - self.total_invested

    @property
    def total_pnl_pct(self) -> float:
        if self.total_invested == 0:
            return 0.0
        return (self.total_pnl / self.total_invested) * 100

    @property
    def holding_count(self) -> int:
        return len(self.holdings)

    @property
    def weight(self) -> list[float]:
        """Return fractional weight of each holding (0-1)."""
        total = self.total_current
        if total == 0:
            return [0.0] * len(self.holdings)
        return [h.current_value / total for h in self.holdings]


@dataclass
class SectorExposure:
    """Sector concentration analysis."""

    holdings: list[Holding]
    sector_allocation: dict[str, float]  # sector_name -> % of portfolio
    concentrated_sectors: list[str]  # sectors > 20% of portfolio
    diversification_score: float  # 0-100, higher = more diversified
    herfindahl_index: float  # 0-1 concentration metric


@dataclass
class BenchmarkComparison:
    """Portfolio vs benchmark comparison."""

    portfolio_return: float  # Portfolio total return (%)
    benchmark_return: float  # Benchmark total return (%)
    alpha: float  # Excess return over benchmark (%)
    tracking_error: float  # Tracking error (%)
    information_ratio: float  # Information ratio
    beta: float  # Beta to benchmark
    correlation: float  # Correlation
    rolling_alpha_6m: float  # 6-month rolling alpha (%)
    outperformance_months: int  # Count of months beating benchmark
    total_months: int  # Total months compared


@dataclass
class AnalysisReport:
    """Complete analysis result returned by the engine."""

    portfolio: Portfolio
    risk: RiskMetrics
    sector: SectorExposure
    benchmark: BenchmarkComparison
    prices: dict | None = None  # serialized price history (for export)
    optimization: OptimizationResult | None = None
    monte_carlo: MonteCarloResult | None = None
    regime: RegimeResult | None = None
    # v0.7.0 intelligence modules
    factor_report: FactorRiskReport | None = None
    macro_drivers: list[MacroDriver] | None = None
    institutional_scores: InstitutionalRiskScores | None = None
    macro_scenarios: list[MacroScenarioResult] | None = None
    recommendations: RecommendationReport | None = None
    warnings: WarningReport | None = None
