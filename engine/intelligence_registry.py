"""
Intelligence module registry for NSE Portfolio Risk Scanner.

Centralizes all intelligence modules with consistent error handling,
logging, and result storage. Eliminates 15+ repeated try/except blocks.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from engine._log import logger

# Type for intelligence module functions
IntelligenceFn = Callable[..., Any]

# Registry: (name, function, required_context_keys)
INTELLIGENCE_MODULES: list[tuple[str, IntelligenceFn, list[str]]] = [
    (
        "factor_report",
        lambda ctx: __import__(
            "engine.factors", fromlist=["compute_factor_exposures"]
        ).compute_factor_exposures(ctx["prices"], ctx["weights"], ctx["benchmark_returns"]),
        ["prices", "weights", "benchmark_returns"],
    ),
    (
        "macro_drivers",
        lambda ctx: __import__(
            "engine.factors", fromlist=["estimate_macro_sensitivities"]
        ).estimate_macro_sensitivities(
            ctx["portfolio_returns"], ctx["prices"], ctx["weights"], ctx["benchmark_returns"]
        ),
        ["portfolio_returns", "prices", "weights", "benchmark_returns"],
    ),
    (
        "macro_scenarios",
        lambda ctx: (
            __import__("engine.scenario", fromlist=["run_macro_scenarios"]).run_macro_scenarios(
                ctx["portfolio"].holdings, ctx["stock_betas"]
            )
            if ctx["stock_betas"]
            else []
        ),
        ["portfolio", "stock_betas"],
    ),
    (
        "institutional_scores",
        lambda ctx: __import__(
            "engine.scoring", fromlist=["compute_institutional_scores"]
        ).compute_institutional_scores(
            ctx["risk"], ctx["prices"], ctx["weights"], ctx["sector"].sector_allocation, ctx["raw_corr"]
        ),
        ["risk", "prices", "weights", "sector", "raw_corr"],
    ),
    (
        "early_warnings",
        lambda ctx: __import__("engine.warnings", fromlist=["detect_all_warnings"]).detect_all_warnings(
            ctx["prices"], returns=None, corr_matrix=ctx["raw_corr"]
        ),
        ["prices", "raw_corr"],
    ),
    (
        "recommendations",
        lambda ctx: __import__(
            "engine.recommendations", fromlist=["generate_recommendations"]
        ).generate_recommendations(
            risk=ctx["risk"],
            sector=ctx["sector"],
            benchmark=ctx["benchmark"],
            portfolio=ctx["portfolio"],
            factor_report=ctx.get("factor_report"),
            institutional_scores=ctx.get("institutional_scores"),
            macro_drivers=ctx.get("macro_drivers"),
            corr_matrix=ctx["raw_corr"],
            regime_result=ctx.get("regime_result"),
            profile=ctx["profile"],
        ),
        ["risk", "sector", "benchmark", "portfolio", "raw_corr", "profile"],
    ),
]


def run_intelligence_modules(context: dict) -> dict:
    """
    Run all registered intelligence modules with consistent error handling.

    Args:
        context: Dict containing all required inputs for modules

    Returns:
        Dict mapping module names to results (None on failure)
    """
    results = {}

    for name, fn, required_keys in INTELLIGENCE_MODULES:
        # Validate required keys present
        missing = [k for k in required_keys if k not in context]
        if missing:
            logger.warning(
                "Intelligence module {name} missing context keys: {keys}",
                name=name,
                keys=missing,
            )
            results[name] = None
            continue

        try:
            # Build kwargs from context
            kwargs = {k: context[k] for k in required_keys}
            results[name] = fn(kwargs)
        except Exception as e:
            logger.warning("Intelligence module {name} failed: {e}", name=name, e=e)
            results[name] = None

    return results
