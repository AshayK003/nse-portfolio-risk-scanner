# NSE Portfolio Risk Scanner — Architecture Review & Redesign

**Author:** Principal Architecture Review  
**Date:** 2026-06-18  
**Scope:** Full-stack architecture for a ₹199 Gumroad micro-SaaS, designed for 0→100 users without rewrites.

---

## 1. Current Architecture Assessment

### What exists today
A single `app.py` Streamlit file that chains: CSV upload → yfinance fetch → numpy compute → Plotly render → fpdf export. Everything lives in one namespace with Streamlet callbacks woven through business logic.

### Weaknesses

| # | Issue | Impact Today | Impact at 100 Users |
|---|-------|-------------|---------------------|
| 1 | **No separation of concerns** — UI rendering, yfinance calls, and risk math are interleaved | Hard to test, hard to debug | Impossible to reuse compute for CLI, API, or cron jobs |
| 2 | **No caching** — each page re-run fetches prices fresh from Yahoo | Slow UX (3-8s per stock) | Yahoo rate-limits you after ~50 NSE symbols/hour. App becomes unusable. |
| 3 | **No state management** — Streamlet reruns the entire script on every widget interaction | Portfolio disappears on tab switch | Users can't compare scenarios. No session persistence. |
| 4 | **No persistence** — portfolio lives in session memory only | Must re-upload CSV every session | Power users with 30+ stocks abandon the app |
| 5 | **Streamlet tightly coupled to compute** — can't run risk analysis via CLI, API, or cron | Must open browser to get numbers | Can't build Telegram alerts or scheduled portfolio briefings |
| 6 | **No error boundaries** — one stock failing yfinance crashes the whole analysis | Single delisted ticker = zero output | Frequent NSE corporate actions cause support tickets |
| 7 | **No testability** — unit tests require mocking streamlit global state | Manual testing only | Every release breaks something |

---

## 2. Target Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     STREAMLIT APP (thin UI)               │
│  app.py → ui/upload.py  ui/dashboard.py  ui/charts.py    │
│           ui/export.py                                    │
│  State: st.session_state (UI only)                        │
│  Caching: @st.cache_data (yfinance responses)             │
└────────────────────────┬─────────────────────────────────┘
                         │ imports (not API calls)
┌────────────────────────▼─────────────────────────────────┐
│               BUSINESS LOGIC (pure Python)                 │
│  engine/portfolio.py  →  CSV parse, validate, normalize   │
│  engine/risk.py       →  VaR, beta, volatility, drawdown  │
│  engine/sector.py     →  NSE sector classification        │
│  engine/performance.py→  Sharpe, Sortino, CAGR, alpha     │
│  engine/benchmark.py  →  Nifty 50 vs portfolio comparison │
│                                                           │
│  ZERO dependencies on Streamlit. Pure numpy/pandas/scipy. │
│  Importable by CLI, FastAPI, cron, or Jupyter notebook.   │
└────────────────────────┬─────────────────────────────────┘
                         │ calls
┌────────────────────────▼─────────────────────────────────┐
│              DATA PROVIDERS + CACHE LAYER                  │
│  data/prices.py   →  yfinance wrapper                     │
│  data/cache.py    →  SQLite-backed price cache            │
│  data/sectors.yaml→  Static NSE sector mapping            │
└────────────────────────┬─────────────────────────────────┘
                         │ reads/writes
