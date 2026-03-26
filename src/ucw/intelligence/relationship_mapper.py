"""
Relationship Mapper — Build relationships between entities found in the same event.

Maps co-occurrence, topic-related, and temporal proximity relationships.
"""

import hashlib
from typing import Dict, List


def map_relationships(
    entities: List[Dict],
    event_id: str,
    timestamp_ns: int,
) -> List[Dict]:
    """
    Build relationships between entities found in the same event.

    Args:
        entities: List of {"name": str, "type": str, "confidence": float}
        event_id: The event where these entities co-occurred
        timestamp_ns: Event timestamp in nanoseconds

    Returns:
        List of {
            "source": str, "target": str, "type": str,
            "weight": float, "evidence_event_id": str
        }
    """
    if not entities or len(entities) < 2:
        return []

    relationships: List[Dict] = []
    seen_pairs: set = set()

    for i, source in enumerate(entities):
        for j, target in enumerate(entities):
            if i >= j:
                continue

            # Canonical pair key to avoid duplicates
            pair_key = _canonical_pair(source["name"], target["name"])
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            # Determine relationship type and weight
            rel_type = _determine_relationship_type(source, target)
            weight = _calculate_weight(source, target)

            relationships.append({
                "source": source["name"],
                "target": target["name"],
                "type": rel_type,
                "weight": weight,
                "evidence_event_id": event_id,
            })

    return relationships


def _canonical_pair(a: str, b: str) -> str:
    """Return a canonical key for an entity pair (order-independent)."""
    names = sorted([a.lower(), b.lower()])
    return f"{names[0]}::{names[1]}"


def _determine_relationship_type(source: Dict, target: Dict) -> str:
    """Determine the relationship type based on entity types."""
    s_type = source.get("type", "")
    t_type = target.get("type", "")

    # Same type entities are topic-related
    if s_type == t_type:
        return "topic_related"

    # Person + anything else is co_occurrence
    if "person" in (s_type, t_type):
        return "co_occurrence"

    # Technology + tool is co_occurrence
    if {s_type, t_type} & {"technology", "tool"}:
        return "co_occurrence"

    # Default
    return "co_occurrence"


def _calculate_weight(source: Dict, target: Dict) -> float:
    """Calculate relationship weight based on entity confidences."""
    s_conf = source.get("confidence", 0.5)
    t_conf = target.get("confidence", 0.5)

    # Average confidence of the two entities, scaled
    base_weight = (s_conf + t_conf) / 2.0

    # Same-type entities get a boost
    if source.get("type") == target.get("type"):
        base_weight = min(1.0, base_weight * 1.2)

    return round(base_weight, 3)
