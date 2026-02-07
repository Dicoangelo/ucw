# UCW — Universal Cognitive Wallet

Capture every AI conversation with perfect fidelity. Every byte. Every insight. Every pattern.

UCW is an MCP server that sits between you and Claude, capturing every message with semantic enrichment. Each event gets three layers:

- **Data** — What was said (raw content, tokens, method)
- **Light** — What it means (intent, topic, concepts, summary)
- **Instinct** — What it signals (coherence potential, emergence indicators, gut signal)

## Quickstart

```bash
pip install ucw
ucw init
ucw mcp-config  # prints the JSON to add to Claude
```

Add the output to your Claude settings, restart Claude, and every conversation is captured.

## How It Works

```
You ←→ Claude Desktop/Code
         ↕
    UCW MCP Server
    ├── Transport    (raw STDIO, every byte)
    ├── Protocol     (JSON-RPC 2.0 validation)
    ├── Router       (method dispatch)
    ├── Capture      (nanosecond timestamps, turn tracking)
    ├── UCW Bridge   (Data/Light/Instinct enrichment)
    └── SQLite DB    (persistent, WAL mode)
```

UCW runs as an MCP server. Claude sends messages over STDIO, UCW captures and enriches every one, then passes them through. Zero latency impact on the handshake — database and embeddings initialize in the background.

## MCP Tools (7)

| Tool | Description |
|------|-------------|
| `ucw_capture_stats` | Session + all-time capture statistics |
| `ucw_timeline` | Chronological event timeline with filters |
| `detect_emergence` | Scan for breakthrough signals and concept clusters |
| `coherence_status` | Engine status: events, sessions, signals |
| `coherence_moments` | High-coherence events with emergence indicators |
| `coherence_search` | Semantic similarity search across all events |
| `coherence_scan` | Pattern scan with topic/intent/signal breakdown |

## CLI Commands

```bash
ucw init        # Create ~/.ucw/ and generate config
ucw server      # Start MCP server (stdio mode)
ucw status      # Show database stats
ucw mcp-config  # Print Claude config JSON
```

## Configuration

UCW stores data in `~/.ucw/` by default. Override with environment variables or `~/.ucw/config.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `UCW_DATA_DIR` | `~/.ucw` | Data directory |
| `UCW_LOG_LEVEL` | `DEBUG` | Log level |
| `UCW_PLATFORM` | `claude-desktop` | Platform identifier |

## Architecture

```
src/ucw/
├── cli.py                 # Click CLI (init, server, status, mcp-config)
├── config.py              # Unified configuration
├── server/
│   ├── server.py          # Main orchestrator
│   ├── transport.py       # Raw STDIO transport
│   ├── protocol.py        # JSON-RPC 2.0
│   ├── router.py          # Method dispatch
│   ├── capture.py         # Perfect capture engine
│   ├── ucw_bridge.py      # Semantic layer extraction
│   ├── embeddings.py      # SBERT embeddings
│   └── logger.py          # File-only logging
├── db/
│   ├── sqlite.py          # SQLite storage (WAL mode)
│   └── schema.sql         # PostgreSQL schema (v1.1)
└── tools/
    ├── ucw_tools.py       # 3 capture tools
    └── coherence_tools.py # 4 coherence tools
```

## The Three Layers

Every captured event is enriched with UCW semantic layers:

**Data Layer** — The raw facts
- Method, parameters, result content
- Token estimates, byte counts

**Light Layer** — The meaning
- Intent classification (search, create, analyze, retrieve, execute)
- Topic detection (ucw, database, ai_agents, research, coding, mcp_protocol)
- Concept extraction
- Content summary

**Instinct Layer** — The signal
- Coherence potential (0.0 - 1.0)
- Emergence indicators (high_coherence_potential, concept_cluster, meta_cognitive)
- Gut signal (routine, interesting, breakthrough_potential)

## Development

```bash
git clone https://github.com/Dicoangelo/ucw.git
cd ucw
pip install -e ".[dev]"
pytest
```

## Roadmap

- **v0.1** — MCP server + 7 tools + SQLite + SBERT (this release)
- **v0.2** — Cross-platform capture adapters (ChatGPT, Cursor, Grok)
- **v0.3** — Coherence engine with cross-platform alignment detection
- **v0.4** — PostgreSQL backend with pgvector similarity search
- **v1.0** — Full UCW with real-time coherence dashboard

## License

MIT
