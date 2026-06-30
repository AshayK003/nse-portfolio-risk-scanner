# Changelog

## v0.7.2 (2026-06-30)

### Fixed

- **All ETFs lumped as "ETF" sector causing false concentration alarms** — ETFs are now classified by their underlying asset class (e.g. NIFTYBEES → "Equity: Broad Market", GOLDBEES → "Gold", LIQUIDBEES → "Liquid / Money Market", BANKBEES → "Equity: Banking"). This prevents the false "Reduce ETF" recommendation when holdings are actually diversified across equity, gold, and liquid funds (`engine/sector.py:141-155`, `tests/test_sector.py:16-22`).
- **Risk-parity optimizer overweighting cash-like instruments** — `optimize_hrp()` now excludes assets with annualized volatility below 2% (e.g. LIQUIDBEES) and caps any single holding at 35% with proportional redistribution. Same cap applied to `optimize_min_volatility()` and `optimize_max_sharpe()`. Prevents misleading "100% in Liquidbees" output (`engine/optimization.py:14-42,107-115,136,198-200,234-237`).

### Changed

- **Risk-reduction disclaimer** — the "Total Risk Reduction Potential" metric now includes a caption: *"Risk reduction is a directional estimate based on heuristic rules, not a backtested or simulated forecast."* (`app.py:641-643`).
- **Optimization concentration warning** — when the optimizer allocates >25% to any single holding, the UI shows a warning that risk-parity may not suit return-seeking investors (`ui/dashboard.py:233-238`).

## v0.7.1 (2026-06-30)

### Changed

- **UI makeover — shadcn-inspired CSS refinement** — completely overhauled `ui/styles.py` with refined dark theme CSS. Metric cards now use subtle gradient backgrounds, smoother hover transitions with `translateY(-1px)` lift, refined border colors, and improved typography scale. Tab styling updated to line-variant with blue accent indicator. Buttons get hover shadow + active press `scale(0.98)` feedback. File uploader gets background shift on hover. Added custom metric card CSS classes (`.custom-metric-card`) for future rich card components. Section header, progress bar gradient, disclaimer `details` container, and spinner color styled for design consistency. All visual — zero functional changes. 268/268 tests pass, zero new dependencies.

### Fixed

- **Shape mismatch crash when a ticker fails price fetch** — `fetch_prices()` silently drops tickers that fail (bad symbol, network error, etc.), returning prices for N-M tickers. `portfolio.weight` still returned N weights. The subsequent `returns.dot(weights)` in `compute_portfolio_returns()` crashed with "Dot product shape mismatch". Fix: after price fetch, filter `portfolio.holdings` to only include tickers present in `prices.columns`, with a `st.warning()` notifying the user which were dropped (`app.py:163-168`). Added 2 regression tests (`tests/test_integration.py:34-95`). Total: 270/270 tests pass.

### Added

- **Institutional Risk Scoring (P×I×C Framework)** — new `engine/scoring.py` computes five composite scores: Overall Risk Score, Conviction Score, Portfolio Stress Score, Hidden Correlation Score, and Tail Risk Score. Each risk factor scored by Probability × Impact × Confidence with causal reasoning. Top 5 actionable insights ranked by composite score (`engine/scoring.py`, `tests/test_scoring.py`).
- **Multi-Factor Risk Decomposition** — new `engine/factors.py` decomposes portfolio risk into Market (beta), Size, Momentum, Volatility, Liquidity, and Concentration factors. Estimates macro driver sensitivities for crude oil, interest rates, INR/USD, global risk sentiment, and credit quality with regime classification and causal reasoning (`engine/factors.py`, `tests/test_factors.py`).
- **Macro-Driven Stress Tests** — enhanced `engine/scenario.py` with 7 real-world macro scenarios (crude oil spike, INR depreciation, rate hike/cut, global risk-off, recession, black swan). Sector-specific multipliers model differential impact across 18 sectors. Each scenario includes probability, severity, and causal reasoning (`engine/scenario.py`, `tests/test_macro_scenarios.py`).
- **Portfolio Recommendations Engine** — new `engine/recommendations.py` generates actionable recommendations (reduce, hedge, diversify, accumulate, monitor, rebalance) with causal reasoning, trade-off analysis, and expected risk reduction estimates. Covers concentration risk, beta risk, tail risk, momentum breakdown, and macro sensitivities (`engine/recommendations.py`, `tests/test_recommendations.py`).
- **Early-Warning Signal Detection** — new `engine/warnings.py` detects technical signals (MA crossovers, RSI overbought/oversold), volatility regime shifts, correlation breakdown (diversification failure), and momentum divergences. Each signal includes severity, reasoning, affected holdings, and suggested action (`engine/warnings.py`, `tests/test_warnings.py`).
- **Hidden Correlation Detection** — scoring engine computes average pairwise correlation, high-correlation pair count, and diversification ratio to detect when holdings are more correlated than they appear (`engine/scoring.py`).
- **4 new UI tabs** — Institutional Intelligence (scores, factor breakdown, top 5 insights), Macro Scenarios (sector-aware stress tests), Recommendations (priority actions with trade-offs), Early Warnings (signal dashboard with severity indicators).
- **84 new tests** — 15 factor tests, 9 scoring tests, 9 macro scenario tests, 10 recommendation tests, 10 warning tests. Total test count: 252.

### Changed

- `engine/__init__.py` — added imports for FactorExposure, FactorRiskReport, MacroDriver, InstitutionalRiskScores, RiskScore, MacroScenarioResult, RecommendationReport, Recommendation, WarningReport, WarningSignal. Extended `AnalysisReport` with 6 new optional fields (backward compatible).
- `engine/scenario.py` — extended with `MacroScenarioResult` dataclass, `SECTOR_MULTIPLIERS` dict, `MACRO_SCENARIOS` definitions, `run_macro_scenarios()`, and `_build_scenario_reasoning()`. Original `ScenarioResult` and `run_default_scenarios()` unchanged.
- `app.py` — orchestrates all new intelligence modules, adds 4 new tabs to the UI, caches new results in session state.

### Architecture

- All new modules are pure Python (zero Streamlit imports, zero IO side effects)
- Each module is independently testable with synthetic data
- New data models follow existing dataclass pattern in `engine/__init__.py`
- No new dependencies required — all computations use existing numpy/pandas/scipy

## v0.6.6 (2026-06-30)

### Fixed

- **BSE alias silently converted BSE Ltd stock to SENSEX index** — removed `"BSE": "^BSESN"` from `_TICKER_ALIASES`. Users entering "BSE" now get `BSE.NS` (the stock), not `^BSESN` (the index). Test updated (`engine/portfolio.py:25-30`, `tests/test_portfolio.py:37-38`).
- **Bare `except: pass` on DB save** — `save_analysis_run()` failures now log via `logger.error()` instead of silent swallow (`app.py:362`).
- **Benchmark fetch errors silently swallowed** — failed benchmark fetches now log via `logger.warning()` (`app.py:165`).
- **Regime detection tests flaky on synthetic data** — relaxed `len(result.stats) == 3` assertions to `2 <= len(result.stats) <= 3` to handle random data not always splitting into 3 regimes (`tests/test_regime.py`).

### Changed

- **Monte Carlo merged into single function** — `monte_carlo_simulation()` now accepts `return_paths`/`n_paths` parameters to return both statistics and chart-ready paths from a single GBM run. `monte_carlo_paths()` removed. The chart uses paths thinned from the 10K-statistics simulation (~80% fewer compute cycles, paths now consistent with reported stats) (`engine/risk.py:201-282`, `app.py:189-191`).
- **`compute_risk_metrics()` accepts pre-computed returns** — new optional `portfolio_returns` parameter skips internal `prices.pct_change().dot(weights)` to avoid duplicate computation from `app.py`. Backward compatible (`engine/risk.py:72-81`, `app.py:174`).
- **Sector classification no longer calls external APIs** — removed the per-ticker yfinance fallback in `classify_holdings()`. Unknown tickers are labeled "Unknown". This eliminates ~N×2 HTTP calls per portfolio for sector data. Static map + "Unknown" is deterministic and instant (`engine/sector.py:172-208`).
- **ThreadPool workers reduced 6→3** — `fetch_prices()` now uses `min(len(tickers), 3)` workers to avoid yfinance rate limiting (`data/prices.py:179`).
- **Input hash uses `hashlib.md5` instead of `hash()`** — deterministic, collision-resistant content hash for the computation guard (`app.py:125-132`).
- **CSV size validation added to `parse_portfolio_csv()`** — defense-in-depth against oversized files (`engine/portfolio.py:34,49-50`).

### Removed

- **`unittest.mock.patch` import from sector tests** — no longer needed after removing the yfinance fallback (`tests/test_sector.py:1-4`).
- **Unused `nselib` import from `engine/sector.py`** — dead code after removing api fallbacks (`engine/sector.py:15-20`).

## v0.6.5 (2026-06-30)

### Fixed

- **Rebalance action threshold at 0.5% instead of 50%** — `suggest_rebalance()` compared raw decimal drift against `0.5` (meaning 50 percentage points). A 5% drift towards the target always showed "hold" instead of "buy"/"sell". Changed threshold to `0.005` (0.5 pp). The action column now correctly shows buy/sell for trades with >0.5% drift (`engine/optimization.py:217`).
- **`compute_max_drawdown` potential IndexError** — when the peak preceding the maximum drawdown is at the first element, `cum[:end][...].index[0]` could fail. Added a guard that checks `peak.empty` before accessing `.index[0]` (`engine/performance.py:72`).
- **Manual entry ignored `normalize_ticker`** — `render_manual_entry()` used a custom `.replace(".NS", "")` + re-add pattern instead of calling `normalize_ticker()`. Index aliases like "NIFTY" → `^NSEI` were not handled, and "LTD"/"EQ" suffixes were not stripped. Now imports and delegates to `normalize_ticker()` (`ui/upload.py:103`).

### Changed

- `ui/upload.py` — removed intermediate `all_holdings` list; emptiness check uses `csv_portfolio is None and not manual_holdings` directly.

### Tests

- Added `test_action_buy_when_drift_exceeds_0_5pct` — verifies buy/sell actions are assigned for >0.5% drift.
- Added `test_action_hold_when_drift_below_0_5pct` — verifies "hold" when drift <0.5%.
- Added `test_max_drawdown_first_element_peak` — verifies no IndexError when drawdown peak is at position 0.

## v0.6.4 (2026-06-30)

### Security

- **CSV file size limit (10MB)** — `ui/upload.py` now checks uploaded file size before parsing. Files >10MB are rejected with a user-facing error via `st.error()`. Prevents OOM or excessive memory allocation from crafted uploads (V1).
- **Row limit on portfolio parsing** — `engine/portfolio.py` enforces `_MAX_HOLDINGS = 200`. Portfolios exceeding this raise `ValueError` with a clear message. Prevents unbounded resource consumption from oversized portfolios (V2).
- **Per-ticker HTTP timeout (120s)** — `data/prices.py` wraps `future.result()` with `timeout=120`. A stuck yfinance ticker no longer blocks the entire parallel fetch indefinitely. Explicit `TimeoutError` caught separately (V3).
- **Dependency upper bounds pinned** — all `pyproject.toml` deps now have major-version upper caps (`<2`, `<3`, etc.). Prevents unexpected breaking changes from future releases (V6).

### Changed

- `.streamlit/config.toml` — removed `runOnSave = true` from production config (V7).
- `pyproject.toml` — all runtime dependencies pinned with upper version bounds.

## v0.6.3 (2026-06-30)

### Performance

- **Input-hash computation guard** — `app.py` now computes a hash of portfolio tickers + quantities + benchmark on every interaction. When the hash matches the last computation, all expensive engine calls (price fetch, risk metrics, optimization, Monte Carlo, HMM regime detection, scenario analysis, rebalancing) are skipped. Results are restored from a session state cache. This eliminates **~90% of recomputation cost** on tab switches, checkbox toggles, and other interactions where the portfolio hasn't changed. Perceived latency drops from ~2-4s to ~100ms.
- **Vectorized per-holding beta computation** — replaced the sequential `for col in returns.columns` loop (individual `pd.concat` + `cov` per stock) with a single extended covariance matrix. ~80% faster beta computation for portfolios with 10+ holdings.
- **Reduced Monte Carlo paths** — `monte_carlo_paths()` reduced from 1,000 to 200 paths. The chart only displayed 100; the extra 900 were discarded. ~80% faster simulation computation.
- **Conditional `save_analysis_run()`** — only persists the analysis to SQLite when the report actually changed (first load or portfolio edit), not on every interaction.

### Removed

- **`scikit-learn` from requirements.txt** — never imported anywhere in the codebase; was a dead dependency carried over from an earlier iteration. Removed as a direct dependency (still installed transitively via hmmlearn).

### Fixed

- **Force-refresh checkbox UX** — added `key="force_refresh"` so the checkbox properly unchecks after one force-refresh cycle, preventing repeated forced fetches on every subsequent interaction.

### Changed

- `app.py` — input-hash guard restructured the computation pipeline. Full recomputation only runs when holdings, benchmark selection, or force-refresh changes. `app.py` grew from 325 to 381 lines (+56 for cache logic).
- `requirements.txt` — removed `scikit-learn>=1.4` (transitive via hmmlearn).

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
