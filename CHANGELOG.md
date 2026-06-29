# Changelog

## v0.2.0 (2026-06-29)

### Added

- **Risk Metrics Engine** — VaR (95%/99%), CVaR, annualized volatility, Sharpe ratio, Sortino ratio, CAGR, max drawdown with start/end dates, beta, correlation to benchmark
- **Sector Classification** — 160+ NSE stocks mapped across 18 sectors (Banking, IT, FMCG, Pharma, Automobile, Power, Oil & Gas, etc.)
- **Sector Concentration Analysis** — Herfindahl-Hirschman Index, diversification score, automatic concentrated-sector detection (>20% threshold)
- **Benchmark Comparison** — Portfolio vs Nifty 50, Bank Nifty, Nifty IT, Nifty Midcap 100, Nifty Smallcap 250. Alpha, tracking error, information ratio, monthly outperformance count
- **Multi-Broker CSV Parsing** — Automatic column detection for Zerodha, Groww, Upstox export formats. Indian number format support (₹, commas)
- **Interactive UI** — Plotly charts: sector treemap, drawdown chart, benchmark overlay, correlation heatmap, volatility gauge
- **Price Caching** — L1 (in-memory LRU) → L2 (SQLite) → L3 (yfinance) multi-tier cache. 24-hour TTL, force-refresh button
- **Analysis History** — SQLite persistence for saved portfolios and analysis runs
- **Portfolio Management** — Save/load/delete portfolios across sessions, inline data editor for holdings
- **Export** — CSV download with position-level risk metrics
- **Unit Tests** — 39 tests across risk computation, performance, portfolio parsing, sector classification, and benchmark comparison

### Architecture

- Pure separation: `engine/` (zero Streamlit imports), `ui/` (zero business logic), `app.py` (thin orchestration)
- All risk computation uses numpy/scipy — no external ML dependencies
