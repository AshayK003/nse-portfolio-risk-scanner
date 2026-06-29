# NSE Portfolio Risk Scanner

A Streamlit app that analyzes your NSE portfolio for risk metrics: VaR, volatility, sector concentration, benchmark comparison, and more.

## Quick Start

```bash
pip install -e .
streamlit run app.py
```

## Features

- **CSV Upload** — Import portfolios from Zerodha, Groww, Upstox
- **Risk Metrics** — Annualized volatility, VaR (95%), CVaR, Sharpe/Sortino ratios, beta, max drawdown
- **Sector Classification** — 100+ NSE stocks auto-classified, concentration detection
- **Benchmark Comparison** — Performance vs Nifty 50, alpha, tracking error, information ratio
- **Interactive Charts** — Drawdown chart, benchmark overlay, sector treemap, correlation heatmap
- **Export** — Download position-level CSV report

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
│   └── export.py         # CSV report download
├── data/                 # Static assets & price fetching
│   ├── prices.py         # yfinance wrapper with caching
│   └── sectors.yaml      # Ticker-to-sector mapping
├── storage/              # Persistence (v1.1)
├── tests/                # 39 tests across all modules
└── .streamlit/           # Streamlit config
```

## Architecture Rules

1. **Engine never imports Streamlit** — all business logic is pure Python
2. **UI never computes math** — calls engine functions, gets results, renders
3. **app.py is thin** — reads CSV → computes risk → renders UI
