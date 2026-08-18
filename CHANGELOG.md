# Changelog

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

- **Chart images overlapped the following content** (`fig_to_img`)
  Image height was computed from the in-memory figure size, but `savefig(..., bbox_inches="tight")` crops whitespace (suptitles, legends, colorbars) and changes the output aspect ratio. The allocated box was therefore shorter than the real PNG — by up to ~1.25 cm on charts with a suptitle — so the next flowable (Spacer/Paragraph/Table) rendered on top of the chart's bottom edge. Height is now derived from the **actual saved PNG dimensions** via PIL, not `fig.get_size_inches()`.
- **Metric-table cells overflowed into neighbours** (`styled_metric_table`)
  All cells were passed as raw strings. reportlab does not wrap plain-string cells, so long factor names, macro-driver names, or scenario names spilled horizontally across adjacent columns. Every cell is now wrapped in a `Paragraph`, so text wraps inside its column. Header / label / value styles preserved (bold header, muted label, bold foundation value).

### Tests

- Re-verified export with long-name fixtures (factor/driver/scenario) — 0 text-block overlaps across all 8 pages (measured via PyMuPDF bbox collision check).
- Full suite: **397 passed**, 1 skipped (GARCH optional-dep skip). Ruff lint + format clean.

### Fixed — PDF Export Phantom-Schema Crashes (Production Reliability)

