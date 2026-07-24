# Changelog

## v0.17.3 (2026-07-24)

### Fixed

- **Delivery analysis minimum data points** (`engine/delivery.py:50`) — `_compute_delivery()` now requires at least 2 rows of bhavcopy data to compute meaningful delivery metrics. Single-row inputs (insufficient for percentage calculation) now return `None` instead of producing misleading 20% delivery figures.

### Internal

- **Internal docs moved to `internals/`** — Audit reports, research notes, and engineering memory moved to `internals/` (gitignored per SOUL.md). Keeps repo clean; internal files never committed to public history.

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
- **No overlap with user data** — sample tickers (RELIANCE, TCS, INFY, ITC, ICICIBANK, BANKBEES, CPSEETF) are distinct from any holdings in Ashay's or Rishu's real portfolios.

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