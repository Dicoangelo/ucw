<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:2563eb,100:06b6d4&height=200&section=header&text=UCW&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=32&desc=Universal%20Cognitive%20Wallet&descAlignY=56&descSize=20" width="100%" />
</p>

<div align="center">
<img src="https://readme-typing-svg.demolab.com?font=Orbitron&weight=600&size=22&duration=3000&pause=1000&color=2563EB&center=true&vCenter=true&multiline=false&repeat=true&width=700&height=40&lines=Every+AI+conversation+captured.+Every+insight+connected." alt="Typing SVG" />
</div>

<p align="center">
<img src="https://img.shields.io/badge/Python-3.10+-2563eb?style=for-the-badge&logo=python&logoColor=white&labelColor=0d1117" />
<img src="https://img.shields.io/badge/SQLite-FTS5-06b6d4?style=for-the-badge&logo=sqlite&logoColor=white&labelColor=0d1117" />
<img src="https://img.shields.io/badge/MCP-Protocol-8b5cf6?style=for-the-badge&logo=anthropic&logoColor=white&labelColor=0d1117" />
<img src="https://img.shields.io/badge/Tests-565+-22c55e?style=for-the-badge&logo=pytest&logoColor=white&labelColor=0d1117" />
<img src="https://img.shields.io/badge/v0.4.0-Active-2563eb?style=for-the-badge&labelColor=0d1117" />
<a href="https://github.com/Dicoangelo"><img src="https://img.shields.io/badge/Dico_Angelo-Metaventions-06b6d4?style=for-the-badge&logo=github&logoColor=white&labelColor=0d1117" /></a>
</p>

<img src="https://user-images.githubusercontent.com/74038190/212284100-561aa473-3905-4a80-b561-0d28506553ee.gif" width="100%"/>

## What Is This?

UCW captures and connects your conversations across AI tools — Claude, ChatGPT, Cursor, Grok. Instead of losing context when you switch platforms, UCW **remembers everything and finds the connections you'd miss**. All data stays local in SQLite. No cloud. No subscriptions.

<img src="https://user-images.githubusercontent.com/74038190/212284115-f47cd8ff-2ffb-4b04-b5bf-4d1c14c0247f.gif" width="100%"/>

## Architecture

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#2563eb', 'edgeLabelBackground':'#1a1a2e', 'tertiaryColor': '#1a1a2e'}}}%%
flowchart TB
    subgraph Platforms["AI Platforms"]
        direction LR
        Claude["Claude Desktop/Code"]
        Cursor["Cursor IDE"]
        ChatGPT["ChatGPT"]
        Grok["Grok"]
    end

    subgraph UCW["UCW Engine"]
        direction TB
        MCP["MCP Server<br/>stdio protocol"]
        Capture["Capture Pipeline<br/>nanosecond timestamps"]
        Enrich["Enrichment<br/>intent · topic · coherence"]
        DB["SQLite + FTS5<br/>WAL mode · local only"]
        Embed["Embedding Cache<br/>sentence-transformers"]
    end

    subgraph Interface["User Interface"]
        direction LR
        CLI["14 CLI Commands"]
        Web["Web Dashboard<br/>port 7077"]
        Tools["23 MCP Tools<br/>Claude can call"]
    end

    Claude -->|live capture| MCP
    Cursor -->|live capture| MCP
    ChatGPT -->|import| DB
    Grok -->|import| DB
    MCP --> Capture --> Enrich --> DB
    DB --> Embed
    DB --> CLI
    DB --> Web
    DB --> Tools

    style Platforms fill:#1e3a5f,stroke:#2563eb,color:#fff
    style UCW fill:#1a1a2e,stroke:#06b6d4,color:#fff
    style Interface fill:#1e3a5f,stroke:#2563eb,color:#fff
