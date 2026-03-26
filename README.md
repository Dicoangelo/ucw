# UCW — Universal Cognitive Wallet

> Your AI memory, unified. Every conversation captured. Every insight connected.

## What UCW Does

UCW captures and connects your conversations across AI tools — Claude, ChatGPT, Cursor, Grok. Instead of losing context when you switch tools, UCW remembers everything and finds the connections you'd miss.

- **Capture everything** — Every AI conversation, automatically
- **Search across tools** — Find that insight from last week, regardless of which AI you used
- **See patterns** — Discover connections between conversations across platforms
- **Own your data** — Everything stored locally in SQLite. No cloud. No subscriptions (yet).

## Quick Start

```bash
pip install ucw
ucw init          # Set up UCW and detect your AI tools
ucw demo          # Load sample data to explore
ucw dashboard     # See your AI memory at a glance
```

## Connect to Claude

```bash
ucw mcp-config    # Get the config JSON
```

Then paste into Claude Desktop (Settings > Developer > Edit Config) or Claude Code (`.claude/settings.json`).

For semantic search across your conversations:

```bash
pip install "ucw[embeddings]"   # adds sentence-transformers + numpy
```

## Import Your History

```bash
ucw import chatgpt ~/Downloads/conversations.json
ucw import cursor
ucw import grok ~/Downloads/grok-export.json
```

## Commands

| Command | Description |
|---------|-------------|
| `ucw init` | Set up UCW and detect your AI tools |
| `ucw server` | Start the MCP server (used by Claude) |
| `ucw dashboard` | View your AI memory overview |
| `ucw demo` | Load sample data to explore features |
| `ucw import <platform>` | Import conversations from other AI tools |
| `ucw status` | Quick database statistics |
| `ucw doctor` | Check installation health |
| `ucw repair` | Fix and optimize the database |
| `ucw migrate` | Run database migrations |
| `ucw mcp-config` | Print Claude MCP configuration |

## 23 MCP Tools

When connected to Claude, UCW provides 23 tools across 7 categories:

- **Capture** — Stats, timeline, session context
- **Coherence** — Search, status, moments, scan, arcs
- **Intelligence** — Emergence detection, event stream, alerts
- **Graph** — Knowledge graph queries, entity relationships
- **Temporal** — Time-based analysis, pattern detection
- **Agent** — Cross-agent memory, trust scoring
- **Proof** — Cryptographic proof-of-cognition, hash chains, Merkle receipts

## How It Works

```
You <-> Claude Desktop/Code
         |
    UCW MCP Server
    |-- Capture      (every message, nanosecond timestamps)
    |-- Enrichment   (intent, topic, concepts, coherence signals)
    |-- Storage      (SQLite, WAL mode, local-only)
    '-- Tools        (23 MCP tools Claude can call)
```

UCW runs as an MCP server. Claude sends messages over STDIO, UCW captures and enriches every one, then passes them through. Zero latency impact — database and embeddings initialize in the background.

## Configuration

UCW stores data in `~/.ucw/` by default. Override with environment variables or `~/.ucw/config.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `UCW_DATA_DIR` | `~/.ucw` | Data directory |
| `UCW_LOG_LEVEL` | `DEBUG` | Log level |
| `UCW_PLATFORM` | `claude-desktop` | Platform identifier |

## Requirements

- Python 3.10+
- SQLite 3.35+
- Optional: `pip install ucw[ui]` for rich dashboard
- Optional: `pip install ucw[embeddings]` for semantic search

## Development

```bash
git clone https://github.com/Dicoangelo/ucw.git
cd ucw
pip install -e ".[dev]"
pytest               # run test suite
ruff check .         # lint
```

## License

MIT
