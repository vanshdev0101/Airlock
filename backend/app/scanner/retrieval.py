"""Chroma-backed retrieval over the known threat-pattern corpus.

Embeds ``knowledge.threat_patterns`` into a local, on-disk Chroma collection
(seeded once, reused after) and returns the k nearest patterns to a given
README so the AI analyzer can ground its judgment in concrete known-bad
examples instead of reasoning from scratch.
"""

from pathlib import Path

import chromadb

from .knowledge.threat_patterns import THREAT_PATTERNS

_PERSIST_DIR = Path(__file__).resolve().parents[2] / ".chroma"
_COLLECTION_NAME = "model_card_threat_patterns"

_collection = None


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection

    client = chromadb.PersistentClient(path=str(_PERSIST_DIR))
    collection = client.get_or_create_collection(_COLLECTION_NAME)
    if collection.count() == 0:
        collection.add(
            ids=[p["id"] for p in THREAT_PATTERNS],
            documents=[p["text"] for p in THREAT_PATTERNS],
            metadatas=[
                {"pattern_name": p["pattern_name"], "description": p["description"]}
                for p in THREAT_PATTERNS
            ],
        )
    _collection = collection
    return _collection


def retrieve_similar_patterns(text: str, k: int = 4) -> list[dict]:
    """Return the k known threat patterns most similar to ``text``."""
    collection = _get_collection()
    result = collection.query(
        query_texts=[text[:2000]],
        n_results=min(k, len(THREAT_PATTERNS)),
    )
    return [
        {"text": doc, **meta}
        for doc, meta in zip(result["documents"][0], result["metadatas"][0])
    ]
