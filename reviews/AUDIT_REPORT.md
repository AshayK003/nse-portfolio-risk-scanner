# reviews/AUDIT_REPORT.md — AEOS Module 23: Comprehensive Codebase Auditor

## Project: NSE Portfolio Risk Scanner
## Audit Date: 2026-08-17
## Auditor: AEOS M23 (Comprehensive Codebase Auditor)
## Overall Health Score: **76/100** 🟡

---

### Executive Summary

The NSE Portfolio Risk Scanner is a **functional, well-tested, production-deployed** Streamlit application for institutional-grade portfolio risk analysis. It successfully computes VaR/CVaR, Monte Carlo simulation, factor decomposition, HMM regime detection, HRP optimization, Altman Z-Score, GARCH VaR, and more — all with 387 passing tests.

**Critical strengths:**
- Pure engine architecture (zero Streamlit in engine/, zero business logic in ui/)
- 387 tests passing, good coverage of core math
- Defensive coding: every intelligence module guarded by try/except
- Multi-tier caching (L1/L2/L3) for price data resilience
- AGPL v3 with open-source ethos

**Critical risks (blocking release-quality):**
1. **app.py is a 996-line god module** — violates declared architecture, untestable computation
2. **Hardcoded 31 KB ticker map in Python module** — startup latency, maintenance burden
3. **15+ repeated try/except boilerplate** — DRY violation, inconsistent error handling

**Release recommendation:** **CONDITIONAL PASS** — ship with M10 bottlenecks tracked for next sprint. No critical security/reliability blockers.

---

### 28-Dimension Scores

| # | Dimension | Score | Status | Notes |
|---|-----------|-------|--------|-------|
| **Architecture (5)** |
| 1 | Module cohesion | 78 | 🟡 | Engine flat but cohesive; app.py violates separation |
| 2 | Coupling | 82 | 🟡 | Engine→UI one-way; but app.py couples everything |
| 3 | API design | 85 | 🟢 | Pure functions, dataclasses, consistent signatures |
| 4 | Error handling | 75 | 🟡 | Try/except everywhere but inconsistent; no circuit breaker |
| 5 | Configuration | 88 | 🟢 | env-driven, profiles, no hardcoded secrets |
| **Reliability (4)** |
| 6 | Edge cases | 80 | 🟢 | Empty states, NaN guards, validation warnings |
| 7 | Concurrency | 65 | 🟡 | ThreadPoolExecutor + Semaphore; no deadlock analysis |
| 8 | Retry/backoff | 45 | 🔴 | No retry logic on yfinance/nselib calls |
| 9 | Graceful degradation | 85 | 🟢 | Each module try/except → None, UI shows info |
| **Security (4)** |
| 10 | Input validation | 90 | 🟢 | CSV column aliases, quantity/ticker validation |
| 11 | Auth/authz | N/A | 🟢 | No auth (public tool) — correctly N/A |
| 12 | Secrets management | 95 | 🟢 | No secrets in code; .env gitignored |
| 13 | Dependency vulnerabilities | 82 | 🟢 | pillow>=12.3.0 fixed; uv.lock pinned |
| **Performance (3)** |
| 14 | Query efficiency | 80 | 🟢 | Vectorized pandas/numpy; no N+1 |
| 15 | Caching | 88 | 🟢 | 3-tier (L1 LRU, L2 diskcache, L3 network) |
| 16 | Bundle/payload size | 85 | 🟢 | Minimal deps; no heavy frontend bundles |
| **Testing (5)** |
| 17 | Coverage | 78 | 🟡 | 387 tests; core math covered; UI/integration light |
| 18 | Test quality | 82 | 🟢 | Meaningful assertions, parametrized, fixtures |
| 19 | Fixture hygiene | 75 | 🟡 | Some shared session state in tests |
| 20 | CI integration | 95 | 🟢 | GitHub Actions: lint → format → test → cov |
| 21 | Speed | 70 | 🟡 | ~35s full suite; Monte Carlo dominates |
| **CI/CD (3)** |
| 22 | Pipeline completeness | 90 | 🟢 | Ruff + format + pytest + coverage |
| 23 | Artifact management | 60 | 🟡 | No versioned releases; manual version bump |
| 24 | Deployment safety | 70 | 🟡 | Streamlit Cloud only; no canary/rollback |
| **Technical Debt (4)** |
| 25 | Dead code | 65 | 🔴 | analyze_portfolios.py, zero-byte file, 5 PDFs in root |
| 26 | Documentation coverage | 80 | 🟢 | README + CHANGELOG + CONTRIBUTING + docstrings |
| 27 | TODO density | 75 | 🟡 | Few TODOs in code; some stale comments |
| 28 | Dependency freshness | 82 | 🟢 | uv.lock recent; minor lag on optional deps |

