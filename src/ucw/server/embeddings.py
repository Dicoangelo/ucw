"""
Embedding Pipeline — Semantic vectors for cognitive events

Embeds event content using SBERT (local).
Stores vectors for similarity search.

Supports:
  - Real-time: embed single events as they're captured
  - Batch: embed all existing events
  - Search: find similar events by cosine similarity
"""

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from ucw.server.logger import get_logger

log = get_logger("embeddings")

# Lazy-load model to avoid import-time overhead
_model = None
_model_name = "all-MiniLM-L6-v2"
_dimensions = 384


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_model_name)
        log.info(f"Loaded embedding model: {_model_name} ({_dimensions}d)")
    return _model


def build_embed_text(event_or_dict) -> str:
    """
    Build the text to embed from a cognitive event.
    Format: "{intent}: {topic} | {summary} | {concepts}"
    """
    if hasattr(event_or_dict, "light_layer"):
        light = event_or_dict.light_layer or {}
        data = event_or_dict.data_layer or {}
    elif isinstance(event_or_dict, dict):
        light_raw = event_or_dict.get("light_layer", "{}")
        data_raw = event_or_dict.get("data_layer", "{}")
        light = json.loads(light_raw) if isinstance(light_raw, str) else (light_raw or {})
        data = json.loads(data_raw) if isinstance(data_raw, str) else (data_raw or {})
    else:
        return ""

    intent = light.get("intent", "explore")
    topic = light.get("topic", "general")
    summary = light.get("summary", "")
    concepts = light.get("concepts", [])
    content = data.get("content", "")

    parts = [f"{intent}: {topic}"]
    if summary:
        parts.append(summary[:300])
    elif content:
        parts.append(content[:300])
    if concepts:
        parts.append(" ".join(concepts))

    return " | ".join(parts)


def content_hash(text: str) -> str:
    """SHA-256 hash for dedup."""
    return hashlib.sha256(text.encode()).hexdigest()


def embed_texts(texts: List[str], batch_size: int = 64) -> List[List[float]]:
    """Embed a batch of texts. Returns list of float vectors."""
    model = _get_model()
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False)
    return [e.tolist() for e in embeddings]


def embed_single(text: str) -> List[float]:
    """Embed a single text. Returns float vector."""
    model = _get_model()
    return model.encode(text, show_progress_bar=False).tolist()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    import numpy as np
    a_arr = np.array(a)
    b_arr = np.array(b)
    dot = np.dot(a_arr, b_arr)
    norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if norm == 0:
        return 0.0
    return float(dot / norm)


class EmbeddingPipeline:
    """
    Embedding pipeline for SQLite-backed UCW.

    Usage:
        pipeline = EmbeddingPipeline()
        await pipeline.embed_event(event)
    """

    def __init__(self):
        pass

    async def embed_event(self, event) -> Optional[List[float]]:
        """Embed a single capture event."""
        text = build_embed_text(event)
        if not text or len(text) < 10:
            return None
        return embed_single(text)