┌────────────────────────▼─────────────────────────────────┐
│              STORAGE (SQLite)                              │
│  storage/db.py     →  Schema, migrations, connections      │
│  storage/models.py →  Dataclass models (Portfolio, ...)   │
└──────────────────────────────────────────────────────────┘
```

### Key Principle

**The `engine/` package has zero knowledge of Streamlit, HTTP, or the UI layer.** It accepts DataFrames and returns dicts/dataclasses. This single decision unlocks:
- Unit testing without mocking
- CLI tool for power users (`nse-risk --portfolio my.csv`)
- FastAPI backend when you outgrow Streamlit
- Cron jobs for scheduled portfolio monitoring
- Jupyter notebook analysis for your personal workflow

---

## 3. Module Boundaries & Responsibilities

### `engine/portfolio.py`
```
Responsibility:  CSV parsing, validation, normalization
Input:           Raw CSV bytes or file path
Output:          Portfolio dataclass (list of Holdings)
Pure:            Yes (no I/O beyond file reads)
Testable:        pytest with fixture CSVs
```
- Rejects: empty portfolios, unknown tickers, negative quantities
- Normalizes: ticker casing, whitespace, `.NS` suffix mapping
- Returns structured Portfolio with Holdings[] — no DataFrames exposed at boundary

### `engine/risk.py`
```
Responsibility:  All risk metric computation
Input:           price_history DataFrame, current_prices dict, portfolio weights
Output:          RiskMetrics dataclass
Pure:            Yes (pure math on arrays)
Testable:        pytest with synthetic price data
```
- Historical volatility (annualized)
- Value at Risk (95%, 99%) — parametric + historical
- Conditional VaR
- Max drawdown (value + date range)
- Beta to Nifty 50
- Correlation matrix between holdings

### `engine/sector.py`
```
Responsibility:  NSE sector classification + concentration analysis
Input:           list[Stock] with quantities
Output:          SectorExposure dataclass
Pure:            Yes (reads embedded YAML)
Testable:        pytest with known stock names
```
- Maps NSE tickers to sectors from `data/sectors.yaml`
- Computes % allocation per sector
- Flags concentration risk (single sector > 20%)
- Integrates with risk.py for sector-level VaR

### `engine/performance.py`
```
Responsibility:  Return and risk-adjusted performance metrics
Input:           price_history DataFrame, risk_free_rate
Output:          PerformanceMetrics dataclass
Pure:            Yes
Testable:        pytest
```
- Total return (1m, 3m, 6m, 1y, YTD, since inception)
- CAGR
- Sharpe ratio (with Indian risk-free rate ~6.5%)
- Sortino ratio
- Alpha (vs Nifty 50)
- Win rate, profit factor

### `engine/benchmark.py`
```
Responsibility:  Benchmark comparison against Nifty 50 / sector indices
Input:           portfolio returns series
Output:          BenchmarkComparison dataclass
Pure:            Yes
Testable:        pytest
```
- Fetches benchmark data via yfinance (^NSEI for Nifty 50)
- Computes tracking error, information ratio
- Relative drawdown analysis
- Rolling correlation

### `data/prices.py`
```
Responsibility:  Price data acquisition with multi-tier caching
Input:           list[ticker], date_range
Output:          price_history DataFrame
Has I/O:        Yes (yfinance + cache reads/writes)
```
- Tier 1: `@st.cache_data` for in-memory during session
- Tier 2: SQLite cache for cross-session reuse
- Falls back: if yfinance fails for a ticker, return cached + warn, don't crash
- Batch: fetches in batches of 10 with 1s delay to avoid rate limits
- Handles NSE `.NS` suffix transparently

### `ui/` Package
Each file is a "thin presentation layer" — no business logic.
```
ui/upload.py     →  st.file_uploader + st.data_editor
ui/dashboard.py  →  Tab layout, metric cards, chart organization
ui/charts.py     →  Plotly chart builders (treemap, gauge, line, bar)
ui/export.py     →  fpdf report generator + st.download_button
```
- Calls `engine.*` functions, passes results to Plotly/Streamlit
- No raw yfinance calls. No numpy math. Just layout and rendering.

### `storage/db.py`
```
Responsibility:  SQLite schema management, CRUD for portfolios and cache
Input/Output:   SQLite file on disk
```
- Tables: `portfolios`, `holdings`, `price_cache`, `analysis_runs`
- Versioned schema (single `schema_version` integer)
- Write-ahead logging for concurrent reads
- No ORM — raw sqlite3 with parameterized queries

---

## 4. Data Flow

```
USER UPLOADS CSV
       │
       ▼
ui/upload.py ──reads bytes──► engine/portfolio.parse_portfolio()
       │                           │
       │                      ┌────▼────┐
       │                      │ Valid?   │──NO──► st.error()
       │                      └────┬────┘
       │                           │ YES
       │                           ▼
       │                  engine/portfolio.normalize()
       │                  (adds .NS suffix, cleans names)
       │                           │
       ▼                           ▼
st.data_editor ──user edits──► Portfolio dataclass
       │                           │
       │                           ▼
       │                  data/prices.fetch_batch()
       │                  ┌────────┼────────┐
       │                  │ Tier 1 │ Tier 2 │ yfinance
       │                  │memory  │ SQLite │ (miss)
       │                  └────────┴────────┘
       │                           │
       │                           ▼
       │                  price_history DataFrame
       │                           │
       ├───────────────────────────┤
       │                           │
       ▼                           ▼
engine/risk.compute()     engine/performance.compute()
engine/sector.analyze()   engine/benchmark.compare()
       │                           │
       └───────────┬───────────────┘
                   ▼
         RiskReport dataclass
                   │
          ┌────────┼────────┐
          ▼        ▼        ▼
  ui/dashboard  ui/charts  ui/export
  (st.metric)   (Plotly)   (fpdf/CSV)