```

## Project Structure

```
ucw/
├── src/ucw/
│   ├── cli.py              # 14 CLI commands (click)
│   ├── search.py            # FTS5 keyword + semantic vector search
│   ├── web.py               # Local web server (stdlib http.server)
│   ├── web_ui.py            # Embedded SPA (HTML/CSS/JS)
│   ├── dashboard.py         # Dashboard data aggregation
│   ├── config.py            # Configuration & paths
│   ├── demo.py              # Sample data generator
│   ├── errors.py            # Error hierarchy with hints
│   ├── db/
│   │   ├── sqlite.py        # CaptureDB, schema, WAL mode
│   │   ├── schema.sql       # Core schema (events, sessions, moments)
│   │   └── migrations/      # 001-007 incremental migrations
│   ├── server/
│   │   ├── server.py        # MCP protocol server
│   │   ├── bridge.py        # UCWBridgeAdapter (enrichment)
│   │   ├── embeddings.py    # sentence-transformers wrapper
│   │   └── router.py        # Tool routing
│   ├── tools/               # 23 MCP tools across 7 modules
│   │   ├── ucw_tools.py     # Capture stats, timeline, context
│   │   ├── coherence_tools.py  # Search, moments, arcs
│   │   ├── graph_tools.py   # Knowledge graph queries
│   │   ├── intelligence_tools.py  # Emergence, alerts
│   │   ├── temporal_tools.py  # Time-based patterns
│   │   ├── agent_tools.py   # Cross-agent memory, trust
│   │   └── proof_tools.py   # Hash chains, Merkle receipts
│   └── importers/           # ChatGPT, Cursor, Grok adapters
├── tests/                   # 565+ tests
├── visual_assets/           # Dashboard screenshots
└── pyproject.toml           # Hatch build, optional deps
```

<img src="https://user-images.githubusercontent.com/74038190/212284100-561aa473-3905-4a80-b561-0d28506553ee.gif" width="100%"/>

## Features

<table>
<tr>
<td width="33%" align="center">
<h3>Semantic Search</h3>
<b>Find anything across all your AI tools</b>
<p><code>ucw search "that auth conversation"</code> with FTS5 keyword + sentence-transformer embeddings. Cached vectors mean instant repeat queries.</p>
<code>FTS5</code> <code>BM25</code> <code>cosine similarity</code>
</td>
<td width="33%" align="center">
<h3>Live Capture</h3>
<b>Every message, automatically</b>
<p>MCP server captures every Claude conversation in real-time. Nanosecond timestamps, intent detection, topic extraction, coherence signals.</p>
<code>MCP</code> <code>stdio</code> <code>zero-latency</code>
</td>
<td width="33%" align="center">
<h3>Web Dashboard</h3>
<b>Your AI memory at a glance</b>
<p><code>ucw web</code> launches a local SPA with search, platform breakdown, knowledge graph, coherence moments. Dark/light themes.</p>
<code>localhost:7077</code> <code>no npm</code> <code>zero deps</code>
</td>
</tr>
<tr>
<td width="33%" align="center">
<h3>Knowledge Graph</h3>
<b>See how ideas connect</b>
<p>Entities extracted from conversations form a graph. Relationships emerge across platforms — concepts that link your Claude work to ChatGPT research.</p>
<code>entities</code> <code>relationships</code> <code>force-directed</code>
</td>
<td width="33%" align="center">
<h3>Coherence Detection</h3>
<b>Cross-platform insight moments</b>
<p>UCW detects when the same concept appears across different AI tools — the "aha" moments where your thinking converges.</p>
<code>cross-platform</code> <code>moments</code> <code>arcs</code>
</td>
<td width="33%" align="center">
<h3>Proof of Cognition</h3>
<b>Cryptographic receipts for your AI work</b>
<p>SHA-256 hash chains and Merkle trees prove when ideas were captured. Timestamp your intellectual property.</p>
<code>SHA-256</code> <code>Merkle</code> <code>immutable</code>
</td>
</tr>
</table>

## Quick Start

```bash
pip install ucw                    # Core (CLI + capture)
ucw init                           # Set up ~/.ucw/ and detect AI tools
ucw demo                           # Load 52 sample events to explore
ucw dashboard                      # See your AI memory overview
ucw search "authentication"        # Search across all conversations
ucw web                            # Launch web dashboard at localhost:7077
```

### Connect to Claude (live capture)

```bash
ucw mcp-config                     # Print the MCP config JSON
```

Paste into **Claude Desktop** (Settings > Developer > Edit Config) or **Claude Code** (`.claude/settings.json`).

### Optional extras

```bash
pip install "ucw[embeddings]"      # Semantic search (sentence-transformers)
pip install "ucw[ui]"              # Rich terminal dashboard
pip install "ucw[all]"             # Everything
```

### Import existing conversations

```bash
ucw import chatgpt ~/Downloads/conversations.json
ucw import cursor                  # Auto-detects Cursor workspace DB
ucw import grok ~/Downloads/grok-export.json
```

## Commands

| Command | Description |
|---------|-------------|
| `ucw init` | Set up UCW and detect installed AI tools |
| `ucw server` | Start the MCP server (used by Claude) |
| `ucw search QUERY` | Search conversations with `--platform`, `--after`, `--before`, `--semantic` |
| `ucw web` | Launch web dashboard at `localhost:7077` |
| `ucw dashboard` | Terminal dashboard with platform breakdown and topics |
| `ucw index` | Build/manage semantic search embedding cache |
| `ucw capture-test` | Verify the full capture pipeline is working |
| `ucw import <platform>` | Import from ChatGPT, Cursor, or Grok |
| `ucw demo` | Load sample data to explore features |
| `ucw status` | Quick database statistics |
| `ucw doctor` | Check installation health |
| `ucw repair` | Fix and optimize the database (VACUUM) |
| `ucw migrate` | Run database schema migrations |
| `ucw mcp-config` | Print Claude MCP configuration JSON |

## 23 MCP Tools

When connected to Claude, UCW provides 23 tools across 7 categories:

| Category | Tools | Purpose |
|----------|-------|---------|
| **Capture** | `capture_stats`, `timeline`, `session_context` | Session tracking and event replay |
| **Coherence** | `search`, `status`, `moments`, `scan`, `arcs` | Cross-platform insight detection |
| **Intelligence** | `emergence`, `event_stream`, `alerts` | Real-time pattern recognition |
| **Graph** | `knowledge_graph`, `entity_relationships` | Entity extraction and linking |
| **Temporal** | `time_patterns`, `decay_detection`, `activity_map` | Time-based analysis |
| **Agent** | `cross_agent_memory`, `trust_scoring` | Multi-agent coordination |
| **Proof** | `hash_chain`, `merkle_tree`, `receipt` | Cryptographic proof-of-cognition |

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Runtime** | Python 3.10+ | Zero-dependency core (only `click`) |
| **Storage** | SQLite + FTS5 | WAL mode, local-only, nanosecond timestamps |
| **Protocol** | MCP (stdio) | Model Context Protocol for Claude integration |
| **Search** | FTS5 + sentence-transformers | BM25 keyword + cosine similarity vectors |
| **Web** | stdlib `http.server` | Single-file SPA, no npm, no build step |
| **Embeddings** | sentence-transformers (optional) | Cached in SQLite BLOB, 1.5KB per event |
| **Testing** | pytest + ruff | 565+ tests, zero lint errors |

## Web Dashboard

<p align="center">
  <img src="visual_assets/ucw-dashboard-v040.png" width="48%" alt="UCW Dashboard — Light Theme" />
  <img src="visual_assets/ucw-dashboard-v040-dark.png" width="48%" alt="UCW Dashboard — Dark Theme" />
</p>

## Configuration

UCW stores everything in `~/.ucw/`. Override with environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `UCW_DATA_DIR` | `~/.ucw` | Data directory |
| `UCW_LOG_LEVEL` | `DEBUG` | Log level |
| `UCW_PLATFORM` | `claude-desktop` | Platform identifier |

## Requirements

- Python 3.10+
- SQLite 3.35+ (included with Python)

## Development

```bash
git clone https://github.com/Dicoangelo/ucw.git
cd ucw
pip install -e ".[dev]"
pytest                    # 565+ tests
ruff check .              # lint
ucw demo && ucw web       # visual smoke test
```

<details>
<summary><b>Build Log — v0.4.0</b></summary>

| Metric | v0.1.0 | v0.2.0 | v0.3.0 | v0.4.0 |
|--------|--------|--------|--------|--------|
| MCP Tools | 7 | 8 | 23 | 23 |
| CLI Commands | 3 | 4 | 10 | 14 |
| Tests | 63 | 153 | 469 | 565+ |
| Migrations | 0 | 0 | 5 | 7 |
| Importers | 0 | 0 | 3 | 3 |

**v0.4.0 highlights:**
- Semantic search (`ucw search`) with FTS5 + embedding cache
- Web dashboard (`ucw web`) — local SPA, dark/light themes
- Capture verification (`ucw capture-test`) — pipeline health check
- Cached coherence search (replaced brute-force re-embedding)

</details>

## Vision

```
┌─────────────────────────────────────────────────┐
│                                                 │
│   Every AI conversation you've ever had         │
│   is a data point in your cognitive portfolio.   │
│                                                 │
│   UCW captures the value.                       │
│   You own the equity.                           │
│                                                 │
└─────────────────────────────────────────────────┘
```

## License

MIT

<p align="center">
<a href="https://github.com/Dicoangelo/ucw"><img src="https://img.shields.io/badge/UCW-Universal_Cognitive_Wallet-2563eb?style=for-the-badge&labelColor=0d1117" /></a>
<a href="https://metaventionsai.com"><img src="https://img.shields.io/badge/Metaventions-AI-06b6d4?style=for-the-badge&labelColor=0d1117" /></a>
</p>

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:2563eb,100:06b6d4&height=120&section=footer" width="100%" />
</p>
