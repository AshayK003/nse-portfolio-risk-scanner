"""
Storage-layer data models.
These extend the engine dataclasses with persistence-specific fields
like IDs, timestamps, and serialization helpers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from engine import AnalysisReport, Holding, Portfolio


@dataclass
class SavedPortfolio:
    """A portfolio saved to the SQLite database."""

    id: int | None = None
    name: str = ""
    holdings_json: str = ""  # JSON-serialized list of holdings
    created_at: str = ""  # ISO datetime string
    updated_at: str = ""
    total_invested: float = 0.0
    total_current: float = 0.0
    total_pnl: float = 0.0


@dataclass
class AnalysisRun:
    """A recorded analysis run for history tracking."""

    id: int | None = None
    portfolio_name: str = ""
    holding_count: int = 0
    volatility: float = 0.0
    var_95: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    cagr: float = 0.0
    beta: float = 0.0
    diversification_score: float = 0.0
    benchmark_name: str = "NIFTY 50"
    created_at: str = ""  # ISO datetime string


@dataclass
class CachedPrice:
    """A cached price data entry for a single ticker on a single date."""

    ticker: str = ""
    date: str = ""
    close: float = 0.0


# ── Serialization helpers ──


def portfolio_to_saved(p: Portfolio, name: str = "") -> SavedPortfolio:
    """Convert an engine Portfolio to a SavedPortfolio for persistence."""
    import json

    holdings_data = []
    for h in p.holdings:
        holdings_data.append(asdict(h))
    return SavedPortfolio(
        name=name or p.name,
        holdings_json=json.dumps(holdings_data),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        total_invested=round(p.total_invested, 2),
        total_current=round(p.total_current, 2),
        total_pnl=round(p.total_pnl, 2),
    )


def saved_to_portfolio(sp: SavedPortfolio) -> Portfolio:
    """Reconstruct an engine Portfolio from a SavedPortfolio."""
    import json

    holdings_data = json.loads(sp.holdings_json)
    holdings = [
        Holding(
            ticker=h["ticker"],
            name=h.get("name", h["ticker"]),
            quantity=h["quantity"],
            avg_price=h["avg_price"],
            sector=h.get("sector", ""),
            current_price=h.get("current_price", 0.0),
            change_pct=h.get("change_pct", 0.0),
        )
        for h in holdings_data
    ]
    return Portfolio(holdings=holdings, name=sp.name)


def analysis_from_report(report: AnalysisReport, portfolio_name: str = "") -> AnalysisRun:
    """Create an AnalysisRun record from an AnalysisReport."""
    return AnalysisRun(
        portfolio_name=portfolio_name or report.portfolio.name,
        holding_count=report.portfolio.holding_count,
        volatility=report.risk.volatility_annual,
        var_95=report.risk.var_95,
        max_drawdown=report.risk.max_drawdown,
        sharpe=report.risk.sharpe,
        cagr=report.risk.cagr,
        beta=report.risk.beta,
        diversification_score=report.sector.diversification_score,
        created_at=datetime.now().isoformat(),
    )
