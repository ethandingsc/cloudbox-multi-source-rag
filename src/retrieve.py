"""Multi-source retrieval: per-source top-k (Step 2.3) + source weighting (Step 3.1).

The single ChromaDB collection is queried once per source type with a
metadata filter (documentation / forum / blog), TOP_K_PER_SOURCE hits each,
then merged into one candidate list sorted by raw similarity. An optional
source-type filter restricts retrieval to a subset — used later by the
Demo UI's single-source modes (Step 5.4).

Step 3.1 lays a deterministic weighting stage on top without changing the
shape: `weight_candidates()` computes weighted_score = similarity ×
SOURCE_WEIGHTS[source_type], re-sorts, and keeps the top
CANDIDATE_POOL_SIZE as the pool the Step 3.2 reranker consumes.
`retrieve_reranked()` chains that pool into src.rerank (CrossEncoder);
`retrieve_final()` adds the Step 3.3 deterministic conflict rules
(src.conflict). Raw similarity is always preserved on every hit. Reuses
the existing EmbedStore — no second index is built, no re-embedding.
"""

from . import config
from .embed_store import EmbedStore


def weight_candidates(hits: list[dict], pool_size: int | None = None) -> list[dict]:
    """Step 3.1: apply the fixed per-source weight to raw retrieval hits.

    weighted_score = similarity × SOURCE_WEIGHTS[source_type] (weights live
    ONLY in config.py). Returns a NEW list of hit dicts — the input raw
    hits stay untouched so both stages can be logged — sorted by
    weighted_score descending and truncated to pool_size (default
    CANDIDATE_POOL_SIZE), the pool Step 3.2's reranker consumes.

    Deterministic: constant weights + stable sort.
    """
    pool_size = config.CANDIDATE_POOL_SIZE if pool_size is None else pool_size
    weighted = []
    for h in hits:
        w = dict(h)
        w["weight"] = config.SOURCE_WEIGHTS[w["source_type"]]
        w["weighted_score"] = w["similarity"] * w["weight"]
        weighted.append(w)
    weighted.sort(key=lambda h: h["weighted_score"], reverse=True)
    return weighted[:pool_size]


