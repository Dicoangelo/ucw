"""
Temporal Analyzer — Track knowledge evolution over time.

Provides topic evolution, skill trajectories, knowledge decay detection,
activity heatmaps, session comparisons, and temporal stats.
"""

import sqlite3
import time
from typing import Any, Dict, List

from ucw.server.logger import get_logger

log = get_logger("intelligence.temporal")


class TemporalAnalyzer:
    """Temporal analysis over cognitive_events."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def topic_evolution(self, days: int = 30) -> List[Dict[str, Any]]:
        """Show how topics change over time. Group events by day + topic, return counts."""
        cutoff_ns = time.time_ns() - (days * 86400 * 1_000_000_000)
        cur = self._conn.execute(
            """SELECT date(created_at) as day, light_topic, COUNT(*) as cnt
               FROM cognitive_events
               WHERE timestamp_ns > ? AND light_topic IS NOT NULL
               GROUP BY day, light_topic
               ORDER BY day, cnt DESC""",
            (cutoff_ns,),
        )
        return [
            {"day": row[0], "topic": row[1], "count": row[2]}
            for row in cur.fetchall()
        ]

    def skill_trajectory(self, topic: str, days: int = 30) -> Dict[str, Any]:
        """Track coherence progression for a topic over time."""
        cutoff_ns = time.time_ns() - (days * 86400 * 1_000_000_000)
        cur = self._conn.execute(
            """SELECT date(created_at) as day,
                      AVG(instinct_coherence) as avg_coherence,
                      COUNT(*) as event_count
               FROM cognitive_events
               WHERE light_topic LIKE ? AND timestamp_ns > ?
                     AND instinct_coherence IS NOT NULL
               GROUP BY day
               ORDER BY day""",
            (f"%{topic}%", cutoff_ns),
        )
        trajectory = [
            {
                "day": row[0],
                "avg_coherence": round(row[1], 3) if row[1] else 0.0,
                "event_count": row[2],
            }
            for row in cur.fetchall()
        ]
        return {"topic": topic, "trajectory": trajectory}

    def knowledge_decay(self, days: int = 90) -> List[Dict[str, Any]]:
        """Find topics that were active but have gone silent.

        Strategy: topics with events in first half of window but not in last 14 days.
        """
        cutoff_ns = time.time_ns() - (days * 86400 * 1_000_000_000)
        recent_cutoff_ns = time.time_ns() - (14 * 86400 * 1_000_000_000)

        # Get all topics in the window
        cur = self._conn.execute(
            """SELECT light_topic, COUNT(*) as cnt,
                      MAX(date(created_at)) as last_seen
               FROM cognitive_events
               WHERE timestamp_ns > ? AND light_topic IS NOT NULL
               GROUP BY light_topic""",
            (cutoff_ns,),
        )
        all_topics = {row[0]: {"count": row[1], "last_seen": row[2]} for row in cur.fetchall()}

        # Get topics active in last 14 days
        cur = self._conn.execute(
            """SELECT DISTINCT light_topic
               FROM cognitive_events
               WHERE timestamp_ns > ? AND light_topic IS NOT NULL""",
            (recent_cutoff_ns,),
        )
        recent_topics = {row[0] for row in cur.fetchall()}

        # Decaying = in window but not in recent
        decaying = []
        today = time.strftime("%Y-%m-%d")
        for topic, info in all_topics.items():
            if topic not in recent_topics:
                last_seen = info["last_seen"] or today
                # Estimate days inactive
                try:
                    from datetime import datetime
                    last_dt = datetime.strptime(last_seen, "%Y-%m-%d")
                    today_dt = datetime.strptime(today, "%Y-%m-%d")
                    days_inactive = (today_dt - last_dt).days
                except (ValueError, TypeError):
                    days_inactive = 0

                decaying.append({
                    "topic": topic,
                    "last_seen": last_seen,
                    "peak_count": info["count"],
                    "days_inactive": days_inactive,
                })

        decaying.sort(key=lambda x: x["days_inactive"], reverse=True)
        return decaying

    def activity_heatmap(self, days: int = 30) -> Dict[str, Any]:
        """Hour-of-day activity distribution."""
        cutoff_ns = time.time_ns() - (days * 86400 * 1_000_000_000)
        cur = self._conn.execute(
            """SELECT strftime('%H', created_at) as hour, COUNT(*) as cnt
               FROM cognitive_events
               WHERE timestamp_ns > ?
               GROUP BY hour
               ORDER BY hour""",
            (cutoff_ns,),
        )
        hours = {row[0]: row[1] for row in cur.fetchall()}
        return {"days": days, "hours": hours}

    def session_comparison(self, session_id_a: str, session_id_b: str) -> Dict[str, Any]:
        """Compare two sessions: topic overlap, coherence diff, concept overlap."""

        def _session_data(sid):
            cur = self._conn.execute(
                """SELECT light_topic, light_concepts, instinct_coherence
                   FROM cognitive_events WHERE session_id = ?""",
                (sid,),
            )
            topics = set()
            concepts = set()
            coherences = []
            for row in cur.fetchall():
                if row[0]:
                    topics.add(row[0])
                if row[1]:
                    try:
                        import json
                        parsed = json.loads(row[1])
                        if isinstance(parsed, list):
                            concepts.update(parsed)
                    except (json.JSONDecodeError, TypeError):
                        pass
                if row[2] is not None:
                    coherences.append(row[2])
            avg_coherence = sum(coherences) / len(coherences) if coherences else 0.0
            return topics, concepts, avg_coherence

        topics_a, concepts_a, coherence_a = _session_data(session_id_a)
        topics_b, concepts_b, coherence_b = _session_data(session_id_b)

        topic_overlap = topics_a & topics_b
        concept_overlap = concepts_a & concepts_b

        return {
            "session_a": session_id_a,
            "session_b": session_id_b,
            "topics_a": sorted(topics_a),
            "topics_b": sorted(topics_b),
            "topic_overlap": sorted(topic_overlap),
            "concepts_a": sorted(concepts_a),
            "concepts_b": sorted(concepts_b),
            "concept_overlap": sorted(concept_overlap),
            "coherence_a": round(coherence_a, 3),
            "coherence_b": round(coherence_b, 3),
            "coherence_diff": round(coherence_b - coherence_a, 3),
        }

    def get_temporal_stats(self) -> Dict[str, Any]:
        """Overall temporal stats: date range, busiest day, avg events/day."""
        cur = self._conn.execute(
            """SELECT MIN(date(created_at)), MAX(date(created_at)), COUNT(*)
               FROM cognitive_events"""
        )
        row = cur.fetchone()
        first_day = row[0]
        last_day = row[1]
        total = row[2]

        cur = self._conn.execute(
            """SELECT date(created_at) as day, COUNT(*) as cnt
               FROM cognitive_events
               GROUP BY day
               ORDER BY cnt DESC
               LIMIT 1"""
        )
        busiest = cur.fetchone()
        busiest_day = busiest[0] if busiest else None
        busiest_count = busiest[1] if busiest else 0

        # Calculate days span
        if first_day and last_day:
            try:
                from datetime import datetime
                d1 = datetime.strptime(first_day, "%Y-%m-%d")
                d2 = datetime.strptime(last_day, "%Y-%m-%d")
                span_days = max((d2 - d1).days, 1)
            except (ValueError, TypeError):
                span_days = 1
        else:
            span_days = 1

        avg_per_day = round(total / span_days, 1) if span_days else 0.0

        return {
            "first_day": first_day,
            "last_day": last_day,
            "total_events": total,
            "span_days": span_days,
            "avg_events_per_day": avg_per_day,
            "busiest_day": busiest_day,
            "busiest_count": busiest_count,
        }
