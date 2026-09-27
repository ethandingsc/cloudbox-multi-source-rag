"""CrossEncoder reranking (Step 3.2).

The reranker re-scores the Step 3.1 weighted candidate pool on
(query, chunk_text) pairs with a CrossEncoder — a far finer relevance
signal than embedding similarity — then re-sorts the pool by rerank_score
and keeps the top FINAL_EVIDENCE_SIZE candidates as the evidence for the
answer stage (Step 4).

Scores from the earlier stages (similarity, weighted_score) are kept on
every candidate so the whole scoring chain stays explainable and loggable.
Deterministic: same model weights + same inputs -> same scores, stable sort.

CrossEncoder ships with the sentence-transformers package already used for
embeddings — no new dependency.
"""

from sentence_transformers import CrossEncoder

from . import config


class Reranker:
    """Thin wrapper around the CrossEncoder model."""

    def __init__(self, model_name: str | None = None):
        self.model = CrossEncoder(model_name or config.RERANK_MODEL)

    def rerank(self, query: str, candidates: list[dict],
               top_n: int | None = None) -> list[dict]:
        """Score each (query, candidate text) pair, reorder, keep top_n.

        Returns NEW hit dicts (the input candidates stay untouched) with a
        `rerank_score` added, sorted by rerank_score descending, truncated
        to top_n (default config.FINAL_EVIDENCE_SIZE).
        """
        top_n = config.FINAL_EVIDENCE_SIZE if top_n is None else top_n
        scores = self.model.predict(
            [(query, c["text"]) for c in candidates],
            show_progress_bar=False,
        )
        reranked = []
        for c, score in zip(candidates, scores):
            hit = dict(c)
            hit["rerank_score"] = float(score)
            reranked.append(hit)
        reranked.sort(key=lambda h: h["rerank_score"], reverse=True)
        return reranked[:top_n]


def rerank(query: str, candidates: list[dict], top_n: int | None = None,
           reranker: Reranker | None = None) -> list[dict]:
    """One-shot convenience; pass a shared Reranker to avoid model reloads."""
    return (reranker or Reranker()).rerank(query, candidates, top_n=top_n)