```

### State Flow

```
┌─────────────────────────────────────┐
│         Streamlit Session            │
│                                     │
│  st.session_state.portfolio  ───────┤  Portfolio dataclass (persisted across reruns)
│  st.session_state.risk_report ──────┤  RiskReport dataclass (cached compute)
│  st.session_state.active_tab ───────┤  Current tab index
│  st.session_state.saved_portfolios──┤  List of saved portfolio names (from SQLite)
│                                     │
│  SQLite (on disk)                    │
│  ├── portfolios table ──────────────┤  Named portfolios, user-saved
│  ├── price_cache table ─────────────┤  yfinance responses (TTL: 24h)
│  └── analysis_runs table ───────────┤  History of analyses performed
└─────────────────────────────────────┘
```

---

## 5. Caching Strategy (Three Tiers)

| Tier | Location | Scope | TTL | Contents | Eviction |
|------|----------|-------|-----|----------|----------|
| **L1** | `@st.cache_data` | In-memory, per session | 1 hour | yfinance price responses for current portfolio | Session end or TTL expiry |
| **L2** | `price_cache` table (SQLite) | On-disk, cross-session | 24 hours | Historical price data for all fetched symbols | Stale entries on write |
| **L3** | `sectors.yaml` | Git-tracked file | Months | Ticker→sector mapping | Manual PR |

**Cache invalidation rules:**
- Forced refresh button in UI clears L1 and L2 for selected symbols
- Price cache auto-expires on the next market day (compare date vs next trading day)
- Sector mapping only changes when NSE reclassifies (rare — manual update)

**Why no Redis:** SQLite handles 50k+ rows of cached prices trivially. A ₹199 tool does not need Redis. When you have 10,000 users, add Redis. Until then, SQLite is faster to deploy and zero maintenance.

---

## 6. API Design (for Phase 2 — Streamlit-only in v1)

These endpoints are defined now so the `engine/` package exposes them from day one. The Streamlit UI calls them directly (no HTTP). When FastAPI is added later, the endpoints are already designed and tested.

### REST Endpoints (for future FastAPI layer)

| Method | Path | Input | Output | Purpose |
|--------|------|-------|--------|---------|
| `POST` | `/api/portfolio/parse` | CSV file | `Portfolio` JSON | Validate & normalize uploaded portfolio |
| `POST` | `/api/portfolio/analyze` | `Portfolio` JSON | `RiskReport` JSON | Full risk analysis (async for large portfolios) |
| `GET` | `/api/portfolio/{id}` | Portfolio ID | `Portfolio` JSON | Load saved portfolio |
| `GET` | `/api/portfolio/{id}/report` | Portfolio ID | PDF file | Downloadable risk report |
| `POST` | `/api/portfolio/compare` | Two Portfolio IDs | Comparison JSON | Side-by-side risk comparison |
| `GET` | `/api/stock/{ticker}/info` | Ticker | Stock info JSON | Company name, sector, mcap |

### Python API (for direct import — THIS IS WHAT V1 USES)

```python
# engine/portfolio.py
parse_portfolio(csv_bytes: bytes) -> Portfolio  # Validate and normalize
save_portfolio(name: str, portfolio: Portfolio)  # Persist to SQLite
load_portfolio(name: str) -> Portfolio            # Load from SQLite

# engine/risk.py
compute_risk(portfolio: Portfolio, prices: pd.DataFrame) -> RiskMetrics

# engine/sector.py
analyze_sectors(portfolio: Portfolio) -> SectorExposure

# engine/performance.py
compute_performance(prices: pd.DataFrame, benchmark: pd.DataFrame) -> PerformanceMetrics

# engine/benchmark.py
compare_to_benchmark(portfolio_returns: pd.Series, benchmark_ticker: str) -> BenchmarkComparison

