# Autonomous Session: ucw

## Mission
Automated quality sweep — fix lint, resolve TODOs, expand tests, clean dead code.

## Current State (from automated recon)
- **Stack:** python
- **Files:** 33
- **Tests:** 0 (0 passing, 0 failing)
- **Lint errors:** 0
- **TODOs:** 0
- **Build:** unknown
- **Directories:** docs, src, tests

## WARNINGS (read before starting)
- **not_installed:** Package not installed — run pip install -e . ()

## Task Phases (execute in order)

### Phase 1: Expand Test Coverage
- Identify untested modules
- Add tests for core functionality
- Run `python3 -m pytest -q` after each batch
- Target: increase from 0 tests

### Phase 2: Dead Code Cleanup
- Find unused exports, imports, and variables
- Remove dead code paths
- Verify build still passes after cleanup

## Validation (run after each phase)
```bash
python3 -m pytest -q    # All tests pass
ruff check .            # 0 lint errors
```

## Rules
- Don't break existing tests
- Commit after each completed phase with descriptive message
- If a TODO requires external service setup, stub it with a clear interface and skip