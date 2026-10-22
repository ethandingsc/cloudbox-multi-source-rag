"""Lightweight BM25 and RRF utilities for the Step 1.5 experiment.

This module is intentionally separate from ``src.retrieve`` so the production
dense pipeline remains unchanged until the ablation result justifies adoption.
It uses the same in-memory chunks and canonical ``derived_from`` identity as
the ChromaDB path.
"""

import math
import re
from collections import Counter, defaultdict

from . import config


TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    """Lowercase word/code tokenizer; preserve versions and API-like tokens."""
    return TOKEN_RE.findall(text.lower())


def canonical_key(hit: dict) -> str:
    return hit.get("metadata", {}).get("derived_from") or hit["chunk_id"]


def chunk_to_hit(chunk: dict) -> dict:
    metadata = {k: v for k, v in chunk.items()
                if k not in {"chunk_id", "text", "source_type"}}
    return {"chunk_id": chunk["chunk_id"],
            "source_type": chunk["source_type"],
            "text": chunk["text"], "metadata": metadata}


def weighted_unique(hits: list[dict], score_field: str,
                    limit: int | None = None) -> list[dict]:
    """Apply existing source weights, sort, and collapse canonical variants."""
    ranked = []
    for hit in hits:
        item = dict(hit)
        item["weight"] = config.SOURCE_WEIGHTS[item["source_type"]]
        item["weighted_score"] = item[score_field] * item["weight"]
        ranked.append(item)
    ranked.sort(key=lambda h: (-h["weighted_score"], h["chunk_id"]))
    unique = []
    seen = set()
    for hit in ranked:
        key = canonical_key(hit)
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
        if limit is not None and len(unique) >= limit:
            break
    return unique


class BM25Index:
    """Small Okapi BM25 index over the exact 590 evaluation chunks."""

    def __init__(self, chunks: list[dict], k1: float = 1.5, b: float = 0.75):
        self.hits = [chunk_to_hit(chunk) for chunk in chunks]
        self.k1 = k1
        self.b = b
        self.term_frequencies = []
        self.lengths = []
        document_frequency = Counter()
        for hit in self.hits:
            terms = tokenize(hit["text"])
            counts = Counter(terms)
            self.term_frequencies.append(counts)
            self.lengths.append(len(terms))
            document_frequency.update(counts.keys())
        self.average_length = (sum(self.lengths) / len(self.lengths)
                               if self.lengths else 0.0)
        n = len(self.hits)
        self.idf = {
            term: math.log(1.0 + (n - df + 0.5) / (df + 0.5))
            for term, df in document_frequency.items()
        }

    def score(self, query: str) -> list[float]:
        query_terms = Counter(tokenize(query))
        scores = []
        for frequencies, length in zip(self.term_frequencies, self.lengths):
            score = 0.0
            norm = self.k1 * (1.0 - self.b + self.b * length /
                              (self.average_length or 1.0))
            for term, query_frequency in query_terms.items():
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                score += (self.idf.get(term, 0.0) * query_frequency *
                          frequency * (self.k1 + 1.0) / (frequency + norm))
            scores.append(score)
        return scores

    def retrieve(self, query: str, top_k_per_source: int | None = None) -> list[dict]:
        """Return source-balanced sparse candidates, matching dense breadth."""
        top_k = config.TOP_K_PER_SOURCE if top_k_per_source is None else top_k_per_source
        by_source = defaultdict(list)
        for hit, score in zip(self.hits, self.score(query)):
            item = dict(hit)
            item["bm25_score"] = float(score)
            by_source[item["source_type"]].append(item)

        output = []
        for source_type in config.SOURCE_TYPES:
            ranked = sorted(by_source[source_type],
                            key=lambda h: (-h["bm25_score"], h["chunk_id"]))
            seen = set()
            for hit in ranked:
                key = canonical_key(hit)
                if key in seen:
                    continue
                seen.add(key)
                output.append(hit)
                if len(seen) == top_k:
                    break
        output.sort(key=lambda h: (-h["bm25_score"], h["chunk_id"]))
        return output


def dense_weighted_ranking(dense_hits: list[dict]) -> list[dict]:
    """Prepare existing dense hits for fair rank fusion."""
    prepared = []
    for hit in dense_hits:
        item = dict(hit)
        item["dense_score"] = item["similarity"]
        prepared.append(item)
    return weighted_unique(prepared, "dense_score")


def bm25_weighted_ranking(bm25_hits: list[dict]) -> list[dict]:
    return weighted_unique(bm25_hits, "bm25_score")


def reciprocal_rank_fusion(rankings: list[list[dict]], rrf_k: int = 60,
                           limit: int | None = None) -> list[dict]:
    """Fuse canonical candidates once per ranking, with deterministic ties."""
    scores = defaultdict(float)
    representatives = {}
    for ranking in rankings:
        seen = set()
        for rank, hit in enumerate(ranking, 1):
            key = canonical_key(hit)
            if key in seen:
                continue
            seen.add(key)
            scores[key] += 1.0 / (rrf_k + rank)
            current = representatives.get(key)
            if current is None or (
                    config.SOURCE_WEIGHTS[hit["source_type"]],
                    hit.get("weighted_score", 0.0), hit["chunk_id"]) > (
                    config.SOURCE_WEIGHTS[current["source_type"]],
                    current.get("weighted_score", 0.0), current["chunk_id"]):
                representatives[key] = hit

    fused = []
    for key, score in scores.items():
        item = dict(representatives[key])
        item["rrf_score"] = score
        fused.append(item)
    fused.sort(key=lambda h: (-h["rrf_score"], h["chunk_id"]))
    return fused[:limit] if limit is not None else fused
