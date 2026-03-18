# Changelog

All notable changes to the Universal Cognitive Wallet (UCW) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