# data/prices.py
fetch_prices(holdings: list[Holding], force_refresh: bool = False) -> pd.DataFrame
```

---

## 7. State Management Strategy

### What to store WHERE

| Data | Where | Why |
|------|-------|-----|
| Current portfolio (active session) | `st.session_state.portfolio` | Avoids re-parse on every rerun |
| Risk report (computed results) | `st.session_state.risk_report` | Avoids recomputing metrics when user switches tabs |
| UI state (active tab, sort order, selected chart) | `st.session_state` | Streamlet reruns the script — state must survive |
| Saved portfolios (user-wanted persistence) | SQLite `portfolios` table | Survives sessions, exportable, queryable |
| Price cache | SQLite `price_cache` table | Cross-session reuse, avoids yfinance rate limits |
| Analysis history | SQLite `analysis_runs` table | "Last week's report" feature, change tracking |
| Sector mapping | `data/sectors.yaml` | Version-controlled, human-readable, edit-friendly |

### Anti-patterns to AVOID

| Anti-pattern | Why it's bad | What to do instead |
|-------------|--------------|-------------------|
| Storing price data in `st.session_state` | Memory leak across reruns | Use `@st.cache_data` (LRU evicted) |
| SQLite as session state | Slow for frequent reads | Default: session_state for UI, SQLite for persistence |
| Computed metrics in session without recompute flag | Stale data when user changes portfolio | Compare portfolio hash on rerun |
| Global mutable variables in engine/ | Breaks testability, creates hidden coupling | Return new objects from pure functions |

---

## 8. Deployment Strategy (Free/OSS Only)

### Phase 1 — Launch (0-50 users)
```
Streamlit Community Cloud (free)
├── GitHub repo connected → auto-deploy on push
├── SQLite file stored on Streamlit's ephemeral storage
│   (acceptable for single-user tool — cache rebuilds on redeploy)
├── Secrets: none required (yfinance needs no auth)
└── Domain: your-app.streamlit.app (free)
```

### Phase 2 — Growth (50-500 users)
```
Hetzner CX22 ($4.49/mo) or Oracle Cloud Free Tier
├── Docker Compose:
│   ├── streamlit-proxy:  Caddy + Tailscale/Cloudflare Tunnel (free)
│   ├── app:              Streamlit container
│   ├── cache:            SQLite (mounted volume)
│   └── scheduler:        Cron container for periodic briefings
├── Cloudflare Tunnel (free) for HTTPS + domain
└── Backup: crontab SQLite dump to your GitHub repo (git push)
```

### Phase 3 — Scale (500+ users)
```
Same Hetzner box, add optional Postgres (+$3/mo) if SQLite WAL
bottlenecks on concurrent writes. But test SQLite first — it handles
thousands of reads/second easily.
```

### What you DO NOT need

| Service | Cost | Why skip |
|---------|------|----------|
| Redis | $15-30/mo | SQLite cache is fine for 500 users |
| AWS/GCP/Azure | $50-200/mo | Hetzner or Oracle free tier covers everything |
| Auth0/Firebase Auth | $25/mo+ | No multi-user in v1 |
| Sentry | $29/mo | Streamlit shows errors in terminal |
| CDN | $10/mo+ | Streamlit Community Cloud has CDN built in |
| Docker registry | N/A | GitHub Container Registry is free |

### Infrastructure as Code (free)

```yaml
# docker-compose.yml (Phase 2)
version: "3.8"
services:
  app:
    build: .
    ports: ["8501:8501"]
    volumes:
      - ./data:/app/data  # SQLite persistence
    env:
      - STREAMLIT_SERVER_PORT=8501

  scheduler:
    build: .
    command: python -m scheduler.daily_briefing
    volumes:
      - ./data:/app/data
    depends_on: [app]
