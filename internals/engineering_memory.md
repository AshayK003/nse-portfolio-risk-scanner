# Engineering Memory — NSE Portfolio Risk Scanner

## Architecture

```
app.py          — Thin Streamlit orchestrator (session state, tab routing)
engine/         — Pure business logic (zero Streamlit/IO imports)
  portfolio.py  — CSV parsing, column mapping, normalization
  risk.py       — VaR/CVaR/volatility/sharpe/sortino/beta
  factors.py    — Fama-French style factor decomposition
  performance.py — CAGR, max drawdown, returns, correlation matrix
  regime.py     — HMM regime detection + statistical fallback
  scenarios.py  — Macro sensitivity, stress testing
  scoring.py    — Composite risk scoring (1-100)
  warnings.py   — Early warning signals
  delivery.py   — Price/volume delivery analysis
  optimization.py — HRP, min-vol, max-sharpe
  recommendations.py — Actionable rebalancing suggestions
  benchmark.py  — Benchmark index mapping + comparison
data/           — Price acquisition + caching
  prices.py     — 3-tier cache (L1 LRU → L2 diskcache → L3 nselib/yfinance)
  cache.py      — L2 diskcache wrapper
storage/        — SQLite persistence
  db.py         — Schema, CRUD for portfolios + analysis runs
  models.py     — SavedPortfolio, AnalysisRun dataclasses
ui/             — Thin Streamlit presentation
  dashboard.py  — Tabs: overview, sectors, scenarios, optimize, export
  upload.py     — CSV upload widget, manual entry, saved portfolios
  icons.py      — Lucide SVG icon helpers
  styles.py     — Premium dark theme CSS
  export.py     — FPDF2 PDF report generation
tests/          — 270+ tests, tmp_path isolation, synthetic data
```

## Cache Hierarchy

```
@lru_cache (L1, process-local, 64 entries)
  → PriceCache/diskcache (L2, on-disk, 24h TTL)
    → nselib (primary for NSE equities)
    → yfinance (fallback for all tickers, indices)
```

- L2 uses `data/.price_cache/` directory
- `_FETCH_POOL` ThreadPoolExecutor for parallel fetch (max 3 workers)
- Retry with backoff: 0.5s → 1.5s → 3.0s
- Force refresh via `fetch_prices_refreshed()` clears both L1 and L2

## Key Bug Fix Patterns

### NaN float pitfall
`float('nan')` is truthy, so `info.get("field") or fallback` returns NaN instead of the fallback. Always use a NaN-safe extractor:
```python
def _nf(v) -> float | None:
    return None if (v is None or (isinstance(v, float) and math.isnan(v))) else v
```

### Threading.Lock() is non-reentrant
`threading.Lock()` deadlocks if acquired twice from the same thread. Use RLock() or inline the locked logic.

### ThreadPoolExecutor + Streamlit
Streamlit runs single-threaded, but `fetch_prices` uses ThreadPoolExecutor for parallel price fetching. The ThreadPoolExecutor `with` block can hang if a thread never completes — use `result(timeout=120)` guard.

### CSV column detection
`_resolve_column_map()` uses a scoring heuristic:
1. Name-based regex match (`^ticker$`, `^qty$`, `^avg price$`, etc.)
2. Value-based heuristic (check if sample values look like tickers, numbers, prices)
3. Position-based fallback (first string col = ticker, first numeric = qty)

### Optional dependency guard pattern
```python
try:
    from nselib import capital_market
    _NSELIB_AVAILABLE = True
except ImportError:
    _NSELIB_AVAILABLE = False
```


### Loguru compatibility
When loguru is not installed, the code falls back to stdlib logging with a wrapper that converts `{var}` kwargs to `.format()` calls. Both files (data/prices.py, app.py) have this guard.

## Trade-offs

### Price cache: diskcache vs SQLite
Two caches were originally defined: the L2 diskcache (`data/cache.py`) and a SQLite `price_cache` table (`storage/db.py`). The diskcache was wired into the fetch pipeline; the SQLite table was never called from production code. Decision: **removed the SQLite price_cache table** — the diskcache is simpler, tested, and sufficient.

### Sector classification
160+ NSE stocks mapped to 13 sectors in `data/sectors.py`. Hardcoded mapping chosen over API-based because yfinance sector data is unreliable for Indian stocks.

### HMM regime vs statistical fallback
HMM requires `hmmlearn` (optional dep). When not installed, falls back to `_detect_statistical()` using rolling quantiles. The statistical approach may be sufficient as the sole implementation — HMM retained for optional regime-switching analysis.

## Known Limitations

- Streamlit PDF export tests can't run without a browser context (21 test failures are pre-existing)
- Cache tests 5 failures are pre-existing (test environment issue with diskcache paths)
- Benchmark indices with `^` prefix can't use nselib — always go through yfinance
