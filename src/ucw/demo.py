"""
UCW Demo — Generate realistic sample AI conversations for exploring UCW features.
"""

import random
import sqlite3
import time
import uuid
from pathlib import Path

from ucw.config import Config

DEMO_CONVERSATIONS = [
    # Claude conversations
    {
        "platform": "claude-desktop",
        "topic": "python",
        "messages": [
            {"role": "user", "content": "How do I use async/await in Python?"},
            {
                "role": "assistant",
                "content": (
                    "Use asyncio: define async handlers, run with"
                    " asyncio.run() as entry point."
                ),
            },
            {"role": "user", "content": "Handling concurrent connections?"},
            {
                "role": "assistant",
                "content": (
                    "Use asyncio.gather() or create_task()."
                    " Each MCP client gets its own session."
                ),
            },
        ],
    },
    {
        "platform": "claude-desktop",
        "topic": "architecture",
        "messages": [
            {"role": "user", "content": "Should I use DI for plugins?"},
            {
                "role": "assistant",
                "content": (
                    "DI works well. Use a registry where plugins"
                    " declare capabilities and dependencies."
                ),
            },
            {"role": "user", "content": "Plugin inter-dependencies?"},
            {
                "role": "assistant",
                "content": (
                    "Topological sort ensures correct load order."
                    " Detect cycles early, fail fast."
                ),
            },
        ],
    },
    # ChatGPT conversations
    {
        "platform": "chatgpt",
        "topic": "machine-learning",
        "messages": [
            {"role": "user", "content": "Explain transformer attention"},
            {
                "role": "assistant",
                "content": (
                    "Attention computes weighted relationships"
                    " between tokens via Q, K, V matrices."
                ),
            },
            {"role": "user", "content": "Multi-head vs single-head?"},
            {
                "role": "assistant",
                "content": (
                    "Multi-head runs parallel attention ops,"
                    " each learning different patterns."
                ),
            },
            {"role": "user", "content": "Attention vs memory in NNs?"},
            {
                "role": "assistant",
                "content": (
                    "Attention is soft addressing over memory."
                    " NTMs formalize this concept."
                ),
            },
        ],
    },
    {
        "platform": "chatgpt",
        "topic": "data-science",
        "messages": [
            {"role": "user", "content": "Handle missing data in pandas?"},
            {
                "role": "assistant",
                "content": (
                    "Use dropna(), fillna(), interpolate(),"
                    " or KNN imputation."
                ),
            },
        ],
    },
    # Cursor conversations
    {
        "platform": "cursor",
        "topic": "debugging",
        "messages": [
            {"role": "user", "content": "Component re-renders every keystroke"},
            {
                "role": "assistant",
                "content": (
                    "Wrap callback in useCallback, memoize with"
                    " React.memo(). Stabilize props."
                ),
            },
            {"role": "user", "content": "useMemo deps keep changing?"},
            {
                "role": "assistant",
                "content": (
                    "You're creating a new object each render."
                    " Extract to a ref instead."
                ),
            },
        ],
    },
    {
        "platform": "cursor",
        "topic": "typescript",
        "messages": [
            {"role": "user", "content": "Type a generic record function?"},
            {
                "role": "assistant",
                "content": (
                    "Use Record<string, T> or a generic"
                    " constraint like <T extends Record<...>>."
                ),
            },
            {"role": "user", "content": "Conditional return types?"},
            {
                "role": "assistant",
                "content": (
                    "Use conditional types with infer."
                    " T extends Promise<infer U> ? U : T."
                ),
            },
        ],
    },
    {
        "platform": "claude-desktop",
        "topic": "database",
        "messages": [
            {"role": "user", "content": "SQLite WAL vs rollback journal?"},
            {
                "role": "assistant",
                "content": (
                    "WAL for concurrent reads. Rollback journal"
                    " for single-writer scenarios."
                ),
            },
            {"role": "user", "content": "WAL with multiple writers?"},
            {
                "role": "assistant",
                "content": (
                    "One writer at a time, others queue."
                    " Use BEGIN IMMEDIATE to fail fast."
                ),
            },
        ],
    },
    {
        "platform": "chatgpt",
        "topic": "career",
        "messages": [
            {"role": "user", "content": "Prepare for system design interview?"},
            {
                "role": "assistant",
                "content": (
                    "Focus on scalability, availability, consistency."
                    " Practice architecture diagrams."
                ),
            },
            {"role": "user", "content": "Behavioral questions for senior roles?"},
            {
                "role": "assistant",
                "content": (
                    "Use STAR format. Prepare stories about conflict,"
                    " technical decisions, mentoring."
                ),
            },
        ],
    },
    {
        "platform": "cursor",
        "topic": "testing",
        "messages": [
            {"role": "user", "content": "Mock async function in pytest?"},
            {
                "role": "assistant",
                "content": (
                    "Use AsyncMock or pytest-asyncio."
                    " Patch the target module, not source."
                ),
            },
            {"role": "user", "content": "Testing SQLite in-memory DBs?"},
            {
                "role": "assistant",
                "content": (
                    "Use ':memory:' for speed. Use shared cache"
                    " for multi-connection tests."
                ),
            },
        ],
    },
    {
        "platform": "claude-desktop",
        "topic": "security",
        "messages": [
            {"role": "user", "content": "OWASP top 10 for 2024?"},
            {
                "role": "assistant",
                "content": (
                    "Broken access control, crypto failures,"
                    " injection, insecure design, SSRF."
                ),
            },
        ],
    },
    {
        "platform": "chatgpt",
        "topic": "python",
        "messages": [
            {"role": "user", "content": "What's new in Python 3.12?"},
            {
                "role": "assistant",
                "content": (
                    "Type params (PEP 695), per-interpreter GIL,"
                    " better errors, f-string grammar."
                ),
            },
            {"role": "user", "content": "Per-interpreter GIL benefits?"},
            {
                "role": "assistant",
                "content": (
                    "Each sub-interpreter gets its own GIL,"
                    " enabling true CPU parallelism."
                ),
            },
        ],
    },
    {
        "platform": "claude-desktop",
        "topic": "devops",
        "messages": [
            {"role": "user", "content": "Docker Compose vs Kubernetes?"},
            {
                "role": "assistant",
                "content": (
                    "Compose for dev/small deploys. K8s when you"
                    " need auto-scaling and rolling updates."
                ),
            },
            {"role": "user", "content": "When to migrate to K8s?"},
            {
                "role": "assistant",
                "content": (
                    "At 5+ services, zero-downtime needs, or"
                    " unpredictable traffic patterns."
                ),
            },
        ],
    },
    {
        "platform": "cursor",
        "topic": "git",
        "messages": [
            {"role": "user", "content": "Remove a committed secret?"},
            {
                "role": "assistant",
                "content": (
                    "Use git filter-repo. Rotate the secret"
                    " immediately -- clones are unaffected."
                ),
            },
        ],
    },
    {
        "platform": "chatgpt",
        "topic": "networking",
        "messages": [
            {"role": "user", "content": "Difference between TCP and UDP?"},
            {
                "role": "assistant",
                "content": (
                    "TCP: reliable, ordered delivery."
                    " UDP: connectionless, no guarantees."
                ),
            },
            {"role": "user", "content": "When to choose UDP over TCP?"},
            {
                "role": "assistant",
                "content": (
                    "For low-latency needs: gaming, streaming,"
                    " VoIP where packet loss is OK."
                ),
            },
        ],
    },
]


