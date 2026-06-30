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

## Features

- **CSV Upload** — Import portfolios from Zerodha, Groww, Upstox
- **Risk Metrics** — Annualized volatility, VaR (95%), CVaR, Sharpe/Sortino ratios, beta, max drawdown
- **Sector Classification** — 160+ NSE stocks auto-classified via static mapping + nselib/yfinance fallback, concentration detection
- **Benchmark Comparison** — Performance vs Nifty 50, alpha, tracking error, information ratio
- **Interactive Charts** — Drawdown chart, benchmark overlay, sector treemap, correlation heatmap
- **Export** — Download position-level CSV or PDF report
- **NSE-Native Data** — Uses nselib for direct NSE data when available, falls back to yfinance

## Project Structure

```
├── app.py                # Entry point (thin orchestration)
├── engine/               # Business logic (pure Python, zero UI deps)
│   ├── portfolio.py      # CSV parsing, validation, normalization
│   ├── risk.py           # VaR, volatility, beta, drawdown
│   ├── sector.py         # NSE sector classification
│   ├── performance.py    # Sharpe, Sortino, CAGR
│   └── benchmark.py      # Nifty 50 comparison
├── ui/                   # Streamlit presentation layer
│   ├── upload.py         # File upload
│   ├── dashboard.py      # Metric cards, tabs, layout
│   ├── charts.py         # Plotly chart builders
│   └── export.py         # CSV/PDF report download
├── data/                 # Static assets & price fetching
│   ├── prices.py         # nselib + yfinance wrapper with multi-tier caching
│   ├── cache.py          # diskcache-backed L2 cache
│   └── sectors.yaml      # Ticker-to-sector mapping
├── storage/              # Persistence
├── tests/                # 62 tests across all modules
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
| numpy / pandas | Data processing | No |
| loguru | Structured logging | No |
| diskcache | Persistent price cache | No |
| nselib | Direct NSE India data | Yes (`[nse]`) |
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
