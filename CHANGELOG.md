# Changelog

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
