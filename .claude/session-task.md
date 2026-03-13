# Autonomous Session: UCW (Universal Cognitive Wallet)

## Mission
Fix broken test suite, get the package installable, and harden the core module. This is pre-launch infrastructure — everything must work.

## Current State
- 6 tests collected, 5 errors during collection
- ALL errors are `ModuleNotFoundError: No module named 'ucw'` — package not installed in dev mode
- Has pyproject.toml, src/ layout
- Sovereign Sprint Briefing exists with full architecture docs

## Task List (execute in order)

### Phase 1: Fix Package Installation
1. Read `pyproject.toml` to understand the package structure
2. Install in dev mode: `pip install -e .` (or `pip install -e ".[dev]"` if extras exist)
3. Verify: `python3 -c "import ucw; print('OK')"`
4. Run `python3 -m pytest -q` — get all 6 tests to collect and run

### Phase 2: Fix Failing Tests
1. Run full test suite, catalog results
2. Fix any failures — likely stale imports, missing config, or DB setup
3. Target: all 6 tests passing

### Phase 3: Expand Test Coverage
Read the src/ucw/ directory structure and add tests for:
1. Core capture pipeline (sqlite, event storage)
2. UCW bridge (MCP transport)
3. CLI entry points
4. Protocol layer (JSON-RPC 2.0)
5. Any semantic layer processing

### Phase 4: Code Quality
1. Add ruff config to pyproject.toml if missing
2. Run `ruff check .` and fix all errors
3. Add type hints to public APIs
4. Ensure `python3 -m ucw --help` (or equivalent CLI) works

## Validation
```bash
pip install -e .              # Clean install
python3 -m pytest -q          # All tests pass
ruff check .                  # 0 lint errors
```

## Rules
- Don't modify the architecture — just make what exists work
- Commit after each phase
- Read UCW_SOVEREIGN_SPRINT_BRIEFING.md for context on what each component should do
