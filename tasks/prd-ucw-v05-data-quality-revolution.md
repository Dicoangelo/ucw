[PRD]
# PRD: UCW v0.5.0 — Data Quality Revolution

## Overview

UCW v0.4.0 has 37K+ real messages but the data quality is broken: 99% of topics are "coding", enrichment is keyword-matching, search returns low-quality snippets, and the dashboard shows nothing insightful. v0.5.0 makes the data actually useful by rebuilding the enrichment pipeline with local NLP, integrating OpenViking/Cohere for high-quality embeddings, and redesigning the dashboard to surface real insights from real conversations.

**The thesis:** UCW has the data (37K messages across 454 Claude Code sessions). The infrastructure works (search, dashboard, export, web UI). What's missing is the intelligence layer that turns raw messages into structured knowledge.

**Target persona:** The same AI power user, but now they have months of conversation history imported. They want to see what they've been working on, find specific conversations, and understand patterns in their AI usage.

## Goals

- Topic classification accuracy: from ~1% (everything is "coding") to 80%+ correct topic assignment
- Search relevance: first result for "FriendlyFace auth" should be about FriendlyFace authentication, not a random code snippet
- Dashboard insights: show real project breakdown, activity timeline, topic evolution over time
- Embedding quality: upgrade from sentence-transformers (384-dim) to Cohere embed-v4.0 (1024-dim) via OpenViking, with sentence-transformers as free fallback
- Auto-import: `ucw init` imports Claude Code sessions automatically, `ucw sync` keeps it current
- Import coverage: support ChatGPT, Cursor, Grok, and Claude Code — with auto-detection where possible
- Zero mandatory cost: everything works with free local models; Cohere/OpenViking is an optional upgrade

## Quality Gates

These commands must pass for every user story:
- `ruff check .` — Zero lint errors
- `python3 -m pytest tests/ -x -q` — All tests pass

For data quality stories, also include:
- Query real database: verify enrichment on actual imported data
- `sqlite3 ~/.ucw/cognitive.db "SELECT light_topic, COUNT(*) FROM cognitive_events WHERE is_noise=0 GROUP BY light_topic ORDER BY 2 DESC LIMIT 10"` — must show >5 distinct topics

For UI stories, also include:
- Manual verification: `ucw web` renders correctly in browser
- Screenshot captured via Chrome DevTools MCP for visual reference

## User Stories

### Epic 1: Smart Enrichment Pipeline

### US-001: Project-aware topic classifier
**Description:** As a user, I want my conversations automatically tagged by project so that the dashboard shows what I actually work on (FriendlyFace, CareerCoach, UCW, etc.) instead of "coding" for everything.

**Acceptance Criteria:**
- [ ] New `src/ucw/enrichment.py` module with `classify_topic(content, metadata)` function
- [ ] Extracts project name from: file paths (`/projects/products/friendlyface/`), git branches, session CWD, explicit mentions
- [ ] Falls back to domain classification (auth, deployment, frontend, backend, testing, database, devops, research) when no project detected
- [ ] Classification runs on import and on new MCP captures
- [ ] At least 10 distinct topics when run against the real 37K message database
- [ ] `python3 -m pytest tests/test_enrichment.py -x -q` — at least 15 tests covering: project extraction from paths, domain classification, edge cases, empty content

### US-002: Intent and action classifier
**Description:** As a user, I want each conversation tagged with what I was doing (debugging, building, refactoring, researching, reviewing) so that search and dashboard can filter by activity type.

**Acceptance Criteria:**
- [ ] `classify_intent(content, metadata)` function in `enrichment.py`
- [ ] Intent categories: `build`, `debug`, `refactor`, `research`, `review`, `deploy`, `configure`, `discuss`, `plan`
- [ ] Detection signals: error tracebacks → debug, "create/add/implement" → build, git operations → deploy, questions → research
- [ ] Returns confidence score (0-1) alongside intent label
- [ ] At least 8 tests covering each intent category

### US-003: Smart summary extraction
**Description:** As a user, I want each conversation to have a useful 1-line summary instead of raw content dumps, so search results and dashboard are readable.

**Acceptance Criteria:**
- [ ] `extract_summary(content, max_length=200)` function in `enrichment.py`
- [ ] For user messages: first substantive sentence (skip greetings, system prompts, tool results)
- [ ] For assistant messages: first sentence of actual response (skip tool calls, code blocks)
- [ ] Strips markdown formatting, XML tags, JSON blobs, file contents
- [ ] Returns clean human-readable text, not raw dumps
- [ ] `light_summary` field populated with this on import and capture
- [ ] At least 10 tests with real message samples

### US-004: Concept and entity extraction
**Description:** As a user, I want key concepts and entities (technologies, people, products) extracted from conversations so the knowledge graph has real data.

**Acceptance Criteria:**
- [ ] `extract_concepts(content)` returns list of `{name, type, confidence}` dicts
- [ ] Entity types: `project`, `technology`, `person`, `file`, `command`, `error`
- [ ] Extracts: project names from paths, npm/pip packages, file names, error types, person names (from @mentions, "asked John", etc.)
- [ ] Deduplicates: "react", "React", "ReactJS" → "React"
- [ ] At least 10 tests with real content samples

