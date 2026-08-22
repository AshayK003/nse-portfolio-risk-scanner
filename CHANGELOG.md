# Changelog

## v0.20.2 (2026-08-22)

### Removed — Dead Code Sweep

Zombie-function cleanup from the codebase audit: functions defined, tested, but never called by any production path. Each deletion was verified against static imports, dynamic `__import__` targets, string-path references, and internal call sites before removal.

- `engine/delivery.py` — entire module (delivery-volume analysis, optional nselib feature never wired into the app) + its tests
`intelligence_registry.get_module_names` — debug helper with zero callers
- `optimization_advanced.optimize_black_litterman` / `riskfolio_available` — unreachable; the optimizer path uses `optimize_advanced`
- `performance.compute_max_drawdown` — superseded by inline drawdown computation in compute/risk
- `ticker_resolver.resolve_ticker` — superseded by `build_ticker_options`/`parse_ticker_option`
- `render.render_disclaimer_footer` / `render_export_tab` retained (called by `render_all_tabs`)
- `sample_template.build_sample_csv` and `upload.render_save_button` — dead UI paths
- 30 orphaned test methods removed alongside their subjects

**Kept after verification** (audit flagged, triage saved): `kupiec_pof`, `backtest_var`, `run_scenario`, `build_tax_lots`, `portfolio_from_dict`, `render_export_tab`, `render_disclaimer_footer`.

**Tests**: 391 passed, 0 failed, 1 skipped (−30 orphaned tests).

---

## v0.20.1 (2026-08-22)

### Fixed — Audit Remediation Round 2

Findings from the post-release codebase audit (M10/M15/M16/M23), plus community issue triage.

**High**
- **XSS via engine-generated strings in HTML:** three `unsafe_allow_html` sites (health card, top-5 insights, recommendation cards) interpolated `score_interpretation`, `insight.name/reasoning`, and card `tickers`/`reason`/`alternatives` unescaped. All now pass through `html.escape()`.
- **Recommendations always assumed a bull market:** market regime was hardcoded to `BULL`; VIX/ADX/breadth/MA200-distance used fixed fallbacks with no derivation. The regime is now derived from the HMM state sequence (latest label → Bull/Neutral/Bear/Crisis), so bear-market guardrails can actually fire. Remaining feed values (VIX, breadth) keep documented neutral fallbacks until live sources are wired.
- **VaR backtest FAIL rendered green:** the PASS/FAIL delta lacked a direction hint, so Streamlit's default made FAIL green. FAIL is now red.

**Low**
- **Custom app icon (#61):** the browser tab showed the default Streamlit icon. Added a branded favicon (`assets/favicon.png`) matching the app palette.

### Closed as already-fixed (verified against v0.20.0)
- #62 holdings editor sync and #63 recommendations refresh: the input-hash gate recomputes whenever any holding changes — verified hash changes on quantity edit and recommendations follow the new portfolio.
- #64 deterministic recommendations: profile-driven rules shipped in v0.20.0 (25%/35%/50% caps per profile).
- #19 color contrast fixes: WCAG contrast sweep shipped in v0.20.0.

**Tests**: 421 passed, 0 failed, 1 skipped.

---

## v0.20.0 (2026-08-22)

### Fixed — Visual UI Audit Remediation

Findings from a full visual audit (headless browser walkthrough of every tab, DOM + computed-style verification).

**High**
- **Health card contradiction:** `_interpret_scores` risk bands (>70/>45) disagreed with the health gauge labels (`health = 100 − overall`, bands at 70/40). A 65/100 "Moderate" gauge could show "LOW RISK" text. Bands aligned to 30/60 so interpretation always matches the gauge.
- **Empty-portfolio sentinel poisoning session state:** the empty state returned `Portfolio(holdings=[])` which was persisted and later used as a real portfolio. Only non-empty portfolios are now stored.
- **Recommendations ignored the Risk Profile:** `generate_recommendations` accepted `profile` but used a hardcoded default. Concentration caps, single-name limits, and horizon now derive from the selected Conservative/Moderate/Aggressive profile — verified that each profile produces different recommendation rules (25%/35%/50% caps).
- **Latent crash on recommendations with unpriced holdings:** `getattr(h, "current_price", h.avg_price)` returned `None` for declared-but-unset dataclass fields (`int * None` TypeError). Falls back to `avg_price` explicitly.

**Medium**
- **Negative returns rendered in neutral white:** Portfolio/Benchmark Return on the "vs Nifty 50" tab now carry red deltas for negative values; positive P&L stays green.
- **Contrast sweep:** input borders visible against dark background, placeholder/label/caption text lifted above WCAG minimums, checkbox labels brightened, inactive tabs brightened, download button given a clear interactive style.

**Low**
- **Checkbox placement:** "Force refresh prices" moved inline next to the Benchmark Index selector instead of floating above the metrics row.

**Tests**
- Added `tests/test_recommendations_profile.py` (3 tests: per-profile concentration caps, aggressive relaxation) and `tests/test_ui_audit_regressions.py` (6 AppTest black-box tests: sample button, empty-state persistence, band alignment).
- Full suite: 421 passed, 1 skipped.

---

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

### Fixed — Audit Remediation (independent code review, 2026-08-21)

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