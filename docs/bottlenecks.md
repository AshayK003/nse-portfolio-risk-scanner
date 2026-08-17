# docs/bottlenecks.md — AEOS Module 10: Product-Minded Engineer

## Project: NSE Portfolio Risk Scanner
## Audit Date: 2026-08-17
## Auditor: AEOS M10 (Product-Minded Engineer)

---

### #1 Bottleneck — Massive `app.py` God Module (40 KB, 996 lines)

**Location:** `app.py` (entire file)

**Current Behavior:**
The entry point `app.py` is a 996-line monolith that:
- Imports 50+ engine/UI functions at top level
- Contains the entire Streamlit rendering pipeline (500+ lines of tab rendering)
- Embeds all computation logic inline (400+ lines of try/except blocks for each intelligence module)
- Manages session state manually with 15+ keys
- Duplicates cache unpacking logic (lines 465-495 mirror 432-462)

**Why It's Wasteful:**
- Violates the declared architecture: "Thin orchestration layer: reads CSV → computes risk → renders UI. Engine has ZERO Streamlit imports. UI has ZERO business logic."
- Every intelligence module (factor, macro, Z-score, GARCH, PELVE, recommendations) has its own try/except — 15+ repeated patterns
- Cache logic is duplicated: 60 lines of cache store + 60 lines of cache load
- Tab rendering is 400+ lines of imperative code mixed with business logic
- Adding a new intelligence module requires touching `app.py` in 3 places (import, computation, cache, render)
- Single point of failure: any syntax error in one module breaks the entire app load

**Proposed Change:**
Extract to 3 files:
1. `app.py` → pure thin orchestrator (< 150 lines): session state, routing, tab dispatch only
2. `ui/render.py` → all tab rendering functions (move from `app.py` lines 525-996)
3. `engine/compute.py` → all computation blocks (lines 186-430), cache logic, intelligence modules

**Expected Impact:**
- 70% reduction in `app.py` size
- New intelligence modules addable by editing 1 file (`engine/compute.py`) not 3
- Clear separation: computation is testable without Streamlit; rendering is pure UI
- Cache logic written once, not duplicated
- Enables unit testing of computation pipeline independently

**Effort Estimate:** 4-6 hours (surgical extraction, no logic changes)

---

### #2 Bottleneck — `engine/ticker_resolver.py` Duplicate Map (31 KB, 939 lines)

**Location:** `engine/ticker_resolver.py` lines 23-650 (NSE_TICKERS dict)

**Current Behavior:**
Hardcoded 318-entry `NSE_TICKERS` dict + 240-entry `ALIASES` dict + resolution logic. This map was ported from NSE Sentiment Analyzer (`data_fetcher.py`) and duplicates the same data in two repos.

**Why It's Wasteful:**
- 31 KB of static data in a Python module — not code, just data
- Same map exists in NSE Sentiment Analyzer repo (single source of truth violated)
- Python module loading cost: imports 31 KB on every app startup (contributes to cold-start latency)
- Maintenance burden: updating ticker list requires editing Python source, not a data file
- Can't version the ticker map independently of code

**Proposed Change:**
1. Move `NSE_TICKERS` + `ALIASES` to `data/tickers.json` (structured JSON)
2. Load once at module import via `json.load()` — lazy load on first use
3. Add `data/tickers_version.txt` for version tracking
4. Build script to sync from NSE Sentiment Analyzer if needed

**Expected Impact:**
- `engine/ticker_resolver.py` drops from 939 → ~200 lines (resolution logic only)
- Cold-start import time reduced (data loaded on demand, not at import)
- Ticker updates = edit JSON, no Python syntax risk, no code review needed for data changes
- Single source of truth shared with NSE Sentiment Analyzer

**Effort Estimate:** 1-2 hours (data extraction + lazy loader)

---

### #3 Bottleneck — Repeated Try/Except Pattern for Intelligence Modules (15+ instances)

**Location:** `app.py` lines 326-425 (also duplicated in cache load/store)

