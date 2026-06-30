"""
Data models for the NSE Portfolio Risk Scanner.
Pure dataclasses — no business logic, no dependencies beyond stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


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
class RiskMetrics:
    """Computed risk metrics for the portfolio."""

    volatility_annual: float  # annualized volatility (%)
    var_95: float  # Value at Risk 95% (%)
    var_99: float  # Value at Risk 99% (%)
    cvar_95: float  # Conditional VaR 95% (%)
    max_drawdown: float  # Maximum drawdown (%)
    max_drawdown_start: str  # Drawdown period start
    max_drawdown_end: str  # Drawdown period end
    beta: float  # Beta to Nifty 50
    correlation_to_benchmark: float  # Correlation with benchmark
    sharpe: float  # Sharpe ratio
    sortino: float  # Sortino ratio
    cagr: float  # Compound annual growth rate (%)
    total_return: float  # Total return (%)


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
class OptimizationResult:
    """Optimal portfolio weights from optimization."""

    method: str  # "hrp", "min_volatility", "max_sharpe"
    weights: dict[str, float]  # ticker -> weight
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe: float = 0.0


@dataclass
class MonteCarloResult:
    """Forward-looking Monte Carlo simulation results."""

    n_simulations: int
    horizon_days: int
    expected_return: float  # mean final return %
    median_return: float
    var_95: float  # 95% VaR of final value
    var_99: float
    cvar_95: float
    prob_profit: float  # % of paths ending positive
    ci_lower: float  # 5th percentile return
    ci_upper: float  # 95th percentile return


@dataclass
class RegimeResult:
    """Market regime detection results."""

    n_states: int
    labels: list[str]  # e.g. ["Bull", "Neutral", "Bear"]
    state_sequence: list  # one per trading day (state label per day)
    transition_matrix: list[list[float]]
    stats: list[dict]  # per-regime: return, vol, count


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
