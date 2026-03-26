"""
Thread Linker — Cross-platform conversation thread linking.

Groups cognitive events into conversation threads using topic similarity,
temporal proximity, and entity overlap scoring.
"""

import hashlib
import json
import sqlite3
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from ucw.server.logger import get_logger

log = get_logger("intelligence.thread_linker")

# 5-minute window in nanoseconds
_TIME_BUCKET_NS = 5 * 60 * 1_000_000_000


class ThreadLinker:
    """Link cognitive events into cross-platform conversation threads."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def link_events_to_threads(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group events into conversation threads.

        Strategy:
        1. Group by topic (exact match)
        2. Within topic groups, cluster by temporal proximity (5-minute windows)
        3. Score: entity_overlap (Jaccard on concepts), semantic (topic match),
           temporal (inverse time gap)
        4. combined_score = 0.4 * entity_overlap + 0.35 * semantic + 0.25 * temporal
        5. Upsert into conversation_threads table
        """
        if not events:
            return []

        # Step 1: Group by topic
        topic_groups: Dict[str, List[Dict]] = defaultdict(list)
        for evt in events:
            topic = evt.get("light_topic") or "general"
            topic_groups[topic].append(evt)

        threads: List[Dict[str, Any]] = []

        for topic, group in topic_groups.items():
            # Step 2: Sub-cluster by time bucket
            time_buckets: Dict[int, List[Dict]] = defaultdict(list)
            for evt in group:
                ts = evt.get("timestamp_ns", 0)
                bucket = ts // _TIME_BUCKET_NS
                time_buckets[bucket].append(evt)

            for bucket, bucket_events in time_buckets.items():
                if not bucket_events:
                    continue

                thread_id = hashlib.sha256(
                    f"{topic}:{bucket}".encode()
                ).hexdigest()[:16]

                # Step 3: Score
                entity_overlap = self._entity_overlap_score(bucket_events)
                semantic = 1.0  # All same topic by definition
                temporal = self._temporal_score(bucket_events)

                # Step 4: Combined
                combined = 0.4 * entity_overlap + 0.35 * semantic + 0.25 * temporal

                # Collect session/platform info
                sessions = list({
                    evt.get("session_id", "unknown")
                    for evt in bucket_events
                })

                now_ns = time.time_ns()
                thread = {
                    "thread_id": thread_id,
                    "topic": topic,
                    "platform_sessions": json.dumps(sessions),
                    "entity_overlap_score": round(entity_overlap, 4),
                    "semantic_score": round(semantic, 4),
                    "temporal_score": round(temporal, 4),
                    "combined_score": round(combined, 4),
                    "created_ns": now_ns,
                    "updated_ns": now_ns,
                    "event_count": len(bucket_events),
                }

                # Step 5: Upsert
                self._upsert_thread(thread)
                threads.append(thread)

        log.info(f"Linked {len(events)} events into {len(threads)} threads")
        return threads

    def get_threads(
        self, min_score: float = 0.3, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Query threads above minimum combined score."""
        cur = self._conn.execute(
            """SELECT thread_id, topic, platform_sessions,
                      entity_overlap_score, semantic_score, temporal_score,
                      combined_score, created_ns, updated_ns
               FROM conversation_threads
               WHERE combined_score >= ?
               ORDER BY combined_score DESC
               LIMIT ?""",
            (min_score, limit),
        )
        return [
            {
                "thread_id": r[0],
                "topic": r[1],
                "platform_sessions": json.loads(r[2]) if r[2] else [],
                "entity_overlap_score": r[3],
                "semantic_score": r[4],
                "temporal_score": r[5],
                "combined_score": r[6],
                "created_ns": r[7],
                "updated_ns": r[8],
            }
            for r in cur.fetchall()
        ]

    def get_thread_events(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get events belonging to a thread by querying platform_sessions."""
        cur = self._conn.execute(
            "SELECT platform_sessions FROM conversation_threads WHERE thread_id = ?",
            (thread_id,),
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return []

        sessions = json.loads(row[0])
        if not sessions:
            return []

        placeholders = ",".join("?" for _ in sessions)
        cur = self._conn.execute(
            f"""SELECT event_id, session_id, timestamp_ns, direction, method,
                       light_topic, light_intent, light_summary, platform
                FROM cognitive_events
                WHERE session_id IN ({placeholders})
                ORDER BY timestamp_ns""",
            sessions,
        )
        return [
            {
                "event_id": r[0],
                "session_id": r[1],
                "timestamp_ns": r[2],
                "direction": r[3],
                "method": r[4],
                "light_topic": r[5],
                "light_intent": r[6],
                "light_summary": r[7],
                "platform": r[8],
            }
            for r in cur.fetchall()
        ]

    def find_cross_platform_threads(self, min_platforms: int = 2) -> List[Dict[str, Any]]:
        """Find threads spanning multiple platforms."""
        threads = self.get_threads(min_score=0.0, limit=1000)
        cross_platform = []

        for t in threads:
            sessions = t.get("platform_sessions", [])
            # Count unique platforms by querying events
            if not sessions:
                continue
            placeholders = ",".join("?" for _ in sessions)
            cur = self._conn.execute(
                f"SELECT COUNT(DISTINCT platform) FROM cognitive_events "
                f"WHERE session_id IN ({placeholders})",
                sessions,
            )
            row = cur.fetchone()
            platform_count = row[0] if row else 0
            if platform_count >= min_platforms:
                t["platform_count"] = platform_count
                cross_platform.append(t)

        return cross_platform

    def get_thread_stats(self) -> Dict[str, Any]:
        """Thread counts, average scores, platform distribution."""
        cur = self._conn.execute(
            """SELECT COUNT(*),
                      AVG(combined_score),
                      AVG(entity_overlap_score),
                      AVG(semantic_score),
                      AVG(temporal_score)
               FROM conversation_threads"""
        )
        row = cur.fetchone()
        total = row[0] if row else 0

        cur = self._conn.execute(
            "SELECT topic, COUNT(*) FROM conversation_threads GROUP BY topic ORDER BY COUNT(*) DESC LIMIT 10"
        )
        topic_dist = {r[0]: r[1] for r in cur.fetchall()}

        return {
            "total_threads": total,
            "avg_combined_score": round(row[1] or 0.0, 4) if row else 0.0,
            "avg_entity_overlap": round(row[2] or 0.0, 4) if row else 0.0,
            "avg_semantic_score": round(row[3] or 0.0, 4) if row else 0.0,
            "avg_temporal_score": round(row[4] or 0.0, 4) if row else 0.0,
            "topic_distribution": topic_dist,
        }

    # --- Internal helpers ---

    def _upsert_thread(self, thread: Dict[str, Any]) -> None:
        """Insert or update a conversation thread."""
        self._conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, topic, platform_sessions,
                entity_overlap_score, semantic_score, temporal_score,
                combined_score, created_ns, updated_ns)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(thread_id) DO UPDATE SET
                   platform_sessions = excluded.platform_sessions,
                   entity_overlap_score = excluded.entity_overlap_score,
                   semantic_score = excluded.semantic_score,
                   temporal_score = excluded.temporal_score,
                   combined_score = excluded.combined_score,
                   updated_ns = excluded.updated_ns""",
            (
                thread["thread_id"],
                thread["topic"],
                thread["platform_sessions"],
                thread["entity_overlap_score"],
                thread["semantic_score"],
                thread["temporal_score"],
                thread["combined_score"],
                thread["created_ns"],
                thread["updated_ns"],
            ),
        )
        self._conn.commit()

    @staticmethod
    def _entity_overlap_score(events: List[Dict[str, Any]]) -> float:
        """Jaccard similarity on concepts across events in the cluster."""
        if len(events) < 2:
            return 0.0

        concept_sets = []
        for evt in events:
            raw = evt.get("light_concepts", "[]")
            if isinstance(raw, str):
                try:
                    concepts = set(json.loads(raw))
                except (json.JSONDecodeError, TypeError):
                    concepts = set()
            elif isinstance(raw, list):
                concepts = set(raw)
            else:
                concepts = set()
            concept_sets.append(concepts)

        # Pairwise Jaccard, return average
        total = 0.0
        pairs = 0
        for i in range(len(concept_sets)):
            for j in range(i + 1, len(concept_sets)):
                a, b = concept_sets[i], concept_sets[j]
                if not a and not b:
                    continue
                union = a | b
                if union:
                    total += len(a & b) / len(union)
                    pairs += 1

        return total / pairs if pairs > 0 else 0.0

    @staticmethod
    def _temporal_score(events: List[Dict[str, Any]]) -> float:
        """Inverse time gap score — closer events score higher."""
        if len(events) < 2:
            return 1.0

        timestamps = sorted(
            evt.get("timestamp_ns", 0) for evt in events
        )
        max_gap_ns = timestamps[-1] - timestamps[0]
        if max_gap_ns == 0:
            return 1.0

        # Normalize: within 1 minute = 1.0, within 5 minutes decays
        max_window = _TIME_BUCKET_NS  # 5 minutes
        score = max(0.0, 1.0 - (max_gap_ns / max_window))
        return round(score, 4)
