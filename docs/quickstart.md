# UCW Quickstart

Get UCW running in 5 minutes.

## 1. Install

```bash
pip install ucw
```

This installs UCW and its dependencies (sentence-transformers, numpy, click).

**Note:** The first time UCW embeds an event, it downloads the SBERT model (~90MB). This happens in the background and doesn't block the MCP handshake.

## 2. Initialize

```bash
ucw init
```

This creates:
- `~/.ucw/` — Data directory
- `~/.ucw/logs/` — Log files
- `~/.ucw/config.env` — Configuration (edit as needed)

## 3. Get MCP Config

```bash
ucw mcp-config
```

This prints a JSON snippet like:

```json
{
  "mcpServers": {
    "ucw": {
      "command": "/path/to/ucw",
      "args": ["server"]
    }
  }
}
```

## 4. Add to Claude

**Claude Desktop:**
1. Open Settings > Developer > Edit Config
2. Add the JSON from step 3

**Claude Code:**
1. Add to `.claude/settings.json` or `~/.claude/settings.json`

Restart Claude after adding the config.

## 5. Verify

Have a conversation with Claude, then check:

```bash
ucw status
```

You should see events being captured:

```
UCW Status
========================================
Events:   24
Sessions: 1
Bytes:    12,847

Top Topics:
  coding: 8
  general: 6
  mcp_protocol: 5
  database: 3
  ucw: 2

Gut Signals:
  routine: 18
  interesting: 4
  breakthrough_potential: 2
```

## Using UCW Tools in Claude

Once connected, you can ask Claude to use UCW tools:

- "Show me my capture stats" → calls `ucw_capture_stats`
- "Show my recent activity timeline" → calls `ucw_timeline`
- "Scan for emergence patterns" → calls `detect_emergence`
- "Search my conversations for database design" → calls `coherence_search`

## Troubleshooting

### SBERT model download

The embedding model downloads on first use. If you're behind a firewall:

```bash
# Pre-download the model
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Permission issues

Ensure `~/.ucw/` is writable:

```bash
chmod -R 755 ~/.ucw
```

### Check logs

```bash
tail -f ~/.ucw/logs/ucw.log
```

### Database location

The SQLite database is at `~/.ucw/cognitive.db`. You can query it directly:

```bash
sqlite3 ~/.ucw/cognitive.db "SELECT COUNT(*) FROM cognitive_events"
```
