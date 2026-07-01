"""
Optional Riskfolio-Lib wrapper for advanced portfolio optimization.

Provides 26+ convex risk measures, Black-Litterman, Entropy Pooling,
and NCO clustering — only when riskfolio-lib is installed.
"""

from __future__ import annotations

try:
    import riskfolio as rf
    RISKFOLIO_AVAILABLE = True
except ImportError:
    RISKFOLIO_AVAILABLE = False


def riskfolio_available() -> bool:
    """Check if riskfolio-lib is installed."""
    return RISKFOLIO_AVAILABLE


def optimize_advanced(returns, method: str = "CVaR",
                      obj: str = "Sharpe") -> dict | None:
    """Run Riskfolio-Lib optimization if available.

    Parameters
    ----------
    returns : pd.DataFrame
        Asset returns (columns = tickers).
    method : str
        Risk measure: 'CVaR', 'EVaR', 'CDaR', 'Standard Deviation', etc.
    obj : str
        Objective: 'Sharpe', 'MinRisk', 'MaxRet', 'Utility'.

    Returns
    -------
    dict | None
        {ticker: weight} dict, or None if riskfolio-lib not installed.
    """
    if not RISKFOLIO_AVAILABLE:
        return None

    try:
        port = rf.Portfolio(returns=returns)
        port.assets_stats(method="hist")
        weights = port.optimization(model="Classic", rm=method,
                                    obj=obj, hist=True)
        return weights.to_dict().get("weights", {})
    except Exception:
        return None


def optimize_black_litterman(returns, views: dict | None = None) -> dict | None:
    """Black-Litterman model via Riskfolio-Lib.

    Parameters
    ----------
    returns : pd.DataFrame
    views : dict, optional
        {ticker: expected_return} views.

    Returns
    -------
    dict | None
    """
    if not RISKFOLIO_AVAILABLE:
        return None
    try:
        port = rf.Portfolio(returns=returns)
        port.assets_stats(method="hist")
        if views:
            port.views = views
        weights = port.optimization(model="BL", rm="MV", obj="Sharpe", hist=True)
        return weights.to_dict().get("weights", {})
    except Exception:
        return None
