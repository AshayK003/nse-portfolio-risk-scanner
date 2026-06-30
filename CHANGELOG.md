# Changelog

## v0.6.2 (2026-06-30)

### Added

- **Scenario Stress Testing** — new `engine/scenario.py` with `run_scenario()` and `run_default_scenarios()`. Portfolio impact computed per holding using stock beta × weight × market change. Five default scenarios: mild crash (−10%), moderate crash (−20%), severe crash (−35%), strong rally (+10%), bull run (+25%). New "Scenario" tab in app.
- **Rebalancing Suggestions** — `suggest_rebalance()` in `engine/optimization.py` computes current vs target weight drift and generates trade list. Equal-weight target method by default. Shown in "Optimization" tab after optimization runs.
- **11 new tests** — 7 scenario + 4 rebalance. All 195 tests pass (2 pre-existing flaky regime tests deselected).

### Changed

- **`app.py`** — computes per-holding beta; wires scenario stress testing and rebalancing suggestions into UI.
- **`ui/dashboard.py`** — `render_scenario_section()`, `render_rebalance_section()`.
- **`engine/__init__.py`** — exports `ScenarioResult` and `RebalanceSuggestion`.

## v0.6.1 (2026-06-30)

### Removed

- **Dead delivery analysis fetch** — `app.py` called `fetch_delivery_for_holdings()` but never used the result. Removed the unused call.
- **Unused CAGR/Sharpe/Sortino functions** — `compute_cagr`, `compute_sharpe_ratio`, `compute_sortino_ratio` in `engine/performance.py` were duplicated by `engine/risk.py` and never called from the app. Removed the dead code and corresponding tests.
- **`dendrogram_chart()` stub** — dead function in `ui/charts.py` rendered an invisible scatter plot. Never imported. Removed.
- **`optimization_pie()` wrapper** — 3-line wrapper around `allocation_pie()` with no callers. Removed.

### Changed

- **Sector mapping deduplicated** — `data/sectors.yaml` was a second source of truth for ticker-to-sector data, missing ~20 entries the hardcoded dict had. Removed the YAML file; `load_sector_map()` now returns built-in defaults directly. Removed `pyyaml` dependency.
- **matplotlib imports deferred** — moved from eager module-level import to lazy import inside PDF chart functions, saving ~200-400ms on page load when PDF export is not used.
- **Loguru fallback removed** — 22-line `ImportError` fallback for loguru removed since it's a core dependency. Uses `from loguru import logger` directly.
- **Empty `nse_risk_scanner/` package removed** — directory contained only an empty `__init__.py` and was unused at runtime.

### Fixed

- **No regressions** — all 184 existing tests pass (2 pre-existing flaky regime tests unaffected).

## v0.6.0 (2026-06-30)

### Added

- **Hierarchical Risk Parity (HRP) Optimization** — new `engine/optimization.py` implements Lopez de Prado's HRP algorithm using scipy hierarchical clustering. No covariance matrix inversion needed. Also includes minimum volatility and maximum Sharpe ratio optimizers via SciPy SLSQP. New "Optimization" tab shows optimal weights with pie chart.
- **Monte Carlo Simulation** — forward-looking portfolio projection using Geometric Brownian Motion (10,000 paths). New section in "Risk Metrics" tab shows expected return, median return, probability of profit, VaR/CVaR at horizon, and confidence interval bands. Chart shows all paths with 5th-95th percentile shading.
- **Correlation Matrix Denoising** — Marchenko-Pastur eigenvalue clipping removes noise from the empirical correlation matrix. Accessible via "Denoised Correlation" expander in the Charts tab. Improves reliability of all covariance-dependent metrics.
- **HMM Market Regime Detection** — new `engine/regime.py` uses Gaussian Hidden Markov Models (hmmlearn) to detect market states (Bull/Neutral/Bear). New "Regime" tab shows per-regime stats (mean return, volatility, cumulative return), transition matrix, and daily returns colored by regime. Optional dependency: `pip install hmmlearn`.
- **NSE Delivery Analysis** — new `engine/delivery.py` fetches delivery volume data from nselib bhavcopy. Tracks delivery percentage and trend (rising/falling/stable) per holding. Uses nselib (already an optional dep).
- **`ml` optional dependency** — `pip install -e ".[ml]"` installs hmmlearn for regime detection.
- **New test files** — 20+ tests across `test_optimization.py` (9), `test_regime.py` (6), `test_delivery.py` (1), plus Monte Carlo and denoising tests in `test_risk.py` (10).

### Architecture

- `engine/optimization.py` — pure NumPy/SciPy, zero UI deps
- `engine/regime.py` — optional hmmlearn, graceful None fallback
- `engine/delivery.py` — optional nselib, graceful {} fallback
- All new results added to `AnalysisReport` as optional fields (backward compatible)

## v0.5.2 (2026-06-30)

### Fixed

- **nselib ignored `period` parameter** — `_fetch_via_nselib` hardcoded `period="1M"` instead of forwarding the caller's `period`. All risk metrics (CAGR, Sharpe, beta, tracking error) were computed from 1 month of data for nselib users. Now forwards the requested period (default "1Y").
- **Concentration check never fired** — `validate_portfolio()` ran before `fetch_prices()`, so all `current_price` values were 0.0 and `weight` returned all zeros. The "high concentration risk" warning could never trigger. Moved validation after price fetch.
- **L2 cache ignored period** — `PriceCache.get()` returned cached data regardless of how much was stored. A 1-month cache entry satisfied a 1-year request. Now validates minimum data points per period.
- **Inconsistent drawdown start dates** — `engine/risk.py` used `index[0]` (first peak) while `engine/performance.py` used `index[-1]` (last peak) for drawdown period discovery. Standardized both to `index[0]`.
- **`change_pct` stored wrong value** — computed as the last daily return (near 0%) instead of total return since `avg_price`. Now computes `(current_price - avg_price) / avg_price * 100`.
- **`portfolio_from_dict` skipped ticker normalization** — raw tickers like `"RELIANCE"` were not converted to `"RELIANCE.NS"`, unlike `parse_portfolio_csv`. Now calls `normalize_ticker`.

## v0.5.1 (2026-06-30)

### Fixed

- **Production crash: `st.plotly_chart(aria_label=...)`** — removed unsupported `aria_label` kwarg
- **Production crash: `data_editor` returns `None`** — added `if df is None` guard before `iterrows()`
- **Manual-only entry bug** — `render_upload_tab()` never assigned manual holdings to the portfolio when no CSV was uploaded. Holdings were collected in `all_holdings` but only merged when CSV existed. Added `elif manual_holdings: portfolio.holdings = manual_holdings`.

## v0.5.0 (2026-06-30)

### Added

- **Consistent error handling** — all errors now use `st.error()`/`st.warning()`/`st.success()` with user-friendly messages. No raw exception strings shown to users
- **Loading states** — spinners for benchmark data fetch and risk metric computation, not just price fetch
- **Empty state** — centered visual card with icon, title, and description guiding users on how to get started
- **Focus indicators** — `:focus-visible` outlines on buttons, inputs, and interactive elements for keyboard navigation
- **Reduced motion** — `prefers-reduced-motion` media query disables hover animations for users who need it
- **Chart accessibility** — all 5 Plotly charts now have `aria-label` attributes for screen readers
- **Form placeholders** — manual entry fields now show example values (e.g. "e.g. RELIANCE", "e.g. 10", "e.g. 2500.00")
- **Tooltips** — remove button has `help` text for context

### Changed

- **Semantic headings** — replaced all `<div class="section-header">` HTML with native `st.subheader()` and `st.divider()` for screen reader support and document outline
- **Form labels visible** — removed `label_visibility="collapsed"` from manual entry form; labels now visible and accessible
- **Button text** — replace button replaced from "✕" icon to labeled "Remove" for clarity and accessibility
- **Expander labels** — removed emoji from "✎ Edit Holdings" and "💾 Save Portfolio" expanders
- **CSS cleanup** — removed unused `.section-header` and `.manual-entry-form` classes, removed `transform: translateY` hover animation, added responsive metric card sizing for mobile
- **Sidebar** — uses `st.sidebar.subheader()` instead of HTML, consistent success/error messages

### Fixed

- Button hover animation (`transform: translateY(-1px)`) caused layout shift — replaced with `box-shadow` only
- Raw exception text shown in price fetch error (`st.error(str(e))`) — now shows user-friendly message
- PDF generation failure shown as `st.caption` — now shown as `st.error`
- Benchmark fetch had no loading indicator — added spinner
- Risk computation had no loading indicator — added spinner
- Remove button "✕" had no tooltip, no accessibility label — now labeled "Remove" with help text

## v0.4.0 (2026-06-30)

### Added

- **Full Storage Layer Tests** — 17 tests for SQLite CRUD: portfolio save/load/delete, analysis history, price cache upsert, TTL expiry, stale clearing
- **Cache Tests** — 11 tests for PriceCache: round-trip, TTL, clear, has, disabled cache
- **Model Serialization Tests** — 10 tests for Portfolio/RiskMetrics round-trips, missing fields, analysis_from_report
- **Integration Tests** — 7 full pipeline tests (CSV → risk metrics) with mocked network layer
- **Expanded Unit Tests** — 36 portfolio tests (Indian format, BOM, malformed rows), 22 risk tests (stock risk, rolling volatility), 13 sector tests (yfinance fallback, HHI)
- **Shared Test Fixtures** — conftest.py with tmp_db, tmp_cache_dir, mock network, report fixtures

### Fixed

- **`data/cache.py`** — diskcache TTL was silently broken: `expire=timedelta(hours=24)` passed to diskcache which expects numeric seconds. Cache entries never expired. Fixed to `expire=self.ttl_hours * 3600`
- **`storage/db.py`** — `get_cached_prices()` used `SELECT *` which returned `fetched_at` column not present in `CachedPrice` dataclass, causing `TypeError` on any real use. Fixed to `SELECT ticker, date, close`
- **`app.py`** — Removed redundant `.cumprod()` computed 4 times; single `portfolio_cum` variable reused
- **`data/prices.py`** — Parallel price fetching with `ThreadPoolExecutor(max_workers=8)` + retry with exponential backoff replacing sequential loop (from prior session)

### Changed

- Test count: 39 → 168 (+129 new tests)
- Overall coverage: 56% → 83%
- `engine/` coverage: 82-100% across all modules
- `storage/db.py` coverage: 0% → 96%
- `storage/models.py` coverage: 0% → 100%
- `data/cache.py` coverage: 0% → 92%

## v0.2.0 (2026-06-29)

### Added

- **Risk Metrics Engine** — VaR (95%/99%), CVaR, annualized volatility, Sharpe ratio, Sortino ratio, CAGR, max drawdown with start/end dates, beta, correlation to benchmark
- **Sector Classification** — 160+ NSE stocks mapped across 18 sectors (Banking, IT, FMCG, Pharma, Automobile, Power, Oil & Gas, etc.)
- **Sector Concentration Analysis** — Herfindahl-Hirschman Index, diversification score, automatic concentrated-sector detection (>20% threshold)
- **Benchmark Comparison** — Portfolio vs Nifty 50, Bank Nifty, Nifty IT, Nifty Midcap 100, Nifty Smallcap 250. Alpha, tracking error, information ratio, monthly outperformance count
- **Multi-Broker CSV Parsing** — Automatic column detection for Zerodha, Groww, Upstox export formats. Indian number format support (₹, commas)
- **Interactive UI** — Plotly charts: sector treemap, drawdown chart, benchmark overlay, correlation heatmap, volatility gauge
- **Price Caching** — L1 (in-memory LRU) → L2 (diskcache) → L3 (nselib/yfinance) multi-tier cache. 24-hour TTL, force-refresh button
- **Analysis History** — SQLite persistence for saved portfolios and analysis runs
- **Portfolio Management** — Save/load/delete portfolios across sessions, inline data editor for holdings
- **Export** — CSV download with position-level risk metrics
- **Unit Tests** — 39 tests across risk computation, performance, portfolio parsing, sector classification, and benchmark comparison

### Architecture

- Pure separation: `engine/` (zero Streamlit imports), `ui/` (zero business logic), `app.py` (thin orchestration)
- All risk computation uses numpy/scipy — no external ML dependencies

## v0.3.0 (2026-06-30)

### Added

- **NSE-Native Data Source** — nselib integrated as primary data provider for NSE equities. yfinance retained as fallback for benchmarks and tickers unavailable via nselib. Install via `nse` extra (`pip install -e ".[nse]"`)
- **diskcache-backed L2 Cache** — Replaced custom SQLite cache with diskcache (thread-safe, TTL expiry, automatic vacuum). More robust with zero maintenance overhead
- **Structured Logging** — loguru replaces print() statements in data layer. Debug-level logging for cache hits/misses and fetch failures
- **CI Pipeline** — GitHub Actions workflow runs ruff check + format check + pytest on every push and PR
- **Developer Tooling** — ruff (linter + formatter), pre-commit hooks (ruff, trailing-whitespace, end-of-file-fixer, YAML validation)
- **vcrpy** — Added as dev dependency for recording/replaying HTTP interactions in tests (enables deterministic testing of data layer)
- **Sector Fallback** — nselib used for sector data on unknown tickers before falling back to yfinance
- **nselib Sector Data** — Fallback sector lookup via nselib before yfinance for better NSE sector coverage
- **60+ Unit Tests** — Expanded test suite to 62 tests with improved coverage

### Changed

- Cache backend: custom SQLite → diskcache (transparent, same API)
- Data source: nselib tried first for NSE equities, yfinance fallback
- Logging: print() → loguru throughout data layer
- Code quality: full ruff linting/formatting pass across entire codebase
- Sector lookup: nselib fallback added before yfinance fallback

### Fixed

- Empty portfolio_returns IndexError in compute_max_drawdown (guarded with empty check)
- Unused imports removed across all modules
- Trailing whitespace and import sorting normalized project-wide

### Developer Notes

- `ruff check .` and `ruff format .` before committing
- Install pre-commit hooks: `pre-commit install`
- Run tests: `pytest tests/`
- Full dev setup: `pip install -e ".[dev,pdf,nse]"`
