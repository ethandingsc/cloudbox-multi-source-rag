"""Embedding + ChromaDB storage (Step 2.2).

Pipeline: Step 2.1 chunks -> sentence-transformers embeddings -> one local
persistent ChromaDB collection. Chunk ids are deterministic (PLAN.md §4),
so upserting the same chunks again is idempotent — no duplicates.
"""

import os

# Chroma 0.6 still checks this env var at import time; Settings(...) alone is
# not enough to silence the product-telemetry warnings.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from . import config


class EmbedStore:
    """Thin wrapper around sentence-transformers + ChromaDB (local, no server)."""

    def __init__(self, model_name: str | None = None, chroma_dir=None):
        self.model = SentenceTransformer(model_name or config.EMBED_MODEL)
        self.client = chromadb.PersistentClient(
            path=str(chroma_dir or config.CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=config.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def embedding_dim(self) -> int:
        return self.model.get_sentence_embedding_dimension()

    @staticmethod
    def _metadata(chunk: dict) -> dict:
        """Chunk dict -> Chroma metadata.

        None values are dropped (Chroma rejects them — e.g. forums have no
        version). List values (topics) are joined to a comma-separated string:
        Chroma 0.6 accepts only scalar metadata values. The in-memory chunk
        keeps the original list; only the persisted copy is stringified."""
        meta = {}
        for k, v in chunk.items():
            if k in ("chunk_id", "text") or v is None:
                continue
            meta[k] = ", ".join(v) if isinstance(v, list) else v
        return meta

    def upsert_chunks(self, chunks: list) -> None:
        """Embed all chunks and upsert by chunk_id. Idempotent by design."""
        ids = [c["chunk_id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [self._metadata(c) for c in chunks]
        embeddings = self.model.encode(documents, normalize_embeddings=True).tolist()
        self.collection.upsert(ids=ids, documents=documents,
                               metadatas=metadatas, embeddings=embeddings)

    def reset(self) -> None:
        """Drop and recreate the collection (used by `ingest.py --reset`)."""
        self.client.delete_collection(config.CHROMA_COLLECTION)
        self.collection = self.client.get_or_create_collection(
            name=config.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        return self.collection.count()