class Retriever:
    """Queries the shared ChromaDB collection per source type."""

    def __init__(self, store: EmbedStore | None = None):
        self.store = store or EmbedStore()

    def retrieve(self, query: str, sources=None, top_k: int | None = None) -> list[dict]:
        """Return merged hits from one or more source types, best first.

        sources: None (all three), a source_type string, or a list of them.
        Each hit carries chunk_id, text, metadata, source_type, and both the
        raw cosine distance and similarity = 1 - distance. Sorting is by
        raw similarity only — no weighting (that is retrieve_weighted).
        """
        sources = self._normalize_sources(sources)
        top_k = config.TOP_K_PER_SOURCE if top_k is None else top_k
        query_embedding = self.store.model.encode(
            [query], normalize_embeddings=True).tolist()

        hits: list[dict] = []
        for src in sources:
            res = self.store.collection.query(
                query_embeddings=query_embedding,
                n_results=top_k,
                where={"source_type": src},
                include=["documents", "metadatas", "distances"],
            )
            hits.extend(self._as_hits(res, src))

        hits.sort(key=lambda h: h["similarity"], reverse=True)
        return hits

    def retrieve_weighted(self, query: str, sources=None, top_k: int | None = None,
                          pool_size: int | None = None) -> list[dict]:
        """retrieve() + the Step 3.1 weighting stage (weighted_score, pool)."""
        return weight_candidates(
            self.retrieve(query, sources=sources, top_k=top_k),
            pool_size=pool_size)

    def retrieve_reranked(self, query: str, sources=None, top_k: int | None = None,
                          pool_size: int | None = None,
                          final_size: int | None = None,
                          reranker=None) -> list[dict]:
        """retrieve_weighted() + the Step 3.2 CrossEncoder reranking stage.

        reranker: a shared src.rerank.Reranker instance (model loaded once);
        when omitted, one is created for this call. The import is lazy so
        plain retrieval never pays the CrossEncoder load.
        """
        from . import rerank  # lazy: keep CrossEncoder out of retrieval-only use
        pool = self.retrieve_weighted(query, sources=sources, top_k=top_k,
                                      pool_size=pool_size)
        return rerank.rerank(query, pool, top_n=final_size, reranker=reranker)

    def retrieve_final(self, query: str, sources=None, top_k: int | None = None,
                       pool_size: int | None = None,
                       final_size: int | None = None,
                       reranker=None) -> dict:
        """retrieve_reranked() + Step 3.3 deterministic contradiction handling.

        Returns {"evidence": [...], "conflicts": [...]}. Single-source
        retrieval skips the conflict rules (PLAN §5.4: nothing to compare)
        — every hit is marked conflict_status "kept". The import is lazy.
        """
        from . import conflict  # lazy
        evidence = self.retrieve_reranked(query, sources=sources, top_k=top_k,
                                          pool_size=pool_size,
                                          final_size=final_size,
                                          reranker=reranker)
        single_source = (isinstance(sources, str)
                         or (sources is not None and len(sources) == 1))
        if single_source:
            return {"evidence": [dict(h, conflict_status="kept") for h in evidence],
                    "conflicts": []}
        return conflict.handle_contradictions(evidence)

    @staticmethod
    def _normalize_sources(sources) -> tuple:
        if sources is None:
            return config.SOURCE_TYPES
        if isinstance(sources, str):
            sources = [sources]
        unknown = [s for s in sources if s not in config.SOURCE_TYPES]
        if unknown:
            raise ValueError(
                f"unknown source_type(s): {unknown}; expected one of {config.SOURCE_TYPES}")
        return tuple(sources)

    @staticmethod
    def _as_hits(res: dict, source_type: str) -> list[dict]:
        """Chroma query result rows -> hit dicts (topics list restored)."""
        hits = []
        for i, cid in enumerate(res["ids"][0]):
            meta = dict(res["metadatas"][0][i])
            # topics was persisted joined (Chroma 0.6 scalars only); restore
            topics = meta.get("topics")
            if isinstance(topics, str):
                meta["topics"] = [t.strip() for t in topics.split(",") if t.strip()]
            hits.append({
                "chunk_id": cid,
                "source_type": source_type,
                "text": res["documents"][0][i],
                "metadata": meta,
                "distance": float(res["distances"][0][i]),
                # collection uses hnsw:space cosine -> distances are cosine
                # distances; similarity = 1 - distance
                "similarity": 1.0 - float(res["distances"][0][i]),
            })
        return hits


def retrieve(query: str, sources=None, top_k: int | None = None,
             store: EmbedStore | None = None) -> list[dict]:
    """One-shot convenience for callers that don't reuse the store."""
    return Retriever(store).retrieve(query, sources=sources, top_k=top_k)


def retrieve_weighted(query: str, sources=None, top_k: int | None = None,
                      pool_size: int | None = None,
                      store: EmbedStore | None = None) -> list[dict]:
    """One-shot: raw retrieval + Step 3.1 source weighting."""
    return Retriever(store).retrieve_weighted(
        query, sources=sources, top_k=top_k, pool_size=pool_size)


def retrieve_reranked(query: str, sources=None, top_k: int | None = None,
                      pool_size: int | None = None,
                      final_size: int | None = None,
                      store: EmbedStore | None = None,
                      reranker=None) -> list[dict]:
    """One-shot: retrieval + weighting + Step 3.2 CrossEncoder reranking."""
    return Retriever(store).retrieve_reranked(
        query, sources=sources, top_k=top_k, pool_size=pool_size,
        final_size=final_size, reranker=reranker)


def retrieve_final(query: str, sources=None, top_k: int | None = None,
                   pool_size: int | None = None,
                   final_size: int | None = None,
                   store: EmbedStore | None = None,
                   reranker=None) -> dict:
    """One-shot: retrieval + weighting + reranking + Step 3.3 conflict rules."""
    return Retriever(store).retrieve_final(
        query, sources=sources, top_k=top_k, pool_size=pool_size,
        final_size=final_size, reranker=reranker)
