# Changelog

All notable changes to the Universal Cognitive Wallet (UCW) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.4.0] - 2026-03-26
### Added
- Semantic search: `ucw search "query"` with FTS5 keyword + sentence-transformer embeddings
- Embedding cache in SQLite (embed once, search forever) with `ucw index` management
- Web dashboard: `ucw web` launches local SPA on port 7077 with dark/light themes
- Dashboard features: search bar, platform breakdown, topic chips, knowledge graph visualization, coherence moments timeline, capture health monitoring
- Capture verification: `ucw capture-test` validates full pipeline health
- `ucw index --status` and `ucw index --rebuild` for embedding cache management
- Database migrations: 006 (FTS5 virtual table), 007 (embedding cache)
- Dashboard capture health: events 24h/7d, last capture age, active platforms
- 4 new CLI commands (10 → 14 total)
- Test coverage expanded from 469 to 565 tests

### Changed
- Coherence search now uses cached embeddings instead of brute-force re-embedding
- Web server binds to 127.0.0.1 only (local access, no network exposure)
- Auto port fallback: if 7077 is busy, tries up to port+10

## [0.3.0] - 2026-03-25
### Added
- 15 new MCP tools across 5 modules (8 → 23 total):
  - Knowledge graph: entity extraction, relationship mapping, queries
  - Real-time intelligence: event streaming, alerting, thread linking
  - Agent integration: cross-agent memory, trust scoring, context handoff
  - Temporal analysis: time-based patterns, decay detection, activity maps
  - Proof-of-cognition: hash chains, Merkle trees, cryptographic receipts
- Import adapters: `ucw import chatgpt`, `ucw import cursor`, `ucw import grok`
- Rich CLI dashboard: `ucw dashboard` with platform breakdown and topics
- Demo data: `ucw demo` loads 52 sample events across 3 platforms
- Health tools: `ucw doctor` diagnostics, `ucw repair` with VACUUM
- Database migrations system with 5 schema migrations
- Error hierarchy (UCWError) with actionable messages and hints
- 6 new CLI commands (4 → 10 total)
- Test coverage expanded from 153 to 469 tests

### Changed
- `ucw init` now detects installed AI tools and shows import suggestions
- README rewritten for external users with market language
- pyproject.toml: optional dependency groups (ui, embeddings, all, dev)
- Tool modules now show helpful hints when DB is not ready
- Version bumped to 0.3.0

## [2026-03-17]
### Changed
- Upgrade GitHub Actions for Node.js 24 compatibility

## [2026-03-15]
### Changed
- Remove unused `embed_texts()` and `_PROTOCOL_METHODS`

## [2026-03-13]
### Added
- Cross-platform coherence detection with `coherence_moments` table
- UCWBridgeAdapter and server setup tests (133 total)
- Router and embeddings tests, hardened CI pipeline
- Expanded test coverage from 63 to 153 tests
- Ruff linter config with all lint errors resolved
- `setup.sh` for lightweight installation

### Changed
- Release UCW v0.2.0 — lightweight install, robust search fallback
- Make sentence-transformers optional dependency

### Fixed
- Update tool count to 8 (add `cross_platform_coherence` to docs/tests)

## [2026-02-19]
### Added
- EditorConfig and CI/CD workflow

## [2026-02-07]
### Added
- Live MCP protocol integration test
- UCW v0.1.0 — Universal Cognitive Wallet initial release