### US-005: Batch re-enrichment command
**Description:** As a user, I want `ucw enrich` to re-process all events with the new enrichment pipeline so my existing 37K messages get proper topics, intents, and summaries.

**Acceptance Criteria:**
- [ ] `ucw enrich` command added to CLI
- [ ] Processes all events where `light_topic = 'coding'` or `light_topic = 'general'` (the broken ones)
- [ ] Shows progress bar: "Enriching 35,000 events... [====] 100%"
- [ ] `ucw enrich --status` shows: total events, enriched, pending, topic distribution
- [ ] `ucw enrich --force` re-enriches all events (not just broken ones)
- [ ] Batch size of 1000 with periodic commits (don't lose progress on crash)
- [ ] Updates `light_topic`, `light_intent`, `light_summary`, `light_concepts` in DB
- [ ] At least 6 CLI tests

---

### Epic 2: Embedding Upgrade (OpenViking + Cohere)

### US-006: Cohere embedding provider via OpenViking
**Description:** As a user with OpenViking configured, I want UCW to use Cohere embed-v4.0 (1024-dim) for much better search quality, falling back to sentence-transformers if OpenViking is not available.

**Acceptance Criteria:**
- [ ] New `src/ucw/embeddings_provider.py` module with `get_provider()` factory
- [ ] `OpenVikingProvider`: calls OpenViking API (localhost:1933) for embeddings — uses Cohere embed-v4.0 (1024-dim)
- [ ] `SentenceTransformerProvider`: existing local model (384-dim) — zero cost fallback
- [ ] Provider auto-detected: if OpenViking is running → Cohere; else → sentence-transformers; else → keyword-only
- [ ] `embedding_cache` table stores `model` column — different providers coexist
- [ ] `ucw index --provider` shows which provider is active
- [ ] At least 8 tests (mock both providers, fallback logic, dimension handling)

### US-007: Hybrid search with reranking
**Description:** As a user, I want search results ranked by actual relevance using Cohere rerank-v3.5, not just cosine similarity.

**Acceptance Criteria:**
- [ ] `search()` in `search.py` gains optional reranking step
- [ ] If OpenViking available: keyword search → get top 50 → rerank with Cohere → return top N
- [ ] If no reranker: fall back to current BM25/cosine ranking
- [ ] Reranking is transparent to the user — just better results
- [ ] Search results include `rerank_score` when reranking is active
- [ ] At least 6 tests

### US-008: OpenViking bidirectional sync
**Description:** As a user, I want UCW events to flow into OpenViking so I can search my cognitive wallet through the OpenViking MCP tools and vice versa.

**Acceptance Criteria:**
- [ ] `ucw sync openviking` command pushes enriched events to `viking://resources/UCW/events/`
- [ ] Events stored with L0 (topic + summary) / L1 (full metadata) / L2 (content) tiering
- [ ] `ucw sync openviking --status` shows sync state: last sync, events synced, pending
- [ ] Incremental: only syncs events newer than last sync timestamp
- [ ] At least 5 tests

---

### Epic 3: Auto-Import & Sync

### US-009: Auto-import Claude Code on init
**Description:** As a new user, I want `ucw init` to automatically import my Claude Code sessions so the wallet is populated immediately without extra steps.

**Acceptance Criteria:**
- [ ] `ucw init` detects `~/.claude/projects/` and offers to import
- [ ] Shows estimated count: "Found 454 Claude Code sessions. Import? [Y/n]"
- [ ] Import runs with progress bar
- [ ] Skips if already imported (idempotent via content_hash)
- [ ] `ucw init --skip-import` flag to skip
- [ ] At least 4 tests

### US-010: `ucw sync` — unified import/update
**Description:** As a user, I want `ucw sync` to import new conversations from all configured sources so my wallet stays current.

**Acceptance Criteria:**
- [ ] `ucw sync` command imports new data from all detected sources
- [ ] Sources auto-detected: Claude Code sessions (always), ChatGPT export (if file provided previously), Cursor (if installed)
- [ ] `ucw sync --source claude-code` to sync only one source
- [ ] Tracks last sync timestamp per source — only processes new data
- [ ] Shows summary: "Synced 47 new messages from claude-code (last sync: 2h ago)"
- [ ] At least 6 tests

### US-011: ChatGPT auto-detect and import guide
**Description:** As a user, I want `ucw import chatgpt` to guide me through exporting my ChatGPT data if I haven't done it yet.

**Acceptance Criteria:**
- [ ] If no filepath given, prints step-by-step export instructions with URLs
- [ ] Auto-detects `~/Downloads/conversations.json` or `~/Downloads/*.zip` containing it
- [ ] Handles ZIP files (ChatGPT exports are ZIPs): auto-extracts conversations.json
- [ ] After import, shows topic breakdown of imported conversations
- [ ] At least 4 tests

---

### Epic 4: Dashboard Redesign

### US-012: Project breakdown dashboard card
**Description:** As a user, I want the web dashboard to show a breakdown of my work by project so I can see where my AI time goes.

**Acceptance Criteria:**
- [ ] New "Projects" card on web dashboard showing top 10 projects by event count
- [ ] Each project shows: name, event count, last activity time, percentage of total
- [ ] Bar chart visualization (CSS-only, no external deps)
- [ ] Data comes from `GET /api/dashboard` — add `projects` field to response
- [ ] Projects derived from `light_topic` where topic matches a project name
- [ ] At least 3 tests for the API endpoint

### US-013: Activity timeline with daily heatmap
**Description:** As a user, I want to see when I use AI tools across the week so I can understand my usage patterns.

**Acceptance Criteria:**
- [ ] New "Activity" card on web dashboard
- [ ] Shows events per day for the last 30 days as a heatmap grid (GitHub contribution style)
- [ ] Color intensity maps to event count (light → dark)
- [ ] Hover shows exact count and date
- [ ] Data comes from `GET /api/activity?days=30` — new endpoint returning `[{date, count}]`
- [ ] At least 3 tests for the API endpoint

### US-014: Search results with highlighted snippets
**Description:** As a user, I want search results to show relevant snippets with query terms highlighted, not raw data dumps.

**Acceptance Criteria:**
- [ ] Search results in web dashboard show clean summaries (from US-003)
- [ ] Query terms highlighted in bold within snippets
- [ ] Platform badge, project tag, and relative timestamp shown per result
- [ ] Results grouped or filterable by project
- [ ] Search bar supports `project:friendlyface query` filter syntax
- [ ] At least 4 tests for snippet highlighting and filter parsing

### US-015: Topic evolution chart
**Description:** As a user, I want to see how my work topics change over time so I can track focus shifts.

**Acceptance Criteria:**
- [ ] New "Topic Trends" card on web dashboard
- [ ] Shows top 5 topics as stacked area chart over the last 30 days
- [ ] Rendered with Canvas 2D (no external deps)
- [ ] Data comes from `GET /api/topics?days=30` — new endpoint
- [ ] At least 3 tests for the API endpoint

---

## Functional Requirements

- FR-1: All enrichment must run locally — no external API calls in the default path
- FR-2: OpenViking/Cohere integration is optional — everything works without it
- FR-3: `ucw enrich` must process 37K events in under 5 minutes (no embedding, just classification)
- FR-4: Search must return relevant results in <2 seconds for 50K event databases
- FR-5: Topic classification must produce at least 10 distinct topics from real data
- FR-6: Import must be idempotent — running twice produces no duplicates
- FR-7: Web dashboard must load in <1 second on localhost
- FR-8: All new CLI commands must include `--help` text
- FR-9: Embedding provider fallback chain: OpenViking/Cohere → sentence-transformers → keyword-only
- FR-10: Batch re-enrichment must commit every 1000 events (crash-safe)

## Non-Goals (Out of Scope)

- No cloud sync or remote storage
- No LLM-powered classification (Claude API calls for enrichment) — unless via existing subscription
- No real-time Claude Code capture via hooks (Claude Code sessions are imported, not streamed)
- No custom embedding model training
- No multi-user support
- No mobile app or Electron wrapper
- No conversation replay or chat-style UI

## Technical Considerations

- **OpenViking** is running at localhost:1933 with Cohere embed-v4.0 (1024-dim) and rerank-v3.5
- **Embedding dimensions differ**: Cohere is 1024-dim, sentence-transformers is 384-dim. The `embedding_cache` table must store `model` and handle mixed dimensions
- **Content is noisy**: Claude Code JSONL contains system reminders, tool results, XML tags, JSON blobs. Summary extraction must aggressively strip these
- **Project detection heuristic**: The JSONL `cwd` field contains the project path. The session directory name contains the project path. These are the strongest signals for topic/project classification
- **Re-enrichment is write-heavy**: 37K UPDATE statements. Use transactions with batch commits
- **Existing enrichment** in `ucw_bridge.py` must still work for live MCP capture. New `enrichment.py` runs on import and on `ucw enrich`
- **OpenViking URI mapping**: UCW events should go to `viking://resources/UCW/events/{project}/{date}/` with L0/L1/L2 tiering

## Success Metrics

- Topic distribution: ≥10 distinct topics in real data (currently 1)
- Search precision: top-3 results for "FriendlyFace auth" all relate to FriendlyFace authentication
- Dashboard load: <1 second with 37K events
- Enrichment speed: 37K events enriched in <5 minutes
- Test count: 650+ (up from 582)
- Zero new mandatory dependencies

## Open Questions

- Should `ucw sync` run on a cron/launchd schedule, or only on manual invocation?
- Should re-enrichment update the FTS5 index automatically, or require `ucw index --rebuild`?
- Should the OpenViking sync be push-only (UCW → Viking) or bidirectional (Viking search results show in UCW dashboard)?
[/PRD]
