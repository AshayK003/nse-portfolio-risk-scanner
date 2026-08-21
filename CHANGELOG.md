# Changelog

## v0.19.3 (2026-08-21)

### Fixed — Deployed Crash Regressions (black-box verification)

Two crashes surfaced by a headless `streamlit.testing.v1.AppTest` run against a sample portfolio (injected via the share link, exercising L2 decode + H1 import path).

- **M1 regression — widget-key mutation crash:** The v0.19.2 M1 fix wrote `st.session_state.force_refresh_cb = False` after the checkbox widget was instantiated. Streamlit 1.61 hard-forbids mutating a widget's session_state key post-instantiation, so the app crashed on the next rerun with `st.session_state.force_refresh_cb cannot be modified after the widget ... is instantiated`. Removed the write; the separate non-widget `force_refresh` key already resets correctly.
- **Export crash — `RecommendationReport` field mismatch:** `ui/export.py` accessed `recommendations.recommendations`, `rec.target`, `rec.expected_risk_reduction`, `rec.reasoning`, and `recommendations.risk_reduction_potential` — none of which exist on the post-refactor `RecommendationReport` dataclass (fields are `cards`, `tickers`, `net_risk_reduction_bps`, `reason`, `total_risk_reduction_bps`). The export tab crashed on every analysis. Aligned the CSV serializer to the real dataclass shape (mirroring the defensive `hasattr` handling already present in `ui/render.py`).

**Tests**
- Added `tests/test_app_blackbox.py` (3 AppTest black-box tests: load+render, force-refresh rerun, benchmark-change rerun).
- Full suite: 412 passed, 1 skipped. Ruff + format clean.

---

## v0.19.2 (2026-08-21)

### Fixed — Audit Remediation (OpenCode review, 2026-08-21)

Remediated 15 findings from an independent code audit. Each fix is backed by a regression test in `tests/test_audit_fixes.py`.

**High**
- **H1 — Module shadowing (ImportError trap):** Removed dead module-level `engine/recommendations.py` that shadowed the `engine/recommendations/` package. Re-exported `generate_recommendations` from the package `__init__` so `scripts/analyze_portfolios.py` and `engine/intelligence_registry.py` both resolve it. (The audit suggested deleting `engine/recommendations/engine.py` — that file is the live implementation the registry imports; deleting it would have silently disabled the recommendation engine.)

**Medium**
- **M1 — Sticky force-refresh loop:** Reset `st.session_state.force_refresh_cb` after compute so reruns don't re-trigger a full yfinance refetch + duplicate `analysis_runs` row on every slider move.
- **M2 — HTML injection from RSS (XSS):** `ui/news.py` now `html.escape`s title/link/source/published and restricts links to `http(s)` schemes before rendering with `unsafe_allow_html`.
- **M3 — Input-hash drift:** `_input_hash` now hashes only user inputs (ticker, quantity, avg_price); it no longer includes `current_price`, which `fetch_prices` mutates — eliminating a guaranteed second recompute.
- **M4 — CSV formula injection (CWE-1236):** `_esc` in `ui/export.py` now prefixes a leading `= + - @` with an apostrophe so a hostile holding name can't execute as a spreadsheet formula.

**Low**
- **L1:** `analysis_from_report` accepts `benchmark_name`; the app now records the actually-selected benchmark instead of hardcoding "NIFTY 50".
- **L2:** Share links use URL-safe base64; decode enforces the holdings cap and validates `q`/`p` as non-negative numerics.
- **L3:** `portfolio.name` is escaped in the exported CSV summary.
- **L5:** `_log` no longer crashes on literal `{`/`}` in log messages (guarded with `contextlib.suppress`).
- **L7:** `load_portfolio` / `list_saved_portfolios` ignore unknown columns, surviving schema drift.
- **L8:** Fixed `from engine.__init__ import ...` (now `from engine import ...`); removed a dead `st.session_state._cache`.
- **L9 (CI):** Cache keyed on `uv.lock`; lint step now covers `scripts/`.
- **L10:** Removed duplicate `pdf-studio-py` pin from the `[pdf]` extra (kept in main deps).
- **L11:** Timeout handling catches `concurrent.futures.TimeoutError` as well as builtin `TimeoutError`.
- **Lint:** Fixed F601 duplicate `NMDC` key in `scripts/introspect.py`.

**Tests**
- Added `tests/test_audit_fixes.py` (8 regression tests). Full suite: 409 passed, 1 skipped. Ruff clean.

---

## v0.19.1 (2026-08-19)

### Fixed — Upload Tab Empty Portfolio Crash

Fixed a crash in `ui/upload.py` where `render_upload_tab()` returned `None` when no CSV or manual holdings were provided, causing a downstream `TypeError` in `app.py` when trying to use the returned `None` as a `Portfolio` object.

**Fix:** Modified `render_upload_tab()` in `ui/upload.py` to return an empty `Portfolio(holdings=[], name="Empty Portfolio")` instead of `None` when no CSV or manual holdings are provided. This prevents downstream crashes in `app.py` and provides a clean empty state for the UI.

**Related:** Fixes the `TypeError: 'NoneType' object is not iterable` / `portfolio = csv_portfolio or Portfolio(...)` crash reported on Streamlit Cloud.

### Fixed — Delete Portfolio Button Safety

Added safe dictionary access in `render_sidebar()` delete logic to prevent `KeyError` when deleting portfolios.

---

## v0.19.0 (2026-08-18)

### Added — Deterministic Recommendation Rule System

A complete, production-ready recommendation engine with 12 deterministic rules governed by a strict governance pattern (BLOCK > REDUCE > PASS). Replaces ad-hoc heuristics with auditable, testable logic.

**Rules Implemented:**
- **Concentration** — Single-name (>15%) and sector (>20%) caps with TRIM actions
- **ETF Overlap** — Detects duplicate index ETFs (NIFTYBEES/MONIFTY500/NEXT50IETF) and consolidates
- **Sharpe Underperformance** — Flags portfolio Sharpe < 0.5, recommends BUY toward higher-Sharpe holdings
- **Regime: VIX Spike** — VIX > 28 → BLOCK shorts, TRIM longs 50%
- **Regime: ADX Doldrums** — ADX < 15 → BLOCK breakout strategies
- **Breadth Confirmation** — A/D ratio misaligned with portfolio bias → TRIM
- **FII/DII Confluence** — FII/DII bias contradicts portfolio direction → TRIM 50%
- **Expiry Week** — Reduces all position sizes by 20%
- **Tax Loss Harvest** — Harvests STCL > ₹5k for STCG offset
- **Cash Floor** — Cash below floor → SELL lowest conviction to raise cash

**Architecture:**
- **Rule Registry** (Governance Pattern) — Each rule is a pure function `ctx → list[RuleVerdict]`; strictest override wins (BLOCK > REDUCE > PASS); per-rule try/except prevents pipeline crashes
- **Orchestrator** — Assembles verdicts into `RecommendationCard[]` + `RecommendationReport`; deduplicates by (action, ticker); computes net risk reduction (bps) minus tax + impact costs
- **Intelligence Registry** — `generate_recommendations()` wrapper for registry integration
- **Frontend** — `render_recommendations_tab()` renders `RecommendationCard[]` with reasoning, triggered rules, tax/impact costs, net risk reduction, guardrails ("Don't execute if..."), alternatives
- **PDF Export** — Backward-compatible `RecommendationReport.priority_actions` for existing generator

**Frontend Cards** include: action badge, reasoning, triggered rules with reasons, tax/impact breakdown, net risk reduction (bps), guardrails ("Don't execute if..."), alternatives considered

**Sample Output (Ashay's Portfolio):**
```
Generated 11 cards:
  Exit HDFCBANK.NS - sell - immediate - 0.90
    Guardrails: ['Execute only during market hours']
    Tax: ₹0 | Impact: ₹9
  Reduce NIFTYBEES.NS - trim - near_term - 0.90
    Reason: Broad Market at 32.8% > 20.0% cap
    Net risk reduction: 114 bps | Tax: ₹2,999
```

**Tests:** 12 new tests + all existing (401 pass, 1 skipped)

---

## v0.18.7 (2026-08-18)

### Fixed — Risk Reporting Display Defects (Decision Reliability)

Two display defects made the engine's risk output misleading in the report/CLI path. Neither affected the underlying score math or the web UI's internal calculations; both affected what a reader actually sees.

- **Risk-score prose showed percentages 100× too small** (`engine/scoring.py`)
  The scoring functions receive VaR/drawdown/CVaR as decimals (e.g. `0.0152` for −1.52%), and three reasoning strings printed them with `:.2f%` / `:.1f%` format specifiers that do **not** auto-scale — so a user read `Daily VaR(95%) is -0.02%` when the true value was **−1.52%**. Fixed `_score_var_risk`, `_score_drawdown_risk`, and `_score_tail_risk` to use `:.2%` / `:.1%` (auto ×100). Score contributions, composites, and the web UI were always correct; only the explanatory text was wrong.

- **Stock Risk Attribution betas defaulted to 1.0 outside the web UI** (`scripts/analyze_portfolios.py`)
  `compute_stock_risk_attribution` falls back to `beta=1.0` for every holding when `stock_betas` is not supplied. The web UI passes real betas, but the analysis script called it without that argument, so every row showed a placeholder 1.0. The script now fetches the Nifty benchmark, computes real per-holding betas via the engine's existing `_compute_stock_betas`, and passes them in. A graceful fallback to 1.0 is preserved if the benchmark fetch fails.

### Tests

- Full suite: **397 passed**, 1 skipped. No regressions in scoring or attribution.
- Verification run confirmed corrected output: VaR prose now reports −1.52% (was −0.02%), drawdown −9.9%, CVaR −2.20%; attribution betas populated per holding (e.g. high-beta names correctly above 1.0, defensive names below).

---

## v0.18.6 (2026-08-18)

### Added — Charts in Empty Report Spaces

The three analytics pages that were previously table-only now include a chart that visualises the same data, filling trailing whitespace:

- **Factor Risk Decomposition (p5)** — horizontal bar of risk contribution % per factor + idiosyncratic (`_factor_risk_chart`), sourced from `FactorRiskReport`.
- **Macro / Scenario (p6)** — horizontal bar of portfolio impact % under each macro stress scenario (`_scenario_chart`), sourced from `scenario_results`; negative impacts shaded red, positive green.
- **Regime (p7)** — bar of time spent in each detected regime (`_regime_chart`), sourced from `RegimeResult.stats`.

All three reuse the existing `_base_chart_style` brand chrome and `fig_to_img` (PNG-accurate height), so they match the cover/risk/holdings charts and inherit the overlap fix from v0.18.5. Each chart is rendered only when its source data is present.

### Tests

- Full suite: **397 passed**, 1 skipped. New chart helpers exercised via existing PDF export tests (factor + scenario on the factor/macro run; regime on the regime run). Generated report verified: 0 text-block overlaps across all 8 pages; page 6/7/8 each gained one chart image.

### Fixed — PDF Overlapping Text (Layout Reliability)

Two layout defects caused text to overlap other text/tables on exported PDF pages: