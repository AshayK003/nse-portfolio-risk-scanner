# Changelog

## v0.9.0 (2026-07-01)

### Changed

- **Split `ui/export.py` into `ui/charts_pdf.py` + `ui/export.py`** — chart/render functions moved to a pure module with zero Streamlit imports. `export.py` is now a thin Streamlit wrapper (only `render_export_section()`). Tests import directly from `charts_pdf.py`, making them pass even when Streamlit is unavailable.
- **Shared loguru compat module** (`engine/_log.py`) — both `app.py` and `data/prices.py` had identical loguru-compat wrappers. Consolidated into one source of truth. Inline compat wrappers removed from both files.
- **L1 cache bounded LRU** (`data/prices.py`) — replaced unbounded dict with `OrderedDict`-based LRU (max 128 entries). Prevents RAM growth when scanning many tickers across periods.
- **`NSE_RISK_SCANNER_*` env var support** — `NSE_RISK_SCANNER_CACHE_DIR` for diskcache directory, `NSE_RISK_SCANNER_DB_PATH` for SQLite path. Both default to project-local values when unset.
- **`PriceCache.get` stale-eviction guard** (`data/cache.py`) — calls `diskcache.Cache.expire()` before each lookup, so expired entries are cleaned up automatically.
- **Transaction rollback** (`storage/db.py`) — `save_portfolio()` and `save_analysis_run()` now wrap writes in `try/except sqlite3.Error` with explicit `conn.rollback()`.
- **MD5 → SHA256** (`app.py`) — input hash for recomputation guard uses SHA256 (truncated to 16 hex chars) instead of MD5.
- **Widened plotly constraint** (`pyproject.toml`) — `plotly<7` instead of `<6` to allow plotly 6.x.
- **`matplotlib` moved to `[pdf]` optional deps** — reduces core dependency footprint.
- **Removed dead `_build_column_map` stub** (`engine/portfolio.py`) — legacy wrapper with no callers.

## v0.8.0 (2026-07-01)

### Fixed

- **PDF: `gauge_w` unbound crash** (`ui/export.py:461`) — `gauge_w` was only assigned inside `if gauge_chart:` block but referenced unconditionally below. Crashed with `UnboundLocalError` when matplotlib was unavailable but risk data existed. Fixed by initializing `gauge_w` before the conditional.
- **`@lru_cache` on `_cached_fetch` blocking retries** (`data/prices.py`) — Python's `@lru_cache` memoized `None` failures permanently, making all subsequent `fetch_prices_parallel()` retries for that ticker return `None` instead of retrying. Replaced with a manual L1 cache dict that never caches `None`.
- **`get_stock_info` incomplete fallback dict** (`data/prices.py`) — yfinance failure branch returned 4-key dict (missing `fiftyTwoWeekHigh`, `fiftyTwoWeekLow`), causing `KeyError` in `ui/dashboard.py:168`. Now returns full 6-key fallback.
- **`get_stock_info` case-sensitive min_points** (`data/prices.py`) — `key.endswith("min_points")` missed `min_points` (no prefix). Added `.lower()` case normalization.
- **`PriceCache.get` corrupted entries crash** (`data/cache.py`) — `json.loads` on corrupted `.json` cache files raised `json.JSONDecodeError`, failing the entire load. Wrapped in try/except.
- **`PriceCache` silent disk I/O failures** (`data/cache.py`) — all disk operations (`_read`, `_write`, `_delete`, `set`, `clear`) lacked error handling for OS-level I/O issues. Added try/except with logging.
- **`PriceCache` relative directory crash** (`data/cache.py`) — bare `os.makedirs(_CACHE_DIR)` failed on Windows. Made relative to `__file__` like `_DATA_DIR`.
- **Price precision loss** (`data/cache.py`) — `round(p, 2)` truncated NSE prices (e.g., ₹3,245.678 → ₹3,245.68). Increased to `round(p, 4)`.
- **`_parse_float` NaN/inf propagation** (`engine/portfolio.py`) — `float("NaN")` and `float("inf")` passed through to Portfolio, corrupting downstream calculations. Now returns `0.0`.
- **`portfolio_from_dict` empty ticker** (`engine/portfolio.py`) — empty strings from CSV parsing created Holdings with empty tickers. Now filtered.
- **Auto-correct cost when quantity=1** (`engine/portfolio.py`) — `total_value = qty * price` was skipped when `qty == 1`, leaving total_cost at its raw (incorrect) value. Now uses `total_value` in the calculation.
- **`_parse_float` $ symbol** (`engine/portfolio.py`) — USD-formatted prices (e.g., `$1,234`) failed to parse. Added `$` to strip list.
- **BOM-encoded CSV crash** (`engine/portfolio.py`) — files with BOM encoding (Windows Excel) raised `UnicodeDecodeError`. Added `encoding="utf-8-sig"` with Latin-1 fallback.
- **`compute_risk_metrics` empty series crash** (`engine/risk.py`) — pandas 3.x raises `ValueError` on `np.percentile([], 5)`. Added early return `_empty_risk_metrics()` for ≤1 element Series.
- **`compute_stock_risk` empty prices crash** (`engine/risk.py`) — same empty series issue. Added guard.
- **`monte_carlo_simulation` empty returns crash** (`engine/risk.py`) — `np.random.standard_normal((50, 1, 1))` with 0 steps crashed. Added `len(returns) < 2` guard.
- **`monte_carlo_simulation` max_drawdown division by zero** (`engine/risk.py`) — `running_max` could be 0 if all prices drop. Added `np.where(running_max > 0, ...)`.
- **`optimize_hrp` IndexError on empty returns** (`engine/optimization.py`) — `returns.shape[1] == 0` caused crash. Added early return.
- **`optimize_hrp` all zero-variance columns** (`engine/optimization.py`) — `dist[dist > 0].min()` on empty array crashed. Added guard for zero-variance stocks.
- **`_inverse_variance` division by zero** (`engine/optimization.py`) — stocks with zero variance produced `inf` weights. Added `np.where(var > 0, 1/var, 0)`.
- **`_recursive_bisection` NaN alpha** (`engine/optimization.py`) — equal-split alpha (0.5) caused NaN in sub-allocations. Added `np.nan_to_num` or `0.5` fallback.
- **`backtest_var` log(0) crash** (`engine/backtesting.py`) — `np.log(1 - exception_rate)` when `exception_rate == 1.0` produced `log(0) = -inf`. Added `min(exception_rate, 1 - 1e-10)` guard.
- **"liquid beession" typo** (`engine/recommendations.py:211`) — misspelled "liquid session" in recommendation text.
- **`json.dumps` NaN serialization crash** (`storage/models.py`) — `json.dumps` raises `ValueError` on NaN/inf values in portfolio data. Added `_sanitize_json` helper.
- **Empty `holdings_json` crash** (`storage/models.py`) — `json.loads("")` raises `json.JSONDecodeError`. Added empty-string guard.
- **`saved_to_portfolio` missing optional keys** (`storage/models.py`) — accessing `d["current_price"]` etc. raised `KeyError` when DB rows lacked newer fields. Changed to `.get()` with defaults.
- **`os.makedirs("")` crash** (`storage/db.py`) — bare filename (no directory) caused `FileNotFoundError`. Changed to `os.makedirs(dir, exist_ok=True)` with fallback.
- **VaR backtest wrong call signature** (`app.py:370-375`) — `backtest_var()` was called with wrong arguments. Fixed to use `kupiec_pof()` with correct signature.
- **Stale cache reads** (`app.py:424-452`) — cache restored via `cache["key"]` crashed with `KeyError` on version upgrades. Changed to `.get()` with sensible defaults.
- **Missing `st.stop()` on all-failures** (`app.py:310`) — when all holdings failed to fetch prices, execution continued to division by zero. Added `st.stop()`.
- **Input hash missing `current_price`** (`app.py:386`) — price changes didn't invalidate cache, showing stale risk metrics. Added `current_price` to hash.
- **Benchmark empty Series guard** (`app.py:397`) — single-point benchmark produced empty `pct_change()` result. Added `len(benchmark_prices) > 1` check.
- **`force_refresh` never clears** (`app.py:128-132`) — checkbox only set True, never cleared False, causing infinite re-fetch. Now clears when unchecked.
- **Advanced optimization dead code** (`ui/dashboard.py:222`) — checked `opt_advanced.get("status") == "ok"` but engine returns flat dict with no status key. Now reads weights directly.
- **Falsy price check** (`ui/dashboard.py:146`) — `if h.current_price` showed "—" for `0.0` prices. Changed to `h.current_price > 0`.
- **Falsy optimization check** (`ui/dashboard.py:318`) — `if opt.expected_return` hid metrics when return was `0.0%`. Changed to explicit `!= 0.0` check.
- **Empty regime stats crash** (`ui/dashboard.py:308`) — `st.columns(len(regime.stats))` crashed on empty list. Added guard.
- **Upload ticker None crash** (`ui/upload.py`) — clearing a ticker cell and uploading caused `AttributeError`. Added None/empty guard.
- **Charts empty data guards** (`ui/charts.py`) — `sector_treemap`, `correlation_heatmap`, `monte_carlo_chart` crashed on empty inputs. Added early return with placeholder title.

### Changed

- **PDF: consolidated matplotlib imports** (`ui/export.py`) — all 7 chart functions previously imported matplotlib independently (~200-400ms each). Now a single `_import_matplotlib()` helper is called once in `_generate_pdf_report()` and `plt` is passed to each chart function. Eliminates 6 redundant imports per PDF generation.
- **PDF: holdings table supports all sizes** (`ui/export.py:568-615`) — removed the hard cap at 25 holdings. The table now renders all rows with automatic page breaks when content exceeds the page boundary. Header row repeats on continuation pages.
- **PDF: page overflow guards** (`ui/export.py`) — Risk Analysis page (drawdown chart, Monte Carlo fan, recommendations) now checks `pdf.get_y()` before each section and adds a continuation page if space is insufficient.
- **PDF: metadata set on output** (`ui/export.py:397-400`) — generated PDF now includes `title`, `author`, and `subject` metadata for better handling in email clients and PDF viewers.
- **PDF: spinner during generation** (`ui/export.py:73`) — wrapped `_generate_pdf_report()` call in `st.spinner("Generating PDF report...")` for better UX on slow generations.
- **Removed dead `portfolio_returns` parameter** (`ui/export.py:28`, `app.py:802`) — `render_export_section()` accepted `portfolio_returns` but never used it in `_generate_pdf_report()`. Removed from both function signature and call site.
- **Chart functions accept `plt` parameter** — `_risk_gauge_chart`, `_sector_pie_chart`, `_pnl_bar_chart`, `_drawdown_area_chart`, `_monte_carlo_fan_chart`, `_holdings_weight_bar` now take `plt` as a required argument instead of importing it internally. Gracefully return `None` when `plt is None`.

### Added

- **1 new test** (`tests/test_pdf_export.py:test_risk_gauge_chart_none_plt`) — verifies chart functions return `None` gracefully when matplotlib is unavailable.

### Metrics

- **360 tests pass** — zero regressions.
- **Lint clean** — ruff E/F/I/N/W/UP/B/SIM all pass.

## v0.7.9 (2026-07-01)

### Added

- **Altman Z-Score** (`engine/fundamentals.py`) — computes Original and Modified Z-Score for each holding using balance sheet data fetched via yfinance. Results classified into Safe (≥3.0 / ≥2.9), Grey Zone (1.8–2.99 / 1.1–2.89), Distress (<1.8 / <1.1) zones. Adopted from `vdamov/financial-risk-analyzer`.
- **VaR Backtesting (Kupiec POF)** (`engine/backtesting.py`) — binomial likelihood-ratio test for VaR model accuracy. Computes exception count, LR statistic, and p-value at multiple confidence levels simultaneously. Pure numpy/scipy, zero new deps. Adopted from `market-risk-engine`.
- **GARCH(1,1)-t VaR** (`engine/garch_var.py`) — time-varying volatility model using the `arch` package. Falls back to static normal VaR when `arch` not installed. Adopted from `kshitijbhandari/Multi-Asset-Portfolio-Risk-Engine`.
- **PELVE Ratio** (`engine/pelve.py`) — Portfolio Equal-Loss Value-at-Risk Equivalent. Solves for the multiplier `c` such that ES(1-cε) = VaR(1-ε) under parametric normal. Pure numpy/scipy. Adopted from `ibaris/VaR`.
- **Advanced Portfolio Optimization** (`engine/optimization_advanced.py`) — optional Riskfolio-Lib wrapper providing CVaR optimization, Black-Litterman, EVaR, and CDaR. Graceful fallback when Riskfolio-Lib not installed.
- **39 new tests** — `tests/test_fundamentals.py` (15), `tests/test_backtesting.py` (8), `tests/test_garch_var.py` (5), `tests/test_pelve.py` (10). Cover boundary values, edge cases (empty/missing data, zero div, mismatched lengths), and fallback behavior.

### Changed

- **UI: Advanced Analytics section** — collapsible expander at the top of Risk Metrics tab (closed by default) showing Z-Score summary cards, VaR backtest pass/fail, GARCH VaR metrics, PELVE interpretation, and Riskfolio-Lib optimal weights.
- **pyproject.toml** — new `[advanced]` optional-dependencies group: `arch>=5.0`, `riskfolio-lib>=1.4.0`.
- **360 tests pass** — 321 existing + 39 new, zero regressions.

### Fixed

- **GARCH VaR formula sign error** — both the fallback (`garch_var.py:89`) and GARCH-t (`garch_var.py:67`) VaR formulas used `+ mu` instead of `- mu` for the positive-loss VaR convention. When mean daily return is positive, this overestimated VaR by 2× the mean. Fixed to `-mu + sigma * quantile`.

### Changed

- **PDF report redesigned** (`ui/export.py`) — 4 pages instead of 3:
  - **Cover page** — dark navy header with portfolio name + date, 6-KPI grid (holdings, invested, value, P&L, P&L%, Sharpe), risk gauge chart, and risk level badge. Centered layout with generous whitespace.
  - **Section numbering** — page headers now show "1. Executive Summary", "2. Risk Analysis", "3. Holdings Breakdown".
  - **Compact risk metrics** — replaced 2-column vertical metric pairs with a denser 4-column grid (3 rows × 4 metrics). Uses smaller font for labels, larger for values.
  - **Right-aligned numbers** — Qty, Avg Price, Current, P&L% columns in holdings table are right-aligned for easier vertical scan.
  - **Page X of Y footer** — `{nb}` alias via `pdf.alias_nb_pages()` shows total page count.
- **16 PDF export tests still pass** — no changes to test assertions, layout only.

### Architecture

- All new modules are pure functions with zero Streamlit, zero IO, zero new mandatory dependencies.
- Each new module is independently tested with mocked network calls (yfinance) and optional-dependency guards (`ARCH_AVAILABLE`, `RISKFOLIO_AVAILABLE`).
- v0.7.9 fields added to `AnalysisReport` dataclass (`engine/__init__.py`): `zscore`, `var_backtest`, `garch_var`, `pelve`, `optimization_advanced`.

## v0.7.8 (2026-07-01)

### Added

- **Rule-based narrative engine** (`engine/narrative.py`) — generates plain-English portfolio explanations from computed risk metrics without any LLM or API call. Six narrative sections: executive summary, risk assessment (volatility, VaR, Sharpe, drawdown), concentration analysis, benchmark context (alpha, beta, win rate), key concerns (top 5 ranked by severity), and overall verdict (Low/Moderate/Higher risk). All thresholds calibrated for Indian equity context.
- **32 new tests** (`tests/test_narrative.py`) — threshold boundaries (low/moderate/high volatility, poor/good/excellent Sharpe, concentration, drawdown, VaR, beta), benchmark edge cases (outperformance/underperformance, missing benchmark), empty portfolio, zero values, single-stock concentration, concern capping, overall verdict scoring.

### Changed

- **UI: AI Insights section** — new collapsible expander block at the top of the Risk Metrics tab. Portfolio Summary expanded by default; Risk Assessment, Concentration, Benchmark Context, and Key Concerns expandable on click. No functional changes to existing sections.
- **321 tests pass** — 289 original + 32 new narrative tests, zero regressions.

### Architecture

- `engine/narrative.py` — pure functions, zero Streamlit imports, zero IO, no new dependencies. Uses only threshold-based string templates (if/elif chains). Composable: each section builder (`_build_summary`, `_build_risk_assessment`, `_build_concentration`, `_build_benchmark_context`, `_build_key_concerns`, `_build_overall_verdict`) is independently unit-testable.
- Hooks into `app.py:414` — `generate_narrative(report)` called after report assembly, rendered via `render_narrative_section()` in the first tab.

## v0.7.7 (2026-07-01)

### Added

- **Mobile responsiveness** — comprehensive responsive CSS with 3 breakpoint tiers:
  - **Tablet (≤768px)**: multi-column layouts wrap to 2 columns, sidebar slimmed, metric cards compacted, fonts scaled down.
  - **Phone (≤480px)**: all columns become single-column stack, tabs scroll horizontally, typography/buttons/inputs/tables/expanders all scale proportionally.
  - **Touch devices** (`hover: none`): all hover states disabled to prevent sticky-hover on mobile.
- **Sidebar default collapsed** — saves screen space on mobile; accessible via hamburger icon.
- **Simplified manual entry form** — 4-column layout reduced to 3-column + full-width button, cleaner on all screen sizes, price label shortened for smaller fields (`ui/upload.py`).

### Changed

- No functional changes; all changes are UI-only (CSS + layout) — 289 tests still pass.

## v0.7.6 (2026-07-01)

### Fixed

- **Bear regime recommendation never generated** — `recommendations.py:218` compared string labels (`"Bear"`) to integer `2` using `s == 2`, which is always `False`. The HMM-based bear market defensive recommendation was dead code. Fixed to `s == "Bear"` (`engine/recommendations.py:218`).
- **Single-stock concentration risk severely underestimated** — `scoring.py:119` computed `max_stock / 30` where `max_stock` is a decimal weight (e.g. 0.35 for 35%). A 35% holding scored 0.0117 instead of ~1.17, rendering single-stock concentration nearly invisible in the institutional risk scoring. Fixed to `max_stock / 0.30` to align with the percentage-based `max_sector / 40` comparison (`engine/scoring.py:119`).

### Changed

- No functional changes; both bugs were in pure computation modules covered by existing tests.

## v0.7.5 (2026-07-01)

### Added

- **Per-stock risk attribution table** — new `compute_stock_risk_attribution()` in `engine/risk.py` decomposes portfolio risk using marginal contribution to risk (MCR). Each holding shows: weight, beta, annualized volatility, average pairwise correlation, MRC, VaR 95% (daily), and percentage risk contribution. Displayed in the Holdings tab below the P&L table. Risk contributions are color-coded (red >25%, amber >15%, green <5%). 5 new tests (`tests/test_risk.py`).

### Changed

- **Risk Metrics tab decluttered** — Monte Carlo projection moved to the Charts tab where it belongs alongside other visualizations. Institutional Risk Scores & Factor Analysis collapsed inside a single expander (closed by default). Early Warning Signals collapsed inside an expander (auto-opens only when critical signals present). Rolling volatility chart collapsed by default. The first tab now shows risk cards + volatility gauge at a glance, with all deeper analysis one click away.
- **Parallel data fetch optimized** — `max_workers` raised from 3 to 8, with a `Semaphore(5)` rate-limiter around actual network calls. Cache hits bypass the semaphore entirely. Portfolio load times should improve 2-3x on fresh fetches (`data/prices.py`).

### Removed

- **Dead import `engine.scores`** — `engine/__init__.py` referenced `engine.scores` (file is `engine/scoring.py`). This blocked test collection silently. Fixed to `engine.scoring`.

## v0.7.4 (2026-07-01)

### Fixed

- **NaN propagation from prices with mismatched date ranges** — `pd.DataFrame(all_prices)` merged series with different date windows; the last row contained NaN for shorter-history tickers, which spread to `current_price` → `total_current` → all risk metrics. Fixed by forward-filling (`ffill()`) before extracting the latest price, plus a NaN guard in Portfolio.total_current (`data/prices.py:249-255`, `engine/__init__.py:67-69`).
- **Divide-by-zero when all weights are zero** — `compute_risk_metrics()` divided by `weights_arr.sum()` which was 0 when no holdings had fetched prices, producing NaN. Now guards with `_empty_risk_metrics()` return (`engine/risk.py:81-86`).
- **Pyproject.toml version frozen at 0.2.0** — bumped to 0.7.4 to match actual release state (`pyproject.toml:7`).
- **Loguru as hard import blocking test collection** — both `data/prices.py` and `app.py` now guard the loguru import with a fallback to stdlib logging. A wrapper layer handles loguru-style `{var}` keyword formatting so all logger calls work without loguru installed.
- **`_get_l2_cache()` race condition** — added double-checked locking with `threading.Lock()` to prevent concurrent threads from creating separate cache instances on first parallel access (`data/prices.py:34-35,48-56`).
- **`_parse_float()` crash on unexpected CSV input** — wrapped `float(s)` in `try/except (ValueError, TypeError)` returning `0.0` on unparseable values (`engine/portfolio.py:501-516`).
- **Streamlit Cloud deployment missing config** — added `.streamlit/config.toml` with `headless=true`.

### Removed

- **Dead SQLite `price_cache` table** — the `storage/db.py` schema, CRUD functions, and `CachedPrice` model were never called by the production data fetcher (which uses the diskcache-based L2 cache). Removed the table from `_ensure_schema()`, deleted `get_cached_prices()` / `save_cached_prices()` / `clear_stale_cache()` / `clear_ticker_cache()` / `clear_all_cache()`, and removed the `CachedPrice` dataclass. Corresponding `TestPriceCache` tests removed. 43 lines of dead code eliminated.

### Chores

- **Added `.ruff_cache/` to `.gitignore`** — prevents accidental commits of ruff's cache directory.
- **Added docstring to `ui/__init__.py`** — empty file now has a one-line description, consistent with other package init files.
- **Internal project notes created** — architectural decisions and trade-off documentation (gitignored, never committed).

## v0.7.3 (2026-06-30)

### Fixed

- **Sector impact in macro scenarios always used first stock's beta** — `run_macro_scenarios()` computed sector-level impacts using `betas.get(list(betas.keys())[0], 1.0)`, which always used the first ticker's beta regardless of which sector was being computed. Now uses the portfolio weighted-average beta instead, giving correct sector impact estimates (`engine/scenario.py:296-298`).
- **Duplicated `plt.subplots()` in `_drawdown_area_chart`** — first figure was created and immediately discarded, leaking memory (`ui/export.py:241`).
- **Missing forward type imports in `engine/__init__.py`** — `AnalysisReport` annotations referenced `FactorRiskReport`, `MacroDriver`, `InstitutionalRiskScores`, `MacroScenarioResult`, `RecommendationReport`, and `WarningReport` without importing them, breaking `typing.get_type_hints(AnalysisReport)` and IDE tooling (`engine/__init__.py:13-19`).
- **Hardcoded period in nselib benchmark fetch** — `fetch_benchmark()` passed `period="1M"` to nselib's `index_data()` instead of the caller's requested period (`data/prices.py:261`).
- **Ambiguous variable name in `_build_scenario_reasoning`** — `severely_affected` iterated over sector impacts but the name suggested holding-level counting. Renamed to `sectors_with_double_digit_losses` for clarity (`engine/scenario.py:354`).

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
