"""
Alert Engine — Generate and manage intelligence alerts from event patterns.

Alerts are persisted to the alerts table (migration 003).
"""

import hashlib
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional

from ucw.server.logger import get_logger

log = get_logger("intelligence.alerting")


class AlertEngine:
    """Create, query, and manage intelligence alerts."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create_alert(
        self,
        type: str,
        severity: str,
        message: str,
        evidence_event_ids: list = None,
    ) -> str:
        """Insert an alert and return its alert_id."""
        timestamp = time.time_ns()
        alert_id = hashlib.sha256(
            f"{type}:{message}:{timestamp}".encode()
        ).hexdigest()[:16]

        self._conn.execute(
            """INSERT INTO alerts
               (alert_id, type, severity, message, evidence_event_ids, timestamp_ns, acknowledged)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (
                alert_id,
                type,
                severity,
                message,
                json.dumps(evidence_event_ids or []),
                timestamp,
            ),
        )
        self._conn.commit()
        log.info(f"Alert created: {alert_id} [{severity}] {type}")
        return alert_id

    def get_alerts(
        self,
        type: str = None,
        severity: str = None,
        acknowledged: bool = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Query alerts with optional filters."""
        clauses: List[str] = []
        params: List[Any] = []

        if type is not None:
            clauses.append("type = ?")
            params.append(type)
        if severity is not None:
            clauses.append("severity = ?")
            params.append(severity)
        if acknowledged is not None:
            clauses.append("acknowledged = ?")
            params.append(1 if acknowledged else 0)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)

        cur = self._conn.execute(
            f"SELECT alert_id, type, severity, message, evidence_event_ids, "
            f"timestamp_ns, acknowledged FROM alerts{where} "
            f"ORDER BY timestamp_ns DESC LIMIT ?",
            params,
        )
        return [
            {
                "alert_id": r[0],
                "type": r[1],
                "severity": r[2],
                "message": r[3],
                "evidence_event_ids": json.loads(r[4]) if r[4] else [],
                "timestamp_ns": r[5],
                "acknowledged": bool(r[6]),
            }
            for r in cur.fetchall()
        ]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged. Returns True if a row was updated."""
        cur = self._conn.execute(
            "UPDATE alerts SET acknowledged = 1 WHERE alert_id = ?",
            (alert_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def check_coherence_alert(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """If coherence > 0.8, create a high-coherence alert. Returns alert dict or None."""
        coherence = event_data.get("instinct_coherence", 0.0)
        if coherence is None or coherence <= 0.8:
            return None

        event_id = event_data.get("event_id", "unknown")
        topic = event_data.get("light_topic", "unknown")
        message = f"High coherence ({coherence:.3f}) detected on topic '{topic}'"

        alert_id = self.create_alert(
            type="high_coherence",
            severity="warning",
            message=message,
            evidence_event_ids=[event_id],
        )
        return {
            "alert_id": alert_id,
            "type": "high_coherence",
            "severity": "warning",
            "message": message,
        }

    def check_emergence_alert(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """If gut_signal == 'breakthrough_potential', create an emergence alert."""
        gut = event_data.get("instinct_gut_signal")
        if gut != "breakthrough_potential":
            return None

        event_id = event_data.get("event_id", "unknown")
        topic = event_data.get("light_topic", "unknown")
        message = f"Emergence signal: breakthrough potential on topic '{topic}'"

        alert_id = self.create_alert(
            type="emergence",
            severity="critical",
            message=message,
            evidence_event_ids=[event_id],
        )
        return {
            "alert_id": alert_id,
            "type": "emergence",
            "severity": "critical",
            "message": message,
        }

    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics: counts by type, severity, acknowledged vs not."""
        cur = self._conn.execute(
            "SELECT type, COUNT(*) FROM alerts GROUP BY type"
        )
        by_type = {r[0]: r[1] for r in cur.fetchall()}

        cur = self._conn.execute(
            "SELECT severity, COUNT(*) FROM alerts GROUP BY severity"
        )
        by_severity = {r[0]: r[1] for r in cur.fetchall()}

        cur = self._conn.execute(
            "SELECT acknowledged, COUNT(*) FROM alerts GROUP BY acknowledged"
        )
        ack_rows = {r[0]: r[1] for r in cur.fetchall()}

        cur = self._conn.execute("SELECT COUNT(*) FROM alerts")
        total = cur.fetchone()[0]

        return {
            "total": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "acknowledged": ack_rows.get(1, 0),
            "unacknowledged": ack_rows.get(0, 0),
        }
