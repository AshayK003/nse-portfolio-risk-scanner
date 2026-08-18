"""
Data models for the NSE Portfolio Risk Scanner.
Pure dataclasses — no business logic, no dependencies beyond stdlib.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RiskProfile:
    """Tunable risk appetite profile that affects optimization, recommendations, and rebalancing."""

    name: str
    method: str  # "min_volatility", "hrp", "max_sharpe"
    max_single_weight: float  # max fraction any single holding can occupy
    beta_threshold: float  # beta above this triggers hedge/reduce recommendation
    sharpe_threshold: float  # sharpe below this triggers rebalance recommendation
    drawdown_threshold: float  # max drawdown (%) above which triggers monitor/hedge
    cvar_threshold: float  # CVaR (fraction) above which triggers hedge recommendation
    concentration_threshold: float  # single-sector % above this triggers reduce/diversify


# Pre-built risk profiles
CONSERVATIVE = RiskProfile(
    name="Conservative",
    method="min_volatility",
    max_single_weight=0.25,
    beta_threshold=1.0,
    sharpe_threshold=0.8,
    drawdown_threshold=15.0,
    cvar_threshold=3.0,
    concentration_threshold=25.0,
)
MODERATE = RiskProfile(
    name="Moderate",
    method="hrp",
    max_single_weight=0.35,
    beta_threshold=1.3,
    sharpe_threshold=0.5,
    drawdown_threshold=20.0,
    cvar_threshold=4.0,
    concentration_threshold=35.0,
)
AGGRESSIVE = RiskProfile(
    name="Aggressive",
    method="max_sharpe",
    max_single_weight=0.50,
    beta_threshold=1.8,
    sharpe_threshold=0.3,
    drawdown_threshold=30.0,
    cvar_threshold=6.0,
    concentration_threshold=50.0,
)

# Lookup from display-name key
RISK_PROFILES: dict[str, RiskProfile] = {p.name.lower(): p for p in [CONSERVATIVE, MODERATE, AGGRESSIVE]}
_DEFAULT_PROFILE = MODERATE


@dataclass
class Holding:
    """Single holding in a portfolio."""

    ticker: str
    name: str
    quantity: int
    avg_price: float
    sector: str = "Unknown"  # Optional sector from CSV; default to Unknown
    current_price: float | None = None
    change_pct: float | None = None

    @property
    def invested_value(self) -> float:
        return self.quantity * self.avg_price

    @property
    def current_value(self) -> float:
        cp = self.current_price
        if cp is None or (isinstance(cp, float) and math.isnan(cp)):
            return 0.0
        return self.quantity * cp

    @property
    def pnl(self) -> float:
        return self.current_value - self.invested_value

    @property
    def pnl_pct(self) -> float:
        if self.invested_value == 0:
            return 0.0
        return (self.current_value - self.invested_value) / self.invested_value * 100


@dataclass
class Portfolio:
    """A collection of holdings with aggregated metrics."""

    holdings: list[Holding]
    name: str = "Portfolio"

    @property
    def holding_count(self) -> int:
        return len(self.holdings)

    @property
    def total_invested(self) -> float:
        return sum(h.invested_value for h in self.holdings)

    @property
    def total_current(self) -> float:
        return sum(h.current_value for h in self.holdings)

    @property
    def total_pnl(self) -> float:
        return sum(h.pnl for h in self.holdings)

    @property
    def total_pnl_pct(self) -> float:
        if self.total_invested == 0:
            return 0.0
        return self.total_pnl / self.total_invested * 100

    @property
    def weight(self) -> list[float]:
        if self.total_current == 0:
            return [0.0] * len(self.holdings)
        return [h.current_value / self.total_current for h in self.holdings]


@dataclass
class RiskMetrics:
    """Portfolio-level risk metrics."""

    volatility_annual: float
    var_95: float
    var_99: float
    cvar_95: float
    max_drawdown: float
    max_drawdown_start: str
    max_drawdown_end: str
    beta: float
    correlation_to_benchmark: float
    sharpe: float
    sortino: float
    cagr: float
    total_return: float
    calmar_ratio: float = 0.0
    treynor_ratio: float = 0.0
    skewness: float = 0.0
    kurtosis_excess: float = 0.0


@dataclass
class SectorExposure:
    """Sector-level portfolio exposure analysis."""

    holdings: list[Holding]
    sector_allocation: dict[str, float]
    concentrated_sectors: list[str]
    diversification_score: float
    herfindahl_index: float


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
    up_capture: float  # Up-market capture ratio (%)
    down_capture: float  # Down-market capture ratio (%)
    rolling_alpha_6m: float  # 6-month rolling alpha (%)
    outperformance_months: int  # Count of months beating benchmark
    total_months: int  # Total months compared
    portfolio_returns: pd.Series | None = None  # Aligned portfolio returns (for charts)
    benchmark_returns: pd.Series | None = None  # Aligned benchmark returns (for charts)


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
    # v0.7.9 advanced modules
    zscore: list | None = None
    var_backtest: dict | None = None
    garch_var: dict | None = None
    pelve: dict | None = None
    optimization_advanced: dict | None = None


# Import types from their owning modules to keep each module self-contained.
# This avoids import-order edge cases on Streamlit Cloud's Linux environment.
from engine.factors import FactorRiskReport, MacroDriver  # noqa: F401, E402
from engine.optimization import OptimizationResult, RebalanceSuggestion  # noqa: F401, E402
from engine.recommendations import RecommendationReport  # noqa: F401, E402
from engine.regime import RegimeResult  # noqa: F401, E402
from engine.risk import MonteCarloResult  # noqa: F401, E402
from engine.scenario import MacroScenarioResult, ScenarioResult  # noqa: F401, E402
from engine.scoring import InstitutionalRiskScores  # noqa: F401, E402
from engine.warnings import WarningReport  # noqa: F401, E402
