<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&height=200&section=header&text=NSE%20Portfolio%20Risk%20Scanner&fontSize=40&fontAlignY=32&desc=Institutional-grade%20risk%20analysis%20for%20Indian%20equity%20portfolios&descAlignY=50&animation=fadeIn" width="100%"/>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-22C55E?style=flat" alt="License"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://streamlit.io"><img src="https://img.shields.io/badge/built%20with-Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white" alt="Streamlit"></a>
  <img src="https://img.shields.io/badge/tests-355%20passing-22C55E?style=flat&logo=pytest" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-90%25-22C55E?style=flat&logo=codecov" alt="Coverage">
  <img src="https://img.shields.io/badge/mobile-friendly-22C55E?style=flat&logo=android" alt="Mobile Friendly">
</p>

---

Analyze your NSE portfolio using professional-grade risk metrics — Value at Risk, Monte Carlo simulation, factor decomposition, regime detection, HRP optimization, stress testing, Altman Z-Score, VaR backtesting, GARCH volatility modeling, PELVE ratio, and advanced portfolio optimization (Riskfolio-Lib). Zero paid APIs. 355 tests.

---

## Features

| Category | What you get |
|----------|-------------|
| **Risk Metrics** | Annualized volatility, VaR (95%/99%), CVaR, Sharpe/Sortino ratios, beta, max drawdown with peak-to-trough dates |
| **Monte Carlo** | 10,000-path GBM simulation — probability of profit, confidence intervals, horizon VaR |
| **Optimization** | Hierarchical Risk Parity (HRP), Minimum Volatility, Maximum Sharpe — with weight caps, cash-instrument exclusion, and transaction cost estimates |
| **Regime Detection** | HMM-based bull/neutral/bear classification with transition matrix and per-regime stats. Falls back to quantile heuristic when hmmlearn not installed |
| **Factor Decomposition** | Market, size, momentum, volatility, liquidity, and concentration factor exposures. Macro sensitivity estimates for crude, rates, INR/USD, and risk sentiment |
| **Sector Analysis** | 160+ NSE stocks pre-mapped across 18 sectors. Concentration detection (HHI), diversification scoring |
| **Benchmark Comparison** | Nifty 50 / Bank Nifty / Sensex / sectoral indices. Alpha, tracking error, information ratio, monthly outperformance |
| **Correlation Denoising** | Marchenko-Pastur eigenvalue clipping for cleaner covariance estimates |
| **Stress Testing** | 5 basic scenarios + 7 macro scenarios with sector-specific multipliers and causal reasoning |
| **Institutional Scoring** | P×I×C framework — Overall Risk, Conviction, Stress, Hidden Correlation, and Tail Risk scores |
| **Early Warnings** | MA crossover, RSI extremes, volatility regime shifts, correlation breakdowns, momentum divergences |
| **Recommendations** | Actionable suggestions (reduce/hedge/diversify/accumulate) with expected risk reduction and trade-off analysis |
| **AI Narratives** | Rule-based plain-English explanations — volatility, VaR, Sharpe, drawdown, concentration, benchmark alpha/beta, key concerns, overall verdict. No LLM, no API calls |
|| **Risk Profiles** | Conservative / Moderate / Aggressive — controls optimization method, single-stock cap, and 6 recommendation thresholds. Changing profile recalculates all metrics automatically |
|| **Portfolio Health Gauge** | Single 0-100 health score at the top of every report — green/yellow/red color-coded. Instant answer to "is my portfolio OK?" |
|| **Risk-free Rate** | Adjustable slider (3-10%) in sidebar — Sharpe, Sortino, and alpha update dynamically. Default 6.5% (10-year Indian bond yield) |
|| **Shareable Links** | Base64-encoded portfolio in `?p=` query param — share your risk report as a single URL. Zero server storage |
|| **Export** | CSV with position-level risk data + 4-page PDF report (cover page, risk analysis, holdings breakdown) |
| **10+ Broker Formats** | Zerodha, Groww, Upstox, Angel One, ICICI Direct, Kotak, HDFC — Indian number format, auto column detection |

## Demo

<!-- Replace with a screenshot of the app:
  ![App Screenshot](assets/demo.png)
-->

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&height=2&section=header" width="100%"/>
</p>

## Quick Start

```bash
# Clone and enter
git clone https://github.com/AshayK003/nse-portfolio-risk-scanner.git
cd nse-portfolio-risk-scanner

# Create virtual environment
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# Install (pick extras as needed)
pip install -e ".[dev,pdf]"             # Minimal — yfinance only
pip install -e ".[dev,pdf,nse]"         # + nselib for official NSE data
pip install -e ".[dev,pdf,nse,ml]"      # + hmmlearn for ML regime detection

# Launch
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
| fpdf2 + matplotlib | — | PDF report export (included by default) |
| ruff / pre-commit | dev | Linting / formatting |
| pytest / vcrpy | dev | Testing |

### Environment Variables

None required. Runs with zero configuration.

| Variable | Purpose | Default |
|----------|---------|---------|
| `NSE_RISK_SCANNER_CACHE_DIR` | Override diskcache directory | `./data/__cache__` |
| `NSE_RISK_SCANNER_DB_PATH` | Override SQLite database path | `./data/nse_risk_scanner.db` |

---

## Architecture

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&height=2&section=header" width="100%"/>
</p>

```
┌─────────────────────────────────────────────────────┐
│  app.py  (thin orchestration, ~200 imperative lines) │
├─────────────────────────────────────────────────────┤
│                    ┌──────────────────┐              │
│                    │    engine/       │              │
│                    │  pure functions  │              │
│                    │  zero Streamlit  │              │
│                    │  zero I/O        │              │
│                    └──────────────────┘              │
│                    ┌──────────────────┐              │
│                    │    data/         │              │
│                    │  price fetching  │              │
│                    │  3-tier cache    │              │
│                    └──────────────────┘              │
│                    ┌──────────────────┐              │
│                    │    ui/           │              │
│                    │  Streamlit only  │              │
│                    │  no business logic│              │
│                    └──────────────────┘              │
│                    ┌──────────────────┐              │
│                    │    storage/      │              │
│                    │  SQLite history  │              │
│                    └──────────────────┘              │
└─────────────────────────────────────────────────────┘
```

**The rules are strict:**
- `engine/` never imports Streamlit. Every function is pure — inputs in, dataclass out.
- `ui/` never computes math. It calls engine functions and renders results.
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
│   ├── backtesting.py         # VaR backtesting (Kupiec POF)
│   ├── fundamentals.py        # Altman Z-Score
│   ├── garch_var.py           # GARCH(1,1)-t VaR
│   ├── optimization_advanced.py # Riskfolio-Lib wrapper
│   ├── pelve.py               # PELVE ratio
│   ├── factors.py            # Factor decomposition + macro sensitivities
│   ├── scoring.py            # Institutional risk scoring (P×I×C)
│   ├── narrative.py          # Rule-based narrative generation (zero LLM)
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
├── tests/                    # 355 tests
└── .pre-commit-config.yaml   # Ruff + pre-commit hooks
```

---

## Local Development

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&height=2&section=header" width="100%"/>
</p>

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

| Rule | Standard |
|------|----------|
| **Target** | Python 3.10+ |
| **Line length** | 110 |
| **Linter** | ruff (E, F, I, N, W, UP, B, SIM) |
| **Formatter** | ruff-format |
| **Immutability** | spread/copy on every mutation, never `.append()` or direct assignment on shared state |
| **Comments** | explain *why*, never *what* |

### Commit Convention

```
<type>: <short description>
Types: fix, feat, docs, refactor, test, chore
```

---

## Testing

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&height=2&section=header" width="100%"/>
</p>

355 tests across 26 test files. Every module in `engine/` has dedicated unit tests.

```bash
pytest tests/                           # Full suite
pytest tests/ -v --tb=short             # Verbose, short tracebacks
pytest tests/test_risk.py -k "monte"    # Filter by test name
pytest tests/ --cov=engine --cov-report=term-missing
```

| Area | File | Coverage |
|------|------|----------|
| CSV parsing + broker formats | `test_portfolio.py` | All 10+ broker formats, Indian numbers, BOM, delimiters |
| Risk metrics | `test_risk.py` | VaR, volatility, drawdown, Monte Carlo, denoising, attribution |
| Sector classification | `test_sector.py` | Mapping, HHI, diversification score, unknown tickers |
| Performance | `test_performance.py` | Returns, max drawdown |
| Benchmark | `test_benchmark.py` | Alpha, beta, tracking error, IR, outperformance |
| Optimization | `test_optimization.py` | HRP, min-vol, max-Sharpe, rebalancing |
| Regime detection | `test_regime.py` | HMM, statistical fallback, transition matrix |
| Scenario analysis | `test_scenario.py` | Basic, macro scenarios, sector impacts |
| Factors | `test_factors.py` | Factor exposures, macro drivers |
| Scoring | `test_scoring.py` | P×I×C scores, risk factors, interpretation |
| Recommendations | `test_recommendations.py` | Action generation, trade-offs, priority |
| Narrative | `test_narrative.py` | Threshold boundaries, edge cases, benchmark none |
| Fundamentals | `test_fundamentals.py` | Altman Z-Score, zone classification, missing data |
| Backtesting | `test_backtesting.py` | Kupiec POF, exception rates, multiple confidences |
| GARCH VaR | `test_garch_var.py` | GARCH(1,1)-t VaR, insufficient data, arch fallback |
| PELVE | `test_pelve.py` | PELVE ratio, epsilon param, zero vol, fat tails |
| Warnings | `test_warnings.py` | MA crossover, RSI, vol shifts, correlation breakdown |
| Price fetching | `test_prices.py` | Retry, backoff, parallel fetch, error handling |
| Cache | `test_cache.py` | TTL, eviction, clear, round-trip |
| Storage | `test_db.py`, `test_models.py` | CRUD, serialization, history |
| Integration | `test_integration.py` | Full pipeline, edge cases |
| PDF export | `test_pdf_export.py` | Chart generation, report assembly |

---

## Deployment

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&height=2&section=header" width="100%"/>
</p>

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

## Pre-commit

This project uses [pre-commit](https://pre-commit.com) with [Ruff](https://docs.astral.sh/ruff/) for linting and formatting on every commit. To set up:

---

## Common Troubleshooting

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&height=2&section=header" width="100%"/>
</p>

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

---

## Contributing

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&height=2&section=header" width="100%"/>
</p>

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
  <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&height=120&section=footer&text=AshayK003/nse-portfolio-risk-scanner&fontSize=20&fontAlignY=70" width="100%"/>
</p>

<p align="center">
  Built by <a href="https://github.com/AshayK003">Ashay Kushwaha</a> ·
  <a href="LICENSE">MIT License</a>
</p>