def load_demo_data(db_path=None):
    """Load sample data into the database. Returns the number of events inserted."""
    db_path = db_path or Config.DB_PATH
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=wal")

    # Ensure base schema exists
    _ensure_schema(conn)

    count = 0
    base_time = int(time.time() * 1e9) - (7 * 24 * 3600 * 1_000_000_000)  # 7 days ago

    for conv_idx, conv in enumerate(DEMO_CONVERSATIONS):
        session_id = f"demo-{conv['platform']}-{conv_idx:03d}"
        conv_time = base_time + (conv_idx * 3600 * 1_000_000_000)  # 1 hour apart

        for msg_idx, msg in enumerate(conv['messages']):
            ts = conv_time + (msg_idx * 60 * 1_000_000_000)  # 1 min apart
            content = msg['content']
            direction = 'inbound' if msg['role'] == 'user' else 'outbound'

            event_id = f"demo-{uuid.uuid4().hex[:12]}"
            intent = 'question' if '?' in content else 'statement'
            topic = conv['topic']
            gut = random.choice(['routine', 'interesting', 'breakthrough_potential'])

            conn.execute("""
                INSERT OR IGNORE INTO cognitive_events
                (event_id, session_id, timestamp_ns, direction, stage, method,
                 content_length, data_content, platform, protocol,
                 light_intent, light_topic, instinct_gut_signal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id, session_id, ts, direction, 'complete', 'demo',
                len(content), content, conv['platform'], 'demo',
                intent, topic, gut,
            ))
            count += 1

        # Create session record
        session_start_ns = conv_time
        conn.execute("""
            INSERT OR IGNORE INTO sessions
            (session_id, started_ns, platform, event_count)
            VALUES (?, ?, ?, ?)
        """, (session_id, session_start_ns, conv['platform'], len(conv['messages'])))

    conn.commit()
    conn.close()
    return count


def clean_demo_data(db_path=None):
    """Remove all demo data. Returns the number of events deleted."""
    db_path = db_path or Config.DB_PATH
    if not Path(db_path).exists():
        return 0
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute("DELETE FROM cognitive_events WHERE protocol = 'demo'")
    deleted = cur.rowcount
    # Sessions don't have a protocol column in the base schema,
    # but demo sessions have predictable IDs.
    conn.execute("DELETE FROM sessions WHERE session_id LIKE 'demo-%'")
    conn.commit()
    conn.close()
    return deleted


def _ensure_schema(conn):
    """Ensure the base cognitive_events and sessions tables exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cognitive_events (
            event_id        TEXT PRIMARY KEY,
            session_id      TEXT,
            timestamp_ns    INTEGER NOT NULL,
            direction       TEXT NOT NULL,
            stage           TEXT NOT NULL,
            method          TEXT,
            request_id      TEXT,
            parent_event_id TEXT,
            turn            INTEGER DEFAULT 0,
            raw_bytes       BLOB,
            parsed_json     TEXT,
            content_length  INTEGER DEFAULT 0,
            error           TEXT,
            data_content    TEXT,
            data_tokens_est INTEGER,
            light_intent    TEXT,
            light_topic     TEXT,
            light_concepts  TEXT,
            light_summary   TEXT,
            instinct_coherence   REAL,
            instinct_indicators  TEXT,
            instinct_gut_signal  TEXT,
            coherence_sig   TEXT,
            platform        TEXT DEFAULT 'claude-desktop',
            protocol        TEXT DEFAULT 'mcp',
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id      TEXT PRIMARY KEY,
            started_ns      INTEGER NOT NULL,
            ended_ns        INTEGER,
            platform        TEXT DEFAULT 'claude-desktop',
            event_count     INTEGER DEFAULT 0,
            turn_count      INTEGER DEFAULT 0,
            topics          TEXT,
            summary         TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );
    """)
