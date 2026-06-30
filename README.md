# NSE Portfolio Risk Scanner

A Streamlit app that analyzes your NSE portfolio for risk metrics: VaR, volatility, sector concentration, benchmark comparison, and more.

## Quick Start

```bash
pip install -e ".[dev,pdf]"
streamlit run app.py
```

For NSE-native data (recommended for Indian equities):

```bash
pip install -e ".[dev,pdf,nse]"
```

With ML-based regime detection:

```bash
pip install -e ".[dev,pdf,nse,ml]"
```

## Features

- **CSV Upload** — Import portfolios from Zerodha, Groww, Upstox
- **Risk Metrics** — Annualized volatility, VaR (95%/99%), CVaR, Sharpe/Sortino ratios, beta, max drawdown
- **Monte Carlo Projection** — Forward-looking 10,000-path simulation with probability-of-profit, confidence intervals, and VaR at horizon
- **Portfolio Optimization** — Hierarchical Risk Parity (HRP), Minimum Volatility, and Maximum Sharpe ratio optimizers with allocation pie chart
- **Market Regime Detection** — HMM-based regime classification (Bull/Neutral/Bear) with per-regime stats and transition matrix
- **Correlation Denoising** — Marchenko-Pastur eigenvalue clipping for cleaner correlation estimates
- **Sector Classification** — 160+ NSE stocks auto-classified via static mapping + nselib/yfinance fallback, concentration detection
- **Benchmark Comparison** — Performance vs Nifty 50, alpha, tracking error, information ratio
- **Interactive Charts** — Drawdown chart, benchmark overlay, sector treemap, correlation heatmap, regime scatter, Monte Carlo fan chart
- **Export** — Download position-level CSV or PDF report
- **NSE-Native Data** — Uses nselib for direct NSE data when available, falls back to yfinance
- **No Paid APIs** — All data sources are free (yfinance, nselib). Zero paid dependencies.
- **Accessibility** — Semantic headings, visible form labels, focus indicators, keyboard navigation, reduced motion support

## Project Structure

```
├── app.py                # Entry point (thin orchestration)
├── engine/               # Business logic (pure Python, zero UI deps)
│   ├── portfolio.py      # CSV parsing, validation, normalization
│   ├── risk.py           # VaR, volatility, beta, drawdown, Monte Carlo, correlation denoising
│   ├── sector.py         # NSE sector classification
│   ├── performance.py    # Sharpe, Sortino, CAGR
│   ├── benchmark.py      # Nifty 50 comparison
│   ├── optimization.py   # HRP, min-vol, max-Sharpe optimization
│   ├── regime.py         # HMM market regime detection (optional)
│   └── delivery.py       # NSE delivery analysis (optional)
├── ui/                   # Streamlit presentation layer
│   ├── upload.py         # File upload
│   ├── dashboard.py      # Metric cards, tabs, layout
│   ├── charts.py         # Plotly chart builders
│   └── export.py         # CSV/PDF report download
├── data/                 # Static assets & price fetching
│   ├── prices.py         # nselib + yfinance wrapper with multi-tier caching
│   ├── cache.py          # diskcache-backed L2 cache
│   └── sectors.yaml      # Ticker-to-sector mapping
├── storage/              # Persistence (SQLite)
│   ├── db.py             # Portfolio CRUD, analysis history, price cache
│   └── models.py         # Storage-layer data models & serialization
├── tests/                # 168 tests, 83% coverage
├── .github/workflows/    # CI (ruff check + pytest on push/PR)
└── .pre-commit-config.yaml
```

## Architecture Rules

1. **Engine never imports Streamlit** — all business logic is pure Python
2. **UI never computes math** — calls engine functions, gets results, renders
3. **app.py is thin** — reads CSV, computes risk, renders UI
4. **Multi-tier caching** — L1 (memory) → L2 (diskcache) → L3 (nselib/yfinance)

## Dependencies

| Dependency | Purpose | Optional? |
|-----------|---------|-----------|
| streamlit | Web UI framework | No |
| plotly | Interactive charts | No |
| yfinance | Yahoo Finance data (fallback) | No |
| numpy / pandas / scipy | Data processing & optimization | No |
| loguru | Structured logging | No |
| diskcache | Persistent price cache | No |
| nselib | Direct NSE India data | Yes (`[nse]`) |
| hmmlearn | HMM market regime detection | Yes (`[ml]`) |
| fpdf2 | PDF report export | Yes (`[pdf]`) |
| ruff / pre-commit | Linting & formatting | Dev only |
| pytest / vcrpy | Testing | Dev only |

## Development

```bash
pip install -e ".[dev,pdf,nse]"
ruff check .
ruff format .
pytest tests/
```

## Testing

168 tests across 10 test files, 83% overall coverage.

```bash
pytest tests/ -v                    # run all tests
pytest tests/ --cov=engine          # engine coverage only
pytest tests/test_db.py -v          # run a single test file
```

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_portfolio.py` | 36 | CSV parsing, Indian format, BOM, malformed rows |
| `test_risk.py` | 22 | VaR, volatility, drawdown, stock risk, edge cases |
| `test_prices.py` | 11 | Retry logic, parallel fetch, backoff, cooldown |
| `test_sector.py` | 13 | Classification, yfinance fallback, HHI, custom maps |
| `test_cache.py` | 11 | Round-trip, TTL expiry, clear, has, disabled cache |
| `test_models.py` | 10 | Serialization round-trips, edge cases |
| `test_db.py` | 17 | Schema, CRUD, price cache upsert/clear/stale |
| `test_integration.py` | 7 | Full pipeline with mock network, sector order |
| `test_benchmark.py` | 6 | Benchmark comparison |
| `test_performance.py` | 24 | Sharpe, Sortino, CAGR, max drawdown |
