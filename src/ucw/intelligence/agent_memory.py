"""
Agent Memory — Store and retrieve agent learnings.

Agents can write back insights, search by project/topic/confidence,
and retrieve relevant context for future queries.
"""

import hashlib
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional

from ucw.server.logger import get_logger

log = get_logger("intelligence.agent_memory")


class AgentMemory:
    """Agent learning store backed by the agent_learnings table."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def store_learning(
        self,
        text: str,
        project: str = None,
        tags: list = None,
        confidence: float = 0.5,
        source_session: str = None,
        entity_ids: list = None,
        intent: str = None,
        topic: str = None,
        concepts: list = None,
        coherence: float = None,
    ) -> str:
        """Insert a learning into agent_learnings. Returns learning_id."""
        timestamp_ns = time.time_ns()
        learning_id = hashlib.sha256(
            f"{text[:100]}:{timestamp_ns}".encode()
        ).hexdigest()[:16]

        self._conn.execute(
            """INSERT INTO agent_learnings (
                learning_id, text, project, tags, confidence,
                source_session, entity_ids, timestamp_ns,
                light_intent, light_topic, light_concepts,
                instinct_coherence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                learning_id,
                text,
                project,
                json.dumps(tags) if tags else None,
                confidence,
                source_session,
                json.dumps(entity_ids) if entity_ids else None,
                timestamp_ns,
                intent,
                topic,
                json.dumps(concepts) if concepts else None,
                coherence,
            ),
        )
        self._conn.commit()
        log.info(f"Stored learning {learning_id}: {text[:60]}")
        return learning_id

    def search_learnings(
        self,
        query: str = None,
        project: str = None,
        topic: str = None,
        min_confidence: float = 0.0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search learnings with LIKE on text, filter by project/topic/confidence."""
        conditions = ["confidence >= ?"]
        params: list = [min_confidence]

        if query:
            conditions.append("text LIKE ?")
            params.append(f"%{query}%")
        if project:
            conditions.append("project = ?")
            params.append(project)
        if topic:
            conditions.append("light_topic LIKE ?")
            params.append(f"%{topic}%")

        where = " AND ".join(conditions)
        params.append(limit)

        cur = self._conn.execute(
            f"""SELECT learning_id, text, project, tags, confidence,
                       source_session, entity_ids, timestamp_ns,
                       light_intent, light_topic, light_concepts,
                       instinct_coherence, created_at
                FROM agent_learnings
                WHERE {where}
                ORDER BY confidence DESC, timestamp_ns DESC
                LIMIT ?""",
            params,
        )
        return [self._row_to_dict(row) for row in cur.fetchall()]

    def get_learning(self, learning_id: str) -> Optional[Dict[str, Any]]:
        """Get a single learning by ID."""
        cur = self._conn.execute(
            """SELECT learning_id, text, project, tags, confidence,
                      source_session, entity_ids, timestamp_ns,
                      light_intent, light_topic, light_concepts,
                      instinct_coherence, created_at
               FROM agent_learnings WHERE learning_id = ?""",
            (learning_id,),
        )
        row = cur.fetchone()
        return self._row_to_dict(row) if row else None

    def update_confidence(self, learning_id: str, new_confidence: float) -> bool:
        """Update confidence for a learning. Returns True if row was found."""
        cur = self._conn.execute(
            "UPDATE agent_learnings SET confidence = ? WHERE learning_id = ?",
            (new_confidence, learning_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def get_learning_stats(self) -> Dict[str, Any]:
        """Count by project, topic, avg confidence, total."""
        cur = self._conn.execute("SELECT COUNT(*) FROM agent_learnings")
        total = cur.fetchone()[0]

        cur = self._conn.execute(
            """SELECT project, COUNT(*) FROM agent_learnings
               WHERE project IS NOT NULL
               GROUP BY project ORDER BY COUNT(*) DESC"""
        )
        by_project = {r[0]: r[1] for r in cur.fetchall()}

        cur = self._conn.execute(
            """SELECT light_topic, COUNT(*) FROM agent_learnings
               WHERE light_topic IS NOT NULL
               GROUP BY light_topic ORDER BY COUNT(*) DESC"""
        )
        by_topic = {r[0]: r[1] for r in cur.fetchall()}

        cur = self._conn.execute("SELECT AVG(confidence) FROM agent_learnings")
        avg_confidence = cur.fetchone()[0] or 0.0

        return {
            "total": total,
            "by_project": by_project,
            "by_topic": by_topic,
            "avg_confidence": round(avg_confidence, 3),
        }

    def get_context_for_query(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Find most relevant learnings for a query (LIKE match + sort by confidence DESC)."""
        cur = self._conn.execute(
            """SELECT learning_id, text, project, tags, confidence,
                      source_session, entity_ids, timestamp_ns,
                      light_intent, light_topic, light_concepts,
                      instinct_coherence, created_at
               FROM agent_learnings
               WHERE text LIKE ?
               ORDER BY confidence DESC, timestamp_ns DESC
               LIMIT ?""",
            (f"%{query}%", limit),
        )
        return [self._row_to_dict(row) for row in cur.fetchall()]

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        """Convert a row tuple to a dict."""
        (
            learning_id, text, project, tags, confidence,
            source_session, entity_ids, timestamp_ns,
            intent, topic, concepts, coherence, created_at,
        ) = row
        return {
            "learning_id": learning_id,
            "text": text,
            "project": project,
            "tags": _safe_json_list(tags),
            "confidence": confidence,
            "source_session": source_session,
            "entity_ids": _safe_json_list(entity_ids),
            "timestamp_ns": timestamp_ns,
            "intent": intent,
            "topic": topic,
            "concepts": _safe_json_list(concepts),
            "coherence": coherence,
            "created_at": created_at,
        }


def _safe_json_list(value) -> list:
    """Parse JSON list or return empty list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []
