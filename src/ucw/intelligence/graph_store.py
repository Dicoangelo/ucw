"""
Graph Store — Database operations for the knowledge graph.

Operates on the entities and entity_relationships tables
created by migration 001_knowledge_graph.
"""

import json
import sqlite3
from typing import Dict, List, Optional

from ucw.server.logger import get_logger

log = get_logger("intelligence.graph_store")


class GraphStore:
    """CRUD operations for the knowledge graph tables."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def upsert_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        confidence: float,
        timestamp_ns: int,
    ) -> bool:
        """
        Insert or update an entity. Increments event_count on update.
        Returns True on success.
        """
        try:
            self._conn.execute(
                """INSERT INTO entities
                   (entity_id, name, type, confidence,
                    first_seen_ns, last_seen_ns,
                    event_count, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, 1, '{}')
                   ON CONFLICT(entity_id) DO UPDATE SET
                       confidence = MAX(entities.confidence, excluded.confidence),
                       last_seen_ns = excluded.last_seen_ns,
                       event_count = entities.event_count + 1
                """,
                (entity_id, name, entity_type, confidence, timestamp_ns, timestamp_ns),
            )
            self._conn.commit()
            return True
        except Exception as exc:
            log.error(f"Failed to upsert entity {entity_id}: {exc}")
            return False

    def upsert_relationship(
        self,
        rel_id: str,
        source_id: str,
        target_id: str,
        rel_type: str,
        weight: float,
        event_id: str,
        timestamp_ns: int,
    ) -> bool:
        """
        Insert or update a relationship. Increments occurrence_count on update.
        Appends event_id to evidence list.
        Returns True on success.
        """
        try:
            # Check if relationship exists
            cur = self._conn.execute(
                "SELECT evidence_event_ids, occurrence_count "
                "FROM entity_relationships WHERE rel_id = ?",
                (rel_id,),
            )
            existing = cur.fetchone()

            if existing:
                # Update: append evidence, increment count
                evidence_ids = json.loads(existing[0]) if existing[0] else []
                if event_id not in evidence_ids:
                    evidence_ids.append(event_id)
                # Keep only last 100 evidence IDs
                evidence_ids = evidence_ids[-100:]

                new_count = existing[1] + 1
                # Weight grows with occurrences, capped at 1.0
                new_weight = min(1.0, weight + 0.05 * new_count)

                self._conn.execute(
                    """UPDATE entity_relationships
                       SET weight = ?, evidence_event_ids = ?,
                           last_seen_ns = ?, occurrence_count = ?
                       WHERE rel_id = ?""",
                    (new_weight, json.dumps(evidence_ids), timestamp_ns, new_count, rel_id),
                )
            else:
                # Insert new
                self._conn.execute(
                    """INSERT INTO entity_relationships
                       (rel_id, source_entity_id,
                        target_entity_id, type, weight,
                        evidence_event_ids, first_seen_ns,
                        last_seen_ns, occurrence_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                    (rel_id, source_id, target_id, rel_type, weight,
                     json.dumps([event_id]), timestamp_ns, timestamp_ns),
                )

            self._conn.commit()
            return True
        except Exception as exc:
            log.error(f"Failed to upsert relationship {rel_id}: {exc}")
            return False

    def get_entity(self, name: str) -> Optional[Dict]:
        """Get an entity by exact name (case-insensitive)."""
        try:
            cur = self._conn.execute(
                """SELECT entity_id, name, type, confidence, first_seen_ns,
                          last_seen_ns, event_count, metadata
                   FROM entities WHERE LOWER(name) = LOWER(?)""",
                (name,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "entity_id": row[0],
                "name": row[1],
                "type": row[2],
                "confidence": row[3],
                "first_seen_ns": row[4],
                "last_seen_ns": row[5],
                "event_count": row[6],
                "metadata": json.loads(row[7]) if row[7] else {},
            }
        except Exception as exc:
            log.error(f"Failed to get entity '{name}': {exc}")
            return None

    def get_relationships(self, entity_id: str, limit: int = 20) -> List[Dict]:
        """Get relationships for an entity (as source or target)."""
        try:
            cur = self._conn.execute(
                """SELECT r.rel_id, r.source_entity_id, r.target_entity_id,
                          r.type, r.weight, r.evidence_event_ids,
                          r.first_seen_ns, r.last_seen_ns, r.occurrence_count,
                          s.name AS source_name, t.name AS target_name
                   FROM entity_relationships r
                   LEFT JOIN entities s ON r.source_entity_id = s.entity_id
                   LEFT JOIN entities t ON r.target_entity_id = t.entity_id
                   WHERE r.source_entity_id = ? OR r.target_entity_id = ?
                   ORDER BY r.weight DESC
                   LIMIT ?""",
                (entity_id, entity_id, limit),
            )
            return [
                {
                    "rel_id": row[0],
                    "source_entity_id": row[1],
                    "target_entity_id": row[2],
                    "type": row[3],
                    "weight": row[4],
                    "evidence_event_ids": json.loads(row[5]) if row[5] else [],
                    "first_seen_ns": row[6],
                    "last_seen_ns": row[7],
                    "occurrence_count": row[8],
                    "source_name": row[9],
                    "target_name": row[10],
                }
                for row in cur.fetchall()
            ]
        except Exception as exc:
            log.error(f"Failed to get relationships for {entity_id}: {exc}")
            return []

    def search_entities(
        self, query: str, type_filter: Optional[str] = None, limit: int = 20,
    ) -> List[Dict]:
        """Search entities by name using LIKE."""
        try:
            sql = """SELECT entity_id, name, type, confidence, first_seen_ns,
                            last_seen_ns, event_count
                     FROM entities
                     WHERE LOWER(name) LIKE LOWER(?)"""
            params: list = [f"%{query}%"]

            if type_filter:
                sql += " AND type = ?"
                params.append(type_filter)

            sql += " ORDER BY event_count DESC, confidence DESC LIMIT ?"
            params.append(limit)

            cur = self._conn.execute(sql, params)
            return [
                {
                    "entity_id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "confidence": row[3],
                    "first_seen_ns": row[4],
                    "last_seen_ns": row[5],
                    "event_count": row[6],
                }
                for row in cur.fetchall()
            ]
        except Exception as exc:
            log.error(f"Failed to search entities for '{query}': {exc}")
            return []

    def get_graph_stats(self) -> Dict:
        """Get overall knowledge graph statistics."""
        try:
            cur = self._conn.execute("SELECT COUNT(*) FROM entities")
            entity_count = cur.fetchone()[0]

            cur = self._conn.execute("SELECT COUNT(*) FROM entity_relationships")
            rel_count = cur.fetchone()[0]

            cur = self._conn.execute(
                "SELECT type, COUNT(*) FROM entities GROUP BY type ORDER BY COUNT(*) DESC"
            )
            entity_types = {row[0]: row[1] for row in cur.fetchall()}

            cur = self._conn.execute(
                "SELECT type, COUNT(*) FROM entity_relationships "
                "GROUP BY type ORDER BY COUNT(*) DESC"
            )
            rel_types = {row[0]: row[1] for row in cur.fetchall()}

            cur = self._conn.execute(
                "SELECT name, event_count FROM entities ORDER BY event_count DESC LIMIT 10"
            )
            top_entities = [{"name": row[0], "event_count": row[1]} for row in cur.fetchall()]

            return {
                "entity_count": entity_count,
                "relationship_count": rel_count,
                "entity_types": entity_types,
                "relationship_types": rel_types,
                "top_entities": top_entities,
            }
        except Exception as exc:
            log.error(f"Failed to get graph stats: {exc}")
            return {
                "entity_count": 0,
                "relationship_count": 0,
                "entity_types": {},
                "relationship_types": {},
                "top_entities": [],
            }
