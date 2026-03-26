"""
UCW Demo — Generate realistic sample AI conversations for exploring UCW features.
"""

import hashlib
import random
import sqlite3
import time
import uuid
from pathlib import Path

from ucw.config import Config

DEMO_CONVERSATIONS = [
    # Claude conversations
    {"platform": "claude-desktop", "topic": "python", "messages": [
        {"role": "user", "content": "How do I use async/await in Python? I'm building an MCP server."},
        {"role": "assistant", "content": "Python's async/await is built on the asyncio module. Here's the pattern for an MCP server: define async handlers, use asyncio.run() as your entry point."},
        {"role": "user", "content": "What about handling multiple concurrent connections?"},
        {"role": "assistant", "content": "Use asyncio.gather() for concurrent tasks or asyncio.create_task() for fire-and-forget. For MCP, each client gets its own session."},
    ]},
    {"platform": "claude-desktop", "topic": "architecture", "messages": [
        {"role": "user", "content": "I'm designing a plugin architecture. Should I use dependency injection?"},
        {"role": "assistant", "content": "For a plugin system, DI works well. Consider a registry pattern where plugins declare their capabilities and dependencies."},
        {"role": "user", "content": "How do I handle plugin dependencies on each other?"},
        {"role": "assistant", "content": "A topological sort of the dependency graph ensures correct load order. Detect cycles early and fail fast with clear error messages."},
    ]},
    # ChatGPT conversations
    {"platform": "chatgpt", "topic": "machine-learning", "messages": [
        {"role": "user", "content": "Explain transformer attention mechanisms to me"},
        {"role": "assistant", "content": "Attention in transformers computes weighted relationships between all token pairs using Query, Key, and Value matrices."},
        {"role": "user", "content": "How does multi-head attention differ from single-head?"},
        {"role": "assistant", "content": "Multi-head attention runs multiple attention operations in parallel, each learning different relationship patterns."},
        {"role": "user", "content": "What's the relationship between attention and memory in neural networks?"},
        {"role": "assistant", "content": "Attention can be viewed as a soft addressing mechanism over memory. External memory networks like Neural Turing Machines formalize this."},
    ]},
    {"platform": "chatgpt", "topic": "data-science", "messages": [
        {"role": "user", "content": "What's the best way to handle missing data in pandas?"},
        {"role": "assistant", "content": "Several strategies: dropna(), fillna() with mean/median, interpolate(), or use models like KNN imputation for more sophistication."},
    ]},
    # Cursor conversations
    {"platform": "cursor", "topic": "debugging", "messages": [
        {"role": "user", "content": "This React component re-renders on every keystroke. How do I fix it?"},
        {"role": "assistant", "content": "Wrap the callback in useCallback and memoize the component with React.memo(). Check that props are stable references."},
        {"role": "user", "content": "The useMemo dependency array keeps changing. What am I doing wrong?"},
        {"role": "assistant", "content": "You're creating a new object literal on each render. Extract it to a ref or move the object creation outside the component."},
    ]},
    {"platform": "cursor", "topic": "typescript", "messages": [
        {"role": "user", "content": "How do I type a function that accepts a generic record?"},
        {"role": "assistant", "content": "Use Record<string, T> or define a mapped type. For more control, use a generic constraint: <T extends Record<string, unknown>>."},
        {"role": "user", "content": "What about conditional types for the return value?"},
        {"role": "assistant", "content": "Conditional types with infer let you extract types from generics. Example: T extends Promise<infer U> ? U : T unwraps promises."},
    ]},
    {"platform": "claude-desktop", "topic": "database", "messages": [
        {"role": "user", "content": "SQLite WAL mode vs rollback journal -- when should I use each?"},
        {"role": "assistant", "content": "WAL mode is better for concurrent reads during writes. Rollback journal is simpler and better for single-writer scenarios with rare reads."},
        {"role": "user", "content": "Can I use WAL mode with multiple processes writing?"},
        {"role": "assistant", "content": "Yes, but only one writer at a time. Others queue behind it. Use BEGIN IMMEDIATE to fail fast if another writer holds the lock."},
    ]},
    {"platform": "chatgpt", "topic": "career", "messages": [
        {"role": "user", "content": "How should I prepare for a system design interview?"},
        {"role": "assistant", "content": "Focus on: scalability, availability, consistency tradeoffs. Practice drawing architecture diagrams and estimating capacity."},
        {"role": "user", "content": "What about behavioral questions for senior roles?"},
        {"role": "assistant", "content": "Use STAR format. Prepare stories about: conflict resolution, technical decisions under uncertainty, mentoring, and project recovery."},
    ]},
    {"platform": "cursor", "topic": "testing", "messages": [
        {"role": "user", "content": "How do I mock an async function in pytest?"},
        {"role": "assistant", "content": "Use AsyncMock from unittest.mock or pytest-asyncio fixtures. Patch the target module, not the source."},
        {"role": "user", "content": "What about testing SQLite in-memory databases?"},
        {"role": "assistant", "content": "Use ':memory:' for speed, but beware: it doesn't persist between connections. Use a shared cache or a temp file for multi-connection tests."},
    ]},
    {"platform": "claude-desktop", "topic": "security", "messages": [
        {"role": "user", "content": "What are the OWASP top 10 for 2024?"},
        {"role": "assistant", "content": "Broken access control, cryptographic failures, injection, insecure design, security misconfiguration, vulnerable components, auth failures, integrity failures, logging gaps, SSRF."},
    ]},
    {"platform": "chatgpt", "topic": "python", "messages": [
        {"role": "user", "content": "What's new in Python 3.12?"},
        {"role": "assistant", "content": "Type parameter syntax (PEP 695), per-interpreter GIL (PEP 684), improved error messages, and f-string grammar relaxation."},
        {"role": "user", "content": "How does the per-interpreter GIL improve concurrency?"},
        {"role": "assistant", "content": "Each sub-interpreter gets its own GIL, enabling true parallelism for CPU-bound Python code without multiprocessing overhead."},
    ]},
    {"platform": "claude-desktop", "topic": "devops", "messages": [
        {"role": "user", "content": "Docker compose vs Kubernetes for a small team?"},
        {"role": "assistant", "content": "Docker Compose for development and small deployments. Kubernetes when you need auto-scaling, rolling updates, and multi-node orchestration."},
        {"role": "user", "content": "When is the right time to migrate to Kubernetes?"},
        {"role": "assistant", "content": "When you have 5+ services, need zero-downtime deploys, or your traffic is unpredictable enough to benefit from auto-scaling."},
    ]},
    {"platform": "cursor", "topic": "git", "messages": [
        {"role": "user", "content": "How do I rewrite commit history to remove a secret that was committed?"},
        {"role": "assistant", "content": "Use git filter-repo (preferred over filter-branch). Also rotate the secret immediately -- git history rewrites don't protect already-cloned copies."},
    ]},
    {"platform": "chatgpt", "topic": "networking", "messages": [
        {"role": "user", "content": "What is the difference between TCP and UDP?"},
        {"role": "assistant", "content": "TCP provides reliable, ordered delivery with connection setup. UDP is connectionless and faster but offers no delivery guarantees."},
        {"role": "user", "content": "When would I choose UDP over TCP for a real-time application?"},
        {"role": "assistant", "content": "Use UDP for low-latency needs like gaming, video streaming, or VoIP where occasional packet loss is acceptable and retransmission adds unacceptable delay."},
    ]},
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
