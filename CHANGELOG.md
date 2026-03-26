# Changelog

All notable changes to the Universal Cognitive Wallet (UCW) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
