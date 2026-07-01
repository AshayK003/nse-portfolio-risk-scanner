<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/NSE%20Portfolio%20Risk%20Scanner-v0.7.6-blue?style=flat-square&labelColor=1a1a2e">
    <img alt="NSE Portfolio Risk Scanner" src="https://img.shields.io/badge/NSE%20Portfolio%20Risk%20Scanner-v0.7.6-blue?style=flat-square">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/AshayK003/nse-portfolio-risk-scanner/actions"><img src="https://img.shields.io/github/actions/workflow/status/AshayK003/nse-portfolio-risk-scanner/ci.yml?branch=master&style=flat-square&label=CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square"></a>
  <a href="https://streamlit.io"><img src="https://img.shields.io/badge/built%20with-Streamlit-ff4b4b?style=flat-square"></a>
  <img src="https://img.shields.io/badge/tests-289%20passing-brightgreen?style=flat-square">
</p>

---

**NSE Portfolio Risk Scanner** is a Streamlit application that analyzes Indian equity portfolios for institutional-grade risk metrics — VaR, volatility, sector concentration, benchmark comparison, factor decomposition, Monte Carlo simulation, and more.

Ships with a clean three-layer architecture, zero paid API dependencies, and 289 tests.

## Features

| Category | What you get |
|----------|-------------|
| **Risk Metrics** | Annualized volatility, VaR (95%/99%), CVaR, Sharpe/Sortino ratios, beta, max drawdown with peak-to-trough dates |
| **Monte Carlo** | 10,000-path GBM simulation — probability of profit, confidence intervals, horizon VaR |
| **Optimization** | Hierarchical Risk Parity (HRP), Minimum Volatility, Maximum Sharpe — with weight caps and cash-instrument exclusion |
| **Regime Detection** | HMM-based bull/neutral/bear classification with transition matrix and per-regime stats. Falls back to quantile heuristic when hmmlearn not installed |
| **Factor Decomposition** | Market, size, momentum, volatility, liquidity, and concentration factor exposures. Macro sensitivity estimates for crude, rates, INR/USD, and risk sentiment |
| **Sector Analysis** | 160+ NSE stocks pre-mapped across 18 sectors. Concentration detection (HHI), diversification scoring |
| **Benchmark Comparison** | Nifty 50 / Bank Nifty / Sensex / sectoral indices. Alpha, tracking error, information ratio, monthly outperformance |
| **Correlation Denoising** | Marchenko-Pastur eigenvalue clipping for cleaner covariance estimates |
| **Stress Testing** | 5 basic scenarios + 7 macro scenarios with sector-specific multipliers and causal reasoning |
| **Institutional Scoring** | P×I×C framework — Overall Risk, Conviction, Stress, Hidden Correlation, and Tail Risk scores |
| **Early Warnings** | MA crossover, RSI extremes, volatility regime shifts, correlation breakdowns, momentum divergences |
| **Recommendations** | Actionable suggestions (reduce/hedge/diversify/accumulate) with expected risk reduction and trade-off analysis |
| **Export** | CSV with position-level risk data + PDF report with charts |
| **10+ Broker Formats** | Zerodha, Groww, Upstox, Angel One, ICICI Direct, Kotak, HDFC — Indian number format, auto column detection |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  app.py  (thin orchestration, ~200 imperative lines) │
├─────────────────────────────────────────────────────┤
│                    ┌──────────────────┐              │
│                    │    engine/        │              │
│                    │  pure functions   │              │
│                    │  zero Streamlit   │              │
│                    │  zero I/O         │              │
│                    └──────────────────┘              │
│                    ┌──────────────────┐              │
│                    │    data/          │              │
│                    │  price fetching   │              │
│                    │  3-tier cache     │              │
│                    └──────────────────┘              │
│                    ┌──────────────────┐              │
│                    │    ui/            │              │
│                    │  Streamlit only   │              │
│                    │  no business logic│              │
│                    └──────────────────┘              │
│                    ┌──────────────────┐              │
│                    │    storage/       │              │
│                    │  SQLite history   │              │
│                    └──────────────────┘              │
└─────────────────────────────────────────────────────┘
```

**The rules are strict:**
- `engine/` never imports Streamlit. Every function is pure — inputs in, dataclass out.
- `ui/` never computes math. It calls engine functions and renders the results.
- `app.py` is a thin orchestrator: read CSV → compute → render.
- Every intelligence module is independently guarded — one failure doesn't kill the rest.

### Directory Layout

```
├── app.py                    # Entry point
├── engine/
│   ├── __init__.py           # Data models (dataclasses only)
│   ├── portfolio.py          # CSV parsing, validation, ticker normalization
│   ├── risk.py               # VaR, CVaR, volatility, beta, drawdown, Monte Carlo, denoising
│   ├── performance.py        # Returns, CAGR, win rate, holding P&L
│   ├── benchmark.py          # Benchmark comparison (alpha, tracking error, IR)
│   ├── sector.py             # Sector classification + concentration (HHI)
│   ├── optimization.py       # HRP, min-vol, max-Sharpe, rebalancing
│   ├── regime.py             # HMM regime detection (optional hmmlearn)
│   ├── scenario.py           # Basic + macro stress tests
│   ├── factors.py            # Factor decomposition + macro sensitivities
│   ├── scoring.py            # Institutional risk scoring (P×I×C)
│   ├── recommendations.py    # Portfolio recommendations engine
│   ├── warnings.py           # Early warning signal detection
│   └── delivery.py           # NSE delivery analysis (optional nselib)
├── ui/
│   ├── dashboard.py          # Metric cards, tabs, layout
│   ├── charts.py             # Plotly chart builders
│   ├── upload.py             # CSV upload + manual entry
│   ├── export.py             # CSV/PDF export
│   ├── styles.py             # Dark theme CSS
│   └── icons.py              # SVG icon helpers
├── data/
│   ├── prices.py             # Price fetching (nselib + yfinance, 3-tier cache)
│   └── cache.py              # diskcache-backed L2
├── storage/
│   ├── db.py                 # SQLite CRUD
│   └── models.py             # Serialization
├── tests/                    # 289 tests
├── .github/workflows/ci.yml  # CI pipeline
└── .pre-commit-config.yaml   # Ruff + pre-commit hooks
```

## Quick Start

```bash
# Clone and enter the project
git clone https://github.com/AshayK003/nse-portfolio-risk-scanner.git
cd nse-portfolio-risk-scanner

# Create a virtual environment
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# Install (pick the extras you need)
pip install -e ".[dev,pdf]"           # Minimal — yfinance only
pip install -e ".[dev,pdf,nse]"       # + nselib for official NSE data (recommended)
pip install -e ".[dev,pdf,nse,ml]"    # + hmmlearn for ML regime detection

# Run
streamlit run app.py
```

### Dependency Matrix

| Package | Required | Purpose |
|---------|----------|---------|
| streamlit | yes | Web UI framework |
| plotly | yes | Interactive charts |
| yfinance | yes | Price data (fallback) |
| numpy / pandas / scipy | yes | Computation |
| loguru | yes | Structured logging |
| diskcache | yes | Price cache |
| nselib | `[nse]` | Official NSE data |
| hmmlearn | `[ml]` | HMM regime detection |
| fpdf2 | `[pdf]` | PDF report export |
| ruff / pre-commit | dev | Linting / formatting |
| pytest / vcrpy | dev | Testing |

## Environment Variables

None required. The application runs with zero configuration.

| Variable | Purpose | Default |
|----------|---------|---------|
| `NSE_RISK_SCANNER_CACHE_DIR` | Override diskcache directory | `./data/__cache__` |
| `NSE_RISK_SCANNER_DB_PATH` | Override SQLite database path | `./data/nse_risk_scanner.db` |

## Local Development

```bash
# Lint & format
ruff check .
ruff format .

# Run all tests
pytest tests/ -v

# Single test file
pytest tests/test_risk.py -v

# With coverage
pytest tests/ --cov=engine --cov=data

# Pre-commit hooks (install once)
pre-commit install
```

### Code Style

- **Target:** Python 3.10+
- **Line length:** 110
- **Linter:** ruff (rules: E, F, I, N, W, UP, B, SIM)
- **Formatter:** ruff-format
- **Immutability:** spread/copy on every mutation, never `.append()` or direct assignment on shared state
- **No comments:** code should be self-documenting. Comments explain *why*, never *what*

### Commit Convention

```
<type>: <short description>

