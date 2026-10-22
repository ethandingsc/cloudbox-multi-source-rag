"""Offline tests for the experimental BM25/RRF path."""

import unittest

from src import hybrid_retrieve


def chunk(chunk_id, source_type, text, derived_from=None):
    item = {"chunk_id": chunk_id, "source_type": source_type,
            "text": text, "title": chunk_id, "date": "2024-05-12",
            "version": "2.1", "topics": []}
    if derived_from:
        item["synthetic"] = True
        item["derived_from"] = derived_from
    return item


class TestBM25(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            chunk("docs:api", "documentation",
                  "HTTP 429 Retry-After API rate limit 1000 requests"),
            chunk("forum:api", "forum", "API upload question"),
            chunk("blog:linux", "blog", "Ubuntu Fedora Linux desktop client"),
        ]

    def test_tokenizer_preserves_versions_and_api_tokens(self):
        self.assertEqual(hybrid_retrieve.tokenize("TLS 1.3 /v1 Retry-After"),
                         ["tls", "1.3", "v1", "retry-after"])

    def test_exact_error_code_ranks_first(self):
        index = hybrid_retrieve.BM25Index(self.chunks)
        hits = index.retrieve("What does HTTP 429 Retry-After mean?", 1)
        self.assertEqual(hits[0]["chunk_id"], "docs:api")

    def test_all_candidates_keep_valid_ids_and_metadata(self):
        index = hybrid_retrieve.BM25Index(self.chunks)
        hits = index.retrieve("API Linux", 1)
        self.assertEqual(len(hits), 3)
        self.assertEqual({h["chunk_id"] for h in hits},
                         {c["chunk_id"] for c in self.chunks})
        self.assertTrue(all(h["metadata"]["title"] for h in hits))


class TestRRF(unittest.TestCase):
    def test_rrf_deduplicates_canonical_variants(self):
        original = hybrid_retrieve.chunk_to_hit(
            chunk("docs:a", "documentation", "alpha"))
        synthetic = hybrid_retrieve.chunk_to_hit(
            chunk("blog:a-copy", "blog", "alpha", derived_from="docs:a"))
        other = hybrid_retrieve.chunk_to_hit(
            chunk("forum:b", "forum", "beta"))
        for hit in (original, synthetic, other):
            hit["weighted_score"] = 1.0
        fused = hybrid_retrieve.reciprocal_rank_fusion(
            [[original, other], [synthetic, other]], rrf_k=60)
        self.assertEqual(len(fused), 2)
        self.assertEqual(len({hybrid_retrieve.canonical_key(h) for h in fused}), 2)
        self.assertEqual(fused[0]["chunk_id"], "docs:a")


if __name__ == "__main__":
    unittest.main()