The PDF generator (`ui/pdf_reportlab.py`) builds 8 optional intelligence blocks, but
the regression tests only ever passed `None` to most of them. Four blocks read
attributes that **never existed** on the engine dataclasses — each crashed at runtime
only when real data hit production. Two were caught and fixed in prior PRs (#47, #50,
#51); this release closes the remaining two plus hardens all four behind regression tests.

- **Institutional Scores block** (`PR #51`) — read `quality`/`momentum`/`value`/`volatility`/`liquidity`/`esg`/`composite`; rewrote to the real `InstitutionalRiskScores` fields (`overall_risk_score`, `conviction_score`, `portfolio_stress_score`, `hidden_correlation_score`, `tail_risk_score`, `score_interpretation`).
- **Regime block** — read `current_regime`/`regime_probabilities`/`regime_returns`; rewrote to the real `RegimeResult` fields (`state_sequence` → current regime, `stats` → per-regime table, `transition_matrix`/`labels` → transition matrix).
- **Early Warnings block** — read `warning_report.warnings` and `w.message`; `WarningReport` has `signals` and `WarningSignal` has `name`/`description` (no `message`). Rewrote to iterate `signals` and render `name` + `description`; severity label derived from the `SignalSeverity` enum.

### Tests

- `tests/test_pdf_export.py` — `test_generate_pdf_report_with_institutional_scores` feeds a real `compute_institutional_scores()` result through the generator.
- `tests/test_pdf_export.py` — `test_generate_pdf_report_with_regime_recommendations_warnings` feeds real `RegimeResult` / `RecommendationReport` / `WarningReport` instances; exercises all three previously-untested blocks.
- Full suite: **397 passed**, 1 skipped (GARCH optional-dep skip). Ruff clean.

## v0.18.3 (2026-08-17)

### Fixed — Silent Data Failures (Deploy Reliability)

- **vs Nifty 50 showed all zeros** (`engine/benchmark.py`, `data/prices.py`, `ui/render.py`)
  `fetch_benchmark` returned a tz-aware price series while equity prices are tz-naive. The date-aligned inner-join in `compare_to_benchmark` then yielded **0 overlapping rows**, and the function returned `_empty_comparison()` — all-zero metrics with `beta=1.0` that looked like real data to an investor. Benchmark series are now timezone-normalized at the source, and `compare_to_benchmark` also strips tz defensively. When genuinely too little data overlaps, the function returns `None` (no fake zeros), and the UI renders an explicit "Benchmark data is not available" notice plus skips the empty chart overlay.
- **Fundamentals tab showed N/A for every stock** (`ui/fundamentals.py`)
  `fetch_fundamentals` swallowed *all* Yahoo failures into `return {}`, and `@st.cache_data(ttl=3600)` cached that empty dict for an hour. On Streamlit Cloud (Yahoo rate-limited / geo-blocked), every ticker returned `{}` → cached N/A. The fetch now retries on empty payloads / exceptions before giving up, and logs the failure instead of failing silently.

### Tests

- Added `tests/test_benchmark_tz.py` — pins tz-aware benchmark alignment with tz-naive portfolio, and that missing data returns `None` (not fake zeros).
- Updated `tests/test_benchmark.py` empty-series case to expect `None`.
- Full suite: **396 passed**, 1 skipped. Zero regressions. Ruff clean.

## v0.18.2 (2026-08-17)

### Added — Investor Reliability Tests

- **PnL arithmetic** (`tests/test_pnl_math.py`) — Holding/Portfolio profit/loss, sign correctness on losses, zero-current-price handling, div-by-zero guards (`pnl_pct` returns 0 when invested is 0), NaN current_price treated as 0, weight normalization, and zero-current-price weight exclusion.
- **Shareable-link round-trip** (`tests/test_shareable_link.py`) — Extracted `encode_portfolio_link` / `decode_portfolio_link` into `engine/portfolio.py` (pure, no Streamlit) and rewired `app._share_link` + `ui/upload.render_upload_tab` to use them. Tests cover encode→decode fidelity, `.NS` stripping, empty portfolio, URL-safe token, and all malformed-input error paths (garbage token, missing `holdings`, non-list `holdings`, missing required field).
- **`optimize_advanced` returns-contract regression** (`tests/test_optimization.py::TestOptimizeAdvancedReceivesReturns`) — Guards the prices-vs-returns bug: `compute_all` must pass `prices.pct_change().dropna()` (fractional returns), never raw price levels. Captures the argument and asserts max abs value < 1.0.

### Tests

- Added 3 test files + 1 regression class. Full suite: **416 passed**, 1 skipped. Zero regressions. Ruff clean.

## v0.18.1 (2026-08-17)

### Fixed — Logic Correctness (Logic Review Pass)

- **H1 — Optimizer weight cap leaked past the limit** (`engine/optimization.py`)
  The old `_cap_max_weight` clip-and-redistribute re-leaked weight (2 assets + 0.35 cap → `[0.35, 0.65]`). The cap is now a **hard SLSQP solver bound** in `optimize_min_volatility` and `optimize_max_sharpe`, with an idempotent clamp as a safety net. When a cap is mathematically infeasible (`cap < 1/n` assets) the optimizer degrades to equal weight — the closest feasible allocation — instead of silently breaching the cap. HRP already capped correctly.
- **H2 — VaR backtest was circular** (`engine/compute.py`, `engine/backtesting.py`)
  `var_backtest` pinned one constant VaR (the in-sample 5th percentile) to the whole series, which passes by construction and never tests the model. Replaced with `rolling_historical_var_backtest` — each day's VaR is estimated from the trailing window and tested against the **next** day's return (genuine out-of-sample Kupiec POF; can legitimately FAIL when the model mis-estimates tail risk).
- **M2 — Macro scenario double-counted the shock** (`engine/scenario.py`)
  `SECTOR_MULTIPLIERS` were applied **additively** on top of the beta×market impact (crude spike: `-30 + (-30pp) = -60%`). Now applied as a **relative multiplier** `beta·mkt·(1 + adj)`, so e.g. Oil & Gas in a crude spike is 30% *milder* than the market move, not an extra -30pp.
- **M3 — GARCH VaR shown with the wrong sign** (`ui/dashboard.py`)
  `GARCH(1,1) VaR 95%` displayed `+{var_95}` (a positive number) for a loss metric. Now displays `{-var_95:.2%}` (negative loss, consistent with the rest of the risk cards).
- **M1 — VaR horizon ambiguity in PDF report** (`ui/charts_pdf.py`)
  Risk-metrics table now labels VaR as `Daily VaR (95%)` / `Daily VaR (99%)` to disambiguate from the MC horizon VaR shown elsewhere.

### Tests

- `tests/test_optimization.py` — `TestHardCap` (cap binds, preserves sum, infeasible cap degrades to equal weight).
- `tests/test_macro_scenarios.py` — `TestSectorMultiplierRelative` (multiplier not additive; O&G milder than unexposed under crude spike).
- `tests/test_backtesting.py` — `TestRollingHistoricalVarBacktest` (out-of-sample rolling test; insufficient data → empty).
- Full suite: **396 passed** (was 387), 1 skipped. Zero regressions.

## v0.18.0 (2026-08-17)

### Added — User Feedback Implementation

- **Downloadable sample Excel/CSV template** — `ui/sample_template.py` generates exact column format; `engine/portfolio.py` added `parse_portfolio_excel`; download button in upload tab.
- **Ticker autocomplete with NSE symbol mapping** — `engine/ticker_resolver.py` (318-entry offline map + 240 aliases + live Yahoo Finance fallback, ported from NSE Sentiment Analyzer). Type-to-filter selectbox in manual entry.
- **Fundamentals tab** — Valuation (P/E, Forward P/E, PEG, P/B, Div Yield, Mkt Cap), Profitability (ROE, ROA, Profit/Operating Margin), Growth (Revenue/EPS Growth), Financial Health (Debt/Equity, Free Cash Flow). Per-stock expanders.
- **News tab** — Yahoo Finance RSS per holding, de-duplicated, linked headlines with source/date.

### Fixed — Critical Bug

- **Ticker↔Name sync** — Editing ticker in data editor now re-resolves the canonical company name; Name column locked. Uses single `get_company_name` resolver so stale names can never persist.

### Tests

- Added `tests/test_ticker_resolver.py` (16 tests) and `tests/test_fundamentals_news.py` (10 tests). Full suite: 387 passed.

## v0.17.5 (2026-08-16)

### Changed (PDF Export — pdf-studio Ledger Theme)

- **ui/pdf_reportlab.py** — Restyle the self-contained PDF generator to match `pdf-studio`'s **ledger** theme: deep-green foundation `#064E3B`, gold accent `#B45309`, light-green surface `#F0FDF4`, Lora-Bold display headings, Inter body. KPI cards, metric tables, holdings table (green header + gold underline rule, zebra striping), and matplotlib charts (green titles, light-green grid, theme series palette) all carry the pdf-studio chrome.
- **ui/fonts/** — Bundle Inter / Lora Regular + Bold TTFs; registered with both reportlab and matplotlib so typography renders identically offline (no system-font dependency on Streamlit Cloud).
- **tests/test_pdf_export.py** — Retarget to the live generator (previously skipped unless `pdf_studio` was installed). 14 tests cover chart figures, risk-assessment text, and full/minimal PDF assembly.

### Docs

- **docs/showcase/** — Add 4 rendered report pages + sample `portfolio-risk-report.pdf` for README showcase.
- **README.md** — Demo section now previews the exported PDF inline (links to full PDF). Refreshed stale test counts (351/355 → 361).

### Notes

- PDF export uses reportlab + matplotlib directly — no external `pdf-studio` package at runtime — so the Export button stays reliable on Streamlit Cloud.

---

## v0.17.4 (2026-07-28)

### Fixed (Engine Hardening & Sector Coverage)

- **data/prices.py** — Add `.NS` suffix for NSE tickers in yfinance fallback. Fixes silent failures where `HDFCBANK`, `SBIN`, `MONIFTY500`, etc. returned no data from yfinance.
- **engine/regime.py** — Fix `rolling.values >= t` indexing bug in `_detect_statistical()`. The Series comparison was failing with "Lengths must match" error; now uses `.values` for correct numpy array comparison.
- **engine/risk.py** — Harden `compute_stock_risk_attribution()` input validation. Added explicit `None`/empty checks for prices and weights to prevent ambiguous truth-value errors on numpy arrays.
- **engine/scoring.py** — Fix `max(weights)` ambiguity in `_score_concentration_risk()`. Changed to `float(np.max(w))` to avoid "truth value of array is ambiguous" ValueError.
- **engine/sector.py** — Add 23 sector mappings for all portfolio tickers: `MONIFTY500`, `TMCV`, `EXIDEIND`, `SRF`, `IEX`, `MAFANG`, `LIQUIDCASE`, `CASTROLIND`, `METAL`, `SILVERBEES`, `GROWW`, `HDFCSML250`. Eliminates "Unknown" sector classification that triggered false concentration warnings.

### Tests & Quality
- All engine modules pass import/validation without errors
- Sector map now covers 100% of portfolio tickers
- No "Unknown" sectors remain in either portfolio (was 56% and 17% respectively)

---

## v0.17.3 (2026-07-24)

### Fixed

- **Delivery analysis minimum data points** (`engine/delivery.py:50`) — `_compute_delivery()` now requires at least 2 rows of bhavcopy data to compute meaningful delivery metrics. Single-row inputs (insufficient for percentage calculation) now return `None` instead of producing misleading 20% delivery figures.

---

## v0.17.2 (2026-07-24)

### Fixed (Internal Quality & Reliability)

- **CI/CD Pipeline added** (`.github/workflows/ci.yml`) — GitHub Actions workflow with uv, ruff, and pytest matrix (Python 3.11/3.12). Runs on every push/PR to main/master. Fail-fast, concurrency cancel, 15-min timeout.

- **Cache thread safety** (`data/cache.py`) — Added module-level `threading.Lock` around all `diskcache` operations. Prevents race conditions when `ThreadPoolExecutor` (8 workers) calls `PriceCache.set()/get()` concurrently on cold start.

- **Non-deterministic test fixture** (`tests/conftest.py`) — Changed `sample_prices` end date from `datetime.now()` to fixed `datetime(2024, 1, 1)`. Eliminates flaky tests caused by synthetic price data changing daily.

- **SQLite missing indexes** (`storage/db.py`) — Added `idx_analysis_created_desc ON analysis_runs(created_at DESC)` and `idx_analysis_portfolio ON analysis_runs(portfolio_name)`. `list_recent_analyses(limit)` now uses index instead of full table scan.

- **Silent benchmark failure surfaced to UI** (`app.py:236-246`) — When `fetch_benchmark()` fails, user now sees a yellow warning banner: "Could not fetch benchmark data (X). Benchmark comparison (alpha, beta, tracking error) will be unavailable. Try a different benchmark or check network connectivity." Previously failed silently with empty Series.

- **nselib indefinite blocking fixed** (`data/prices.py:95-122`) — Wrapped `capital_market.price_volume_data()` in `ThreadPoolExecutor` with 10s timeout. Previously a single slow NSE API call could hang the entire portfolio fetch (120s future timeout didn't apply — nselib ran in same thread).

- **PDF export tests gracefully skipped** (`tests/test_pdf_export.py`) — Added `@pytest.mark.skipif` when `pdf-studio` not installed. 18 tests now skip cleanly instead of failing with `ImportError`.

### Cleaned (Lint & Dead Code)

- **Unused variable removed** (`ui/dashboard.py:106`) — `skw_label` assigned but never used. Removed.

- **Unused import removed** (`engine/narrative.py:215`) — `ir = benchmark.information_ratio` computed but never referenced. Removed.

- **`contextlib.suppress` replaces try/except** (`engine/portfolio.py:348, 499`) — `_parse_float()` and `_analyze_values()` now use `with suppress(ValueError, TypeError):` instead of bare `try/except/pass`. Cleaner, satisfies ruff SIM105.

- **Explicit `zip(strict=False)`** (`engine/portfolio.py:335`) — Satisfies ruff B905. Behavior unchanged (truncates to shorter iterable).

- **Import sorting** (`tests/conftest.py`) — Removed unused `from contextlib import suppress` import.

### Technical Details

- **Tests:** 338 passed, 0 failed, 18 skipped (PDF tests + hmmlearn)
- **Lint:** ruff clean (0 issues) — E/F/I/N/W/UP/B/SIM all pass
- **Dependencies:** Added `diskcache` to core deps (was optional, now required for L2 cache)

---

## v0.17.1 (2026-07-16)

### Fixed

- **Removed dead code (`engine/factors.py`)** — deleted unused `_compute_rolling_beta()` function (zero callers anywhere in the codebase). Beta is computed inline via covariance.
- **Robust VaR backtest guard (`app.py`)** — added `not np.isnan()` check alongside the existing `!= 0` guard so NaN VaR values are correctly skipped instead of silently producing NaN backtest results.
- **Explicit `betas` type check (`engine/scenario.py`)** — changed `if betas:` to `if betas is not None:` so an empty dict passed intentionally doesn't silently zero out sector impacts.
- **Logged column-resolution warnings (`engine/portfolio.py`)** — `pre_warnings` from `_resolve_column_map()` were captured and discarded. Now logged via `logger.info()` so column-resolution signals aren't silently dropped.

### Changed

- **Hoisted in-function import reverted** (`engine/recommendations.py`) — the lazy `from engine.__init__ import MODERATE, RiskProfile` inside `generate_recommendations()` was flagged by an autopsy tool, but reverting it caused a circular import between `engine.__init__` and `engine.recommendations`. Kept as-is with a note that the lazy import is intentional.

### Tests

- **347 passed, 1 skipped** — zero regressions. The same 8 pre-existing PDF export test failures (`test_pdf_export.py`, numpy/pydantic compatibility) remain unchanged.

### Added

- **Calmar Ratio, Treynor Ratio, Skewness, Excess Kurtosis** (`engine/risk.py`, `ui/dashboard.py`) — new risk metric cards in a fourth row below the existing metrics. Calmar = CAGR ÷ |Max DD| (return per drawdown risk). Treynor = (CAGR − Rf) ÷ β (excess return per unit of market risk). Skewness and excess kurtosis from scipy.stats on daily portfolio returns. In CSV export and PDF report. Guarded against near-zero beta (Treynor = 0 when |β| < 0.1).
- **Portfolio Composition row** (`ui/dashboard.py`, `app.py`) — new section showing ETF / Passive Allocation %, US Exposure % (MAFANG + MASPTOP50), Top-3 Concentration %, and Win/Loss count. Exposed between risk cards and institutional section. No data model changes — all computed at display time from the holdings list.
- **ETF keyword detection** checks each ticker for ETF/BEES/IETF/SML250/LIQUIDCASE. US-exposure looks up MAFANG and MASPTOP50 tickers by exact match.

### Changed

- **RiskMetrics dataclass** — `calmar_ratio`, `skewness`, `kurtosis_excess`, `treynor_ratio` added with default 0.0. Existing code constructing or mocking RiskMetrics continues to work unchanged.

### Tests

- **355 tests pass** — zero regressions. Updated `test_risk_metrics_table` row count from 7→9.

---

## v0.16.2 (2026-07-05)

### Added

- **One-click sample portfolio** (`ui/upload.py`) — "Try Sample Portfolio" button in the empty state instantly loads a 7-holding diversified portfolio covering stocks (RELIANCE, TCS, INFY, ITC, ICICIBANK) plus sector and thematic ETFs (BANKBEES, CPSEETF). No CSV download → re-upload step. Zero overlap with user's personal holdings.

### Fixed

- **Save-before-fetch caused -100% P&L on reload** (`app.py:501-502`) — `render_save_button()` ran before the price-fetch block, persisting `current_price=0.0` to the database. Every newly loaded portfolio briefly showed `-100.00%` until the user triggered a manual refresh. Moved save call after the computation pipeline so only real prices are saved.
- **-100.00% flash between load and compute** (`ui/dashboard.py`) — `render_metric_row()` now checks `total_current > 0` before computing P&L. When prices haven't loaded yet, it shows "—" and "Awaiting prices" instead of `-100.00%`.

### Changed

- **Sample portfolio prices reflect profit** — all 7 avg prices set 15-23% below live market close. Portfolio loads showing +21.59% total P&L with every holding in the green.
- **No overlap with user data** — sample tickers (RELIANCE, TCS, INFY, ITC, ICICIBANK, BANKBEES, CPSEETF) are distinct from any holdings in personal portfolios.

---

## v0.16.1 (2026-07-03)

### Fixed

- **All-NaN price history inflated negative P&L** (`app.py:210-216`) — holdings whose price fetch returned a DataFrame but every value was NaN were silently kept in the portfolio with `current_price=0.0`, making `pnl = -invested_value`. Now removed alongside tickers absent from price data. Added a second filter after the existing failed-ticker check to remove any holding where `current_price == 0.0` after the fetch.

---

## v0.16.0 (2026-07-03)

### Changed

- **PDF report layout polished** (`pdf-studio`, `ui/charts_pdf.py`) — all spacing, alignment, and typography refined to a consistent 8pt grid system. No content changes, no new sections, no visual redesign.
  - **Page margins**: 32pt on all sides (was 72pt). Content area widened ~40%.
  - **Header**: repositioned to 18pt below page top.
  - **Heading spacing**: 14pt below all section headings (was 6pt). Line height tightened to 1.2x.
  - **Body paragraph spacing**: 10pt between paragraphs (was 4pt). Line height 1.35x.
  - **Table padding**: cell vertical padding 6pt, horizontal 8pt (was 4pt/6pt). Header row minimum 28pt.
  - **Holdings table**: numeric columns (Quantity, Avg Price, Current Price, P&L %) right-aligned. Column gutters ≥10pt.
  - **Charts**: consistent 12pt above, 16pt below all chart figures.
  - **Bullet lists**: 14pt left indent, 6pt spacing between items. Hanging indent for wrapped lines.
  - **Muted/disclaimer text**: adjusted spacing for consistent page flow.
  - **Caption style**: 12pt above table captions.

---

## v0.15.0 (2026-07-03)

### Changed

- **fpdf2 + matplotlib promoted to default dependencies** (`requirements.txt`) — PDF export now works with a plain `pip install -r requirements.txt`. Previously required `pip install -e ".[pdf]"`. No import cost increase — imports are lazy at runtime.

---

## v0.14.0 (2026-07-03)

### Removed

- **Dead functions in `data/prices.py`** — `get_stock_info()` (36 LOC), `list_available_benchmarks()` (5 LOC), and `get_cache_stats()` (8 LOC). None were imported or called anywhere in production code. Removal eliminates 3 stale yfinance/nselib code paths that could produce confusing log entries.
- **Dead functions in `engine/performance.py`** — `compute_total_return()` (22 LOC), `compute_win_rate()` (13 LOC), and `compute_holding_returns()` (26 LOC). Only referenced in tests, never in production. Module docstring also updated to reflect current contents (was still mentioning Sharpe/Sortino/CAGR removed in v0.6.1).
- **Corresponding dead tests** — `TestComputeTotalReturn`, `TestComputeWinRate`, and `TestComputeHoldingReturns` test classes removed from `tests/test_performance.py` (82 lines).

### Fixed

- **Emoji in rebalancing table** (`ui/dashboard.py:513`) — `🟢`/`🔴`/`⚪` replaced with plain-text `Buy`/`Sell`/`Hold` labels to match project's Lucide-SVGs-over-emoji convention. SVGs can't render inside dataframe cells, so text labels are the correct approach.
- **Stale version string** (`ui/dashboard.py:192`) — `"(v0.7.9)"` suffix removed from Advanced Analytics expander label. Version strings embedded in UI elements go stale and require unnecessary updates on every release.

### Metrics

- **355 tests pass** — zero regressions, 0 failed, 1 skipped (hmmlearn).

---

## v0.13.0 (2026-07-03)

### Fixed

- **Backtest call args swapped** (`app.py:343-356`) — `backtest_var()` received returns as `var_forecasts` and a scalar as `realized_returns`, and referenced a non-existent `risk.var_95_daily` attribute. Fixed to pass a constant VaR forecast series (historical 5th percentile held constant) and real portfolio returns, using `risk.var_95` converted to decimal. The Kupiec POF test now receives correct inputs and produces meaningful p-values.
- **yfinance imported at module level in `engine/fundamentals.py`** — `import yfinance as yf` at the top of the file forced the yfinance dependency to load on engine init, even when fundamentals analysis was never used. Moved to lazy import inside `compute_zscore()`.
- **`import math` inside `_parse_float()`** (`engine/portfolio.py`) — `import math` was placed inside the function body, re-executed on every call. Hoisted to module top.
- **Duplicate `import math`** (`engine/portfolio.py:506-507`) — a second `import math` existed inside another function. Removed.
- **Indentation error** (`engine/risk.py:69-70`) — 8-space indent instead of 4-space, inconsistent with surrounding code. Fixed.
- **Duplicate `from ui.charts import allocation_pie`** (`ui/dashboard.py:365`) — imported twice in the same file. Removed.
- **`from scipy.stats import chi2` inside function** (`engine/backtesting.py:9,79`) — `chi2` was imported inside `kupiec_pof()` instead of at module level. Moved to top.

### Tests

- Updated `tests/test_fundamentals.py` mock targets from `engine.fundamentals.yf.Ticker` to `yfinance.Ticker` to match lazy-import change.
- **364 passed, 1 skipped** — zero regressions.

---

## v0.12.0 (2026-07-01)

### Removed

- **Dead delivery analysis fetch** — `app.py` called `fetch_delivery_for_holdings()` but never used the result. Removed the unused call.
- **Unused CAGR/Sharpe/Sortino functions** — `compute_cagr`, `compute_sharpe_ratio`, `compute_sortino_ratio` in `engine/performance.py` were duplicated by `engine/risk.py` and never called from the app. Removed the dead code and corresponding tests.
- **`dendrogram_chart()` stub** — dead function in `ui/charts.py` rendered an invisible scatter plot. Never imported. Removed.
- **`optimization_pie()` wrapper** — 3-line wrapper around `allocation_pie()` with no callers. Removed.

### Changed

[Previous content continues...]