**Current Behavior:**
Every intelligence module (factor_report, macro_drivers, macro_scenarios, institutional_scores, early_warnings, recommendations, zscore, var_backtest, garch_var, pelve, opt_advanced) has its own 7-line try/except block:
```python
try:
    result = module_fn(args)
except Exception as e:
    logger.warning("Module name failed: {e}", e=e)
```

**Why It's Wasteful:**
- 15+ × 7 lines = 105+ lines of identical boilerplate
- Each block differs only by module name and function call
- Violates DRY — adding a new intelligence module requires copy-pasting the pattern
- Error handling is inconsistent (some log, some don't; some store None, some skip)
- Hard to add cross-cutting concerns (timeout, retry, metrics, circuit breaker)

**Proposed Change:**
Create `engine/intelligence_registry.py`:
```python
INTELLIGENCE_MODULES = [
    ("factor_report", compute_factor_exposures, ["prices", "weights", "benchmark_returns"]),
    (
        "macro_drivers",
        estimate_macro_sensitivities,
        ["portfolio_returns", "prices", "weights", "benchmark_returns"],
    ),
    # ...
]


def run_intelligence_modules(context: dict) -> dict:
    results = {}
    for name, fn, arg_keys in INTELLIGENCE_MODULES:
        try:
            args = {k: context[k] for k in arg_keys}
            results[name] = fn(**args)
        except Exception as e:
            logger.warning(f"{name} failed: {{e}}", e=e)
            results[name] = None
    return results
```

**Expected Impact:**
- 105 lines → 1 loop + registry definition (~30 lines net)
- Adding new module = 1 line in registry, not 7 in app.py
- Consistent error handling, logging, result storage
- Enables cross-cutting: timeout per module, metrics, circuit breaker
- Registry is testable independently

**Effort Estimate:** 2-3 hours (refactor + tests)

---

### Quick Wins (Under 1 Hour Each)

1. **Remove dead file `analyze_portfolios.py` (29 KB)** — appears to be a legacy script not used by app. Delete or move to `scripts/`.
2. **Delete `0` zero-byte file at repo root** — git artifact.
3. **Remove `sample-report.pdf`, `_test_header.pdf`, `test_portfolio_risk.pdf`, `test_final.pdf`, `test_output.txt`** — generated artifacts in root, should be in `.gitignore`/ignored or in `docs/showcase/`.
4. **Consolidate `requirements.txt` + `pyproject.toml`** — both list dependencies; keep only `pyproject.toml` (modern standard), generate `requirements.txt` via `uv pip compile` if needed for legacy tools.
5. **Cache `load_sector_map()`** — called every run in `app.py` line 227; sector map is static JSON, add `@functools.lru_cache`.

---

### What NOT to Do (Considered but Rejected)

| Idea | Why Rejected |
|------|--------------|
| Split `engine/` into subpackages (risk, optimization, etc.) | Current flat structure works; adds import complexity without clear benefit |
| Rewrite price fetching with async/await | `yfinance`/`nselib` are sync; async adds complexity without throughput gain (semaphore already limits concurrency) |
| Replace `diskcache` with Redis | Overkill for Streamlit Cloud free tier; `diskcache` works |
| Add GraphQL API layer | No consumer; Streamlit is the only frontend |
| Micro-frontend split for tabs | Tabs share session state heavily; not independent apps |

---

### Summary

| # | Bottleneck | Lines Affected | Effort | Impact |
|---|------------|----------------|--------|--------|
| 1 | `app.py` god module | 996 → ~150 | 4-6h | Architecture compliance, testability, maintainability |
| 2 | Hardcoded ticker map | 939 → ~200 | 1-2h | Startup latency, data/code separation, single source of truth |
| 3 | Repeated try/except | 105 → ~30 | 2-3h | DRY, extensibility, consistent error handling |

**Total effort:** ~7-11 hours for all three. Each is surgical (no logic changes) and independently valuable.