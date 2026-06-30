# Changelog

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