---

### Critical Findings (Score < 40)

**None.** All dimensions score ≥ 45.

### High-Priority Findings (Score 40-60)

| Dimension | Issue | Remediation |
|-----------|-------|-------------|
| 8. Retry/backoff | Network calls to yfinance/nselib have no retry — transient failures surface as user errors | Add `tenacity` or stdlib retry with exponential backoff in `data/prices.py` |
| 25. Dead code | `analyze_portfolios.py` (29 KB), `0` file, 5 PDF artifacts in root | Delete or move to `scripts/`/`.gitignore` |
| 7. Concurrency | ThreadPoolExecutor + Semaphore(5) but no deadlock analysis; L2 cache uses threading.Lock | Document concurrency model; consider `anyio` for structured concurrency |

### Improvement Suggestions (Score 60-80)

| Dimension | Suggestion |
|-----------|------------|
| 1. Module cohesion | Extract `app.py` computation/rendering per M10 #1 |
| 2. Coupling | Intelligence registry per M10 #3 |
| 4. Error handling | Circuit breaker pattern for external APIs |
| 17. Coverage | Add integration tests for tab rendering (AppTest) |
| 21. Speed | Profile Monte Carlo (10K paths); consider reducing default or caching |
| 23. Artifact management | Semantic versioning + GitHub Releases automation |
| 24. Deployment safety | Document Streamlit Cloud rollback procedure |
| 27. TODO density | Audit and clean stale comments |

---

### Remediation Roadmap

#### Phase 1 — Immediate (Next Sprint)
- [ ] **M10 #1**: Extract `app.py` → `engine/compute.py` + `ui/render.py` (4-6h)
- [ ] **M10 #2**: Move ticker map to `data/tickers.json` + lazy load (1-2h)
- [ ] **M10 #3**: Intelligence registry to eliminate try/except boilerplate (2-3h)
- [ ] **Dim 25**: Remove dead files from root (`analyze_portfolios.py`, `0`, 5 PDFs)

#### Phase 2 — Next Quarter
- [ ] **Dim 8**: Add retry/backoff with `tenacity` to `data/prices.py`
- [ ] **Dim 17/21**: Add AppTest integration tests; profile Monte Carlo speed
- [ ] **Dim 23**: Automate version bump + GitHub Release on tag push
- [ ] **Dim 24**: Document Streamlit Cloud deployment/rollback runbook

#### Phase 3 — Future
- [ ] **Dim 7**: Structured concurrency with `anyio` (if Python 3.11+)
- [ ] **Dim 4**: Circuit breaker for yfinance/nselib
- [ ] Consider splitting `engine/` into subpackages if module count grows >25

---

### Trend Tracking

| Audit | Date | Overall Score | Critical | High | Notes |
|-------|------|---------------|----------|------|-------|
| v0.17.5 | 2026-08-16 | ~72 | 0 | 2 | Pre-feedback merge |
| v0.18.0 | 2026-08-17 | **76** | 0 | 3 | Post-feedback; M10 bottlenecks identified |

**Trend:** ↗️ Improving. Score +4 from v0.17.5 due to feedback fixes (ticker autocomplete, fundamentals, news, template). M10 bottlenecks are pre-existing architectural debt now formally tracked.

---

### Notes for Next Audit

- Verify M10 bottlenecks resolved (app.py < 200 lines, ticker map externalized, registry exists)
- Check retry/backoff implementation on price fetching
- Confirm dead files removed from root
- Re-score dimensions 1, 2, 3, 4, 8, 17, 21, 23, 24, 25