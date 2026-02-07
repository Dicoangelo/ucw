-- ============================================================================
-- Unified Cognitive Database Schema
-- UCW — Universal Cognitive Wallet
-- PostgreSQL 15+ with pgvector (used for v1.1+ with PostgreSQL backend)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- 1. cognitive_events
CREATE TABLE IF NOT EXISTS cognitive_events (
    event_id            TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL,
    timestamp_ns        BIGINT NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    direction           TEXT NOT NULL,
    stage               TEXT NOT NULL,
    method              TEXT,
    request_id          TEXT,
    parent_event_id     TEXT,
    turn                INTEGER DEFAULT 0,
    raw_bytes           BYTEA,
    parsed_json         JSONB,
    content_length      INTEGER DEFAULT 0,
    error               TEXT,
    data_layer          JSONB,
    light_layer         JSONB,
    instinct_layer      JSONB,
    coherence_sig       TEXT,
    semantic_embedding  vector(384),
    platform            TEXT DEFAULT 'claude-desktop',
    protocol            TEXT DEFAULT 'mcp',
    quality_score       REAL,
    cognitive_mode      TEXT
);

CREATE INDEX IF NOT EXISTS idx_ce_timestamp     ON cognitive_events (timestamp_ns);
CREATE INDEX IF NOT EXISTS idx_ce_session       ON cognitive_events (session_id);
CREATE INDEX IF NOT EXISTS idx_ce_method        ON cognitive_events (method);
CREATE INDEX IF NOT EXISTS idx_ce_direction     ON cognitive_events (direction);
CREATE INDEX IF NOT EXISTS idx_ce_platform      ON cognitive_events (platform);

-- 2. cognitive_sessions
CREATE TABLE IF NOT EXISTS cognitive_sessions (
    session_id          TEXT PRIMARY KEY,
    started_ns          BIGINT NOT NULL,
    ended_ns            BIGINT,
    platform            TEXT DEFAULT 'claude-desktop',
    status              TEXT DEFAULT 'active',
    event_count         INTEGER DEFAULT 0,
    turn_count          INTEGER DEFAULT 0,
    topics              JSONB,
    summary             TEXT,
    cognitive_mode      TEXT,
    quality_score       REAL,
    metadata            JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 3. coherence_moments
CREATE TABLE IF NOT EXISTS coherence_moments (
    moment_id           TEXT PRIMARY KEY,
    detected_ns         BIGINT NOT NULL,
    event_ids           TEXT[] NOT NULL,
    platforms           TEXT[] NOT NULL,
    coherence_type      TEXT NOT NULL,
    confidence          REAL NOT NULL,
    description         TEXT,
    time_window_s       INTEGER,
    signature           TEXT,
    metadata            JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 4. embedding_cache
CREATE TABLE IF NOT EXISTS embedding_cache (
    content_hash        TEXT PRIMARY KEY,
    content_preview     TEXT,
    embedding           vector(384),
    model               TEXT NOT NULL,
    dimensions          INTEGER NOT NULL,
    source_event_id     TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ec_embedding
    ON embedding_cache USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
