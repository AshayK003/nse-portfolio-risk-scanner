# AEOS Module 23 Audit — Quick Reference

## Critical (Must Fix Before Release)
| ID | Issue | File | Fix |
|----|-------|------|-----|
| C-01 | **No CI/CD pipeline** | — | Add `.github/workflows/ci.yml` (lint → typecheck → test) |
| C-02 | **Cache thread safety** | `data/cache.py` | Add `threading.Lock` around `diskcache` writes |

## High Priority (Within 2 Sprints)
| ID | Issue | File | Fix |
|----|-------|------|-----|
| H-01 | Non-deterministic fixture | `tests/conftest.py:38` | Use fixed `datetime(2024, 1, 1)` |
| H-02 | Optional deps untested | `engine/regime.py`, `optimization_advanced.py`, `delivery.py` | Add `@pytest.mark.optional` + CI matrix |
| H-03 | SQLite missing indexes | `storage/db.py` | Add indexes on `timestamp`, `portfolio_hash` |
| H-04 | nselib no timeout | `data/prices.py:101` | Wrap in thread with timeout |
| H-05 | Silent benchmark failure | `app.py:236-241` | Surface `st.warning()` to UI |

## Codebase Stats
- **Tests:** 355 total (192 core pass, 22 fail due to optional deps: cache + matplotlib)
- **Coverage:** ~90% on engine modules
- **LOC:** ~6,500 (engine + ui + data + storage)
- **Architecture:** Clean 4-layer (engine/ui/data/storage) with strict import boundaries

## Immediate Next Steps
1. **Run CI locally:** `ruff check . && ruff format . --check && python -m pytest tests/ -x -q`
2. **Create CI workflow** — copy template from `github-actions-cicd` skill
3. **Fix cache lock** — 5-line change in `data/cache.py`
4. **Push and verify** — GitHub Actions runs on PR

Full report: `reviews/AUDIT_REPORT.md`