Types: fix, feat, docs, refactor, test, chore
```

## Testing

289 tests across 21 test files. Every module in `engine/` has dedicated unit tests. Integration tests exercise the full CSV→risk-metrics pipeline with mock network layer.

```bash
pytest tests/                       # Full suite
pytest tests/ -v --tb=short         # Verbose, short tracebacks
pytest tests/test_risk.py -k "monte" # Filter by test name
pytest tests/ --cov=engine --cov-report=term-missing  # Coverage with missed lines
```

**What's tested:**

| Area | File | Coverage |
|------|------|----------|
| CSV parsing + broker formats | `test_portfolio.py` | All 10+ broker formats, Indian numbers, BOM, delimiters |
| Risk metrics | `test_risk.py` | VaR, volatility, drawdown, Monte Carlo, denoising, attribution |
| Sector classification | `test_sector.py` | Mapping, HHI, diversification score, unknown tickers |
| Performance | `test_performance.py` | Returns, CAGR, drawdown, win rate, holding P&L |
| Benchmark | `test_benchmark.py` | Alpha, beta, tracking error, IR, outperformance |
| Optimization | `test_optimization.py` | HRP, min-vol, max-Sharpe, rebalancing |
| Regime detection | `test_regime.py` | HMM, statistical fallback, transition matrix |
| Scenario analysis | `test_scenario.py` | Basic, macro scenarios, sector impacts |
| Factors | `test_factors.py` | Factor exposures, macro drivers |
| Scoring | `test_scoring.py` | P×I×C scores, risk factors, interpretation |
| Recommendations | `test_recommendations.py` | Action generation, trade-offs, priority |
| Warnings | `test_warnings.py` | MA crossover, RSI, vol shifts, correlation breakdown |
| Price fetching | `test_prices.py` | Retry, backoff, parallel fetch, error handling |
| Cache | `test_cache.py` | TTL, eviction, clear, round-trip |
| Storage | `test_db.py`, `test_models.py` | CRUD, serialization, history |
| Integration | `test_integration.py` | Full pipeline, edge cases |
| PDF export | `test_pdf_export.py` | Chart generation, report assembly |

## Deployment

### Streamlit Cloud (recommended)

```toml
# .streamlit/config.toml (already included)
[server]
headless = true

[theme]
base = "dark"
```

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect the repository
4. Set main file to `app.py`
5. Deploy — no secrets or environment variables needed

### Manual / Docker

```bash
streamlit run app.py --server.port 8501 --server.headless true
```

The app binds to `0.0.0.0:8501` by default. Use a reverse proxy (nginx, Caddy) for production.

**CI** (`.github/workflows/ci.yml`) runs on every push/PR: ruff check → ruff format check → pytest with coverage.

## Common Troubleshooting

### "No data fetched for any holdings"
**Cause:** yfinance rate limits or network issues. Indian equities require `.NS` suffix — `RELIANCE` becomes `RELIANCE.NS` automatically, but if yfinance fails, no data returns.

**Fix:** Install nselib (`pip install -e ".[nse]"`) for official NSE data. Or wait and retry — yfinance has rolling rate limits.

### "Could not find columns: ticker, quantity, price"
**Cause:** CSV doesn't match any known broker format. Column names are unrecognized.

**Fix:** Rename columns to one of the supported aliases (see `engine/portfolio.py:_COLUMN_ALIASES`). At minimum: `symbol`, `qty`, `avg price`.

### CSV parses but shows zero quantities
**Cause:** Indian number format with commas (e.g. `1,000`). The parser strips commas globally, but if your locale uses comma as decimal separator, parsing breaks.

**Fix:** Export from your broker without thousand separators, or use a plain format.

### Monte Carlo shows NaN or 0
**Cause:** Insufficient price history (<10 trading days). The simulation needs enough data to estimate drift and volatility.

**Fix:** Use a 1-year price period. If a stock was recently listed, it will have limited history.

### Regime detection always returns None
**Cause:** Default statistical fallback needs 50+ data points. HMM mode (hmmlearn) needs 100+.

**Fix:** Install hmmlearn (`pip install -e ".[ml]"`) or ensure 6+ months of price history.

### "Portfolio exceeds max holdings (200)"
**Cause:** Hard limit to prevent resource exhaustion. Your CSV has more than 200 rows.

**Fix:** Split into sub-portfolios or reduce the limit in `engine/portfolio.py:_MAX_HOLDINGS`.

## Contributing

### PR Workflow

1. **Open an issue** — describe what you're fixing or adding before writing code
2. **Fork and branch** — `git checkout -b fix/description`
3. **Make surgical changes** — every changed line should trace directly to the goal
4. **Add tests** — new features need coverage. Bug fixes need a regression test that fails before the fix
5. **Run lint + tests** — `ruff check . && ruff format . && pytest tests/`
6. **Open a PR** — link the issue, describe the change, include before/after if visual

### Ground Rules

- **No new dependencies** without justification in the PR description. The app has zero paid APIs and we want to keep it that way.
- **No speculative features.** Build what solves the problem, nothing more.
- **Engine stays pure.** If you need Streamlit, it goes in `ui/`. If you need I/O, it goes in `data/`.
- **Comments explain *why*.** Code should be self-documenting for the *what*.
- **Tests are not optional.** Every `engine/` function should have a corresponding test. Every bug fix should include a regression test.
- **Keep the cache working.** If you add a new data source, integrate it into the L1→L2→L3 cache hierarchy.

### Good First Issues

Look for issues tagged [`good-first-issue`](https://github.com/AshayK003/nse-portfolio-risk-scanner/labels/good-first-issue). These are scoped, well-documented, and have existing tests as reference.

---

<p align="center">
  Built by <a href="https://github.com/AshayK003">AshayK003</a> ·
  <a href="LICENSE">MIT License</a>
</p>