```

---

## 9. What NOT to Build Yet

| Feature | Defer To | Rationale |
|---------|----------|-----------|
| **User authentication** | Phase 3 (500+ users) | Streamlit Community Cloud is single-user. Adding auth adds complexity, login screens, password resets, GDPR concerns. Ship first, auth later. |
| **FastAPI backend** | Phase 2 | Streamlit can call the engine directly. HTTP API adds deployment complexity, port management, CORS. Only add when you need non-browser clients. |
| **Redis/Memcached** | Phase 3 | SQLite handles your cache needs. Redis is another service to monitor, backup, and debug. Premature optimization. |
| **Async/parallel processing** | Phase 2 | Streamlit runs sync. For 50 stocks, yfinance batch fetch with 1s delay takes ~5s. Acceptable for v1. Add asyncio when users complain. |
| **CI/CD pipeline** | Day 2 | GitHub Actions for lint + test on PR is 10 lines. Don't build a deployment pipeline — Streamlit auto-deploys from GitHub. |
| **Portfolio optimization** | v2 | Mean-variance optimization, efficient frontier, risk parity. These are features, not architecture. Build them in engine/ when the v1 metrics are proven. |
| **Telegram / email integration** | v2 | Notification channels. Design the engine to emit structured reports (dataclasses), then add delivery adapters. Don't build notification before the report. |
| **Mobile app / API client** | Never | Your users are desktop traders. They use Zerodha/Groww on phone. Your tool is for deep analysis — works best on desktop. Don't split your engineering. |
| **Kubernetes** | Never | You're building a ₹199 tool, not a bank. Docker Compose on a $5 VPS is the ceiling. |

---

## 10. Project Structure (Concrete)

```
D:\Personal projects\NSE Portfolio Risk Scanner\
├── app.py                          # Streamlit entry point (~50 lines — thin orchestration)
├── engine/                         # Business logic (zero Streamlit deps)
│   ├── __init__.py
│   ├── portfolio.py                # CSV parse, validate, normalize
│   ├── risk.py                     # VaR, CVaR, volatility, beta, drawdown
│   ├── sector.py                   # NSE sector classification, concentration
│   ├── performance.py              # Sharpe, Sortino, CAGR, alpha, returns
│   └── benchmark.py                # Nifty 50 tracking error, correlation
├── data/                           # Data providers and static assets
│   ├── __init__.py
│   ├── prices.py                   # yfinance wrapper with 3-tier caching
│   ├── sectors.yaml                # 200+ NSE ticker→sector mappings
│   └── cache.py                    # SQLite-backed price cache
├── ui/                             # Streamlit presentation layer (no business logic)
│   ├── __init__.py
│   ├── upload.py                   # CSV upload + data editor
│   ├── dashboard.py                # Main layout, tabs, metric cards
│   ├── charts.py                   # Plotly chart builders
│   └── export.py                   # PDF/CSV report generation
├── storage/                        # Persistence layer
│   ├── __init__.py
│   ├── db.py                       # SQLite connection, migrations, schema
│   └── models.py                   # Dataclasses: Portfolio, Holding, RiskReport, ...
├── tests/                          # Unit tests (pytest, no Streamlit mocking)
│   ├── conftest.py                 # Fixtures: sample portfolios, price data
│   ├── test_portfolio.py
│   ├── test_risk.py
│   ├── test_sector.py
│   ├── test_performance.py
│   └── test_benchmark.py
├── pyproject.toml                  # Dependencies, build config
├── requirements.txt
├── research/
│   └── open-source-ecosystem-report.md
└── .streamlit/
    └── config.toml                 # Theme, server settings
```

### Dependency map (strict acyclic)

```
app.py
  └── ui/* (Streamlit)
        └── engine/* (pure Python)
              ├── data/prices.py (yfinance + cache)
              ├── data/sectors.yaml
              └── storage/models.py
app.py
  └── storage/db.py (SQLite)
```

Engine never imports Streamlit. UI never computes math. Data never knows about UI state.

---

## 11. Ranked: 5 Highest-Impact Changes

| Rank | Change | Why It Matters Most | Effort | Impact |
|------|--------|---------------------|--------|--------|
| **1** | **Separate `engine/` from `ui/`** | Everything depends on this. Testing, CLI, API, cron, reuse — all blocked until business logic has zero UI dependencies. This is the foundation. | 2 hours | 🟢 Critical |
| **2** | **Add SQLite price cache** | Without caching, the app slows down by 3-8x on every page load and Yahoo rate-limits you after ~50 NSE symbols/hour. This is the single biggest UX killer. | 1 hour | 🟢 Critical |
| **3** | **Introduce `st.session_state` for portfolio persistence** | Currently portfolio vanishes on tab switch or widget interaction. Users can't explore risk scenarios. This is the #1 frustration with naive Streamlit apps. | 30 min | 🟢 Critical |
| **4** | **Error isolation per-ticker** | One delisted/corporate-action stock currently crashes the entire analysis. With per-ticker try/except + graceful fallback + user-facing warnings, the app works even with data issues. | 1 hour | 🟡 High |
| **5** | **@st.cache_data on ALL data fetches** | Streamlet's built-in memory cache costs zero effort (decorator + ttl) but eliminates redundant yfinance calls during the same session. Immediate 3x speedup. | 15 min | 🟡 High |

### Summary

The current naive approach (flat `app.py`) works for a demo but will break at the first real user. The proposed architecture:

- **Keeps Streamlit** as the UI (right tool for the job)
- **Extracts pure business logic** into testable, reusable modules
- **Adds 3-tier caching** to survive yfinance rate limits
- **Separates concerns** so you can add FastAPI, Telegram, or CLI later without rewriting
- **Costs zero dollars** in new infrastructure — all open-source, all free-tier deployable

The most important discipline: **engine/ never imports streamlit.** Draw that line and everything else falls into place.
