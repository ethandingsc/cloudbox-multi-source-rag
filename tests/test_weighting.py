"""Minimal tests for Step 3.1: deterministic source weighting.

Requires the ChromaDB collection from Step 2.2 (run scripts/ingest.py first).

Run from the project root in the cloudbox-rag env:
    python -m unittest discover -s tests -v
"""

import unittest

from src import config, embed_store, retrieve


Q01 = "How much free storage do I get with CloudBox?"
DOCS_STORAGE_ID = "docs:storage-limits:free-plan-storage"
OLD_BLOG_STORAGE_ID = "blog:free-storage-explained:what-the-free-plan-includes"


class TestSourceWeighting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store = embed_store.EmbedStore()
        cls.retriever = retrieve.Retriever(store)

    def test_weight_and_weighted_score_applied_per_source(self):
        hits = self.retriever.retrieve(Q01)
        weighted = retrieve.weight_candidates(hits)
        self.assertTrue(weighted)
        for h in weighted:
            self.assertEqual(h["weight"], config.SOURCE_WEIGHTS[h["source_type"]],
                             h["chunk_id"])
            self.assertAlmostEqual(h["weighted_score"],
                                   h["similarity"] * h["weight"],
                                   places=9)

    def test_pool_sorted_by_weighted_score_and_truncated(self):
        hits = self.retriever.retrieve(Q01)
        self.assertEqual(len(hits), 3 * config.TOP_K_PER_SOURCE)  # 15 raw
        weighted = retrieve.weight_candidates(hits)
        scores = [h["weighted_score"] for h in weighted]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(len(weighted), config.CANDIDATE_POOL_SIZE)  # 12

    def test_raw_scores_and_fields_preserved(self):
        raw = self.retriever.retrieve(Q01)
        weighted = retrieve.weight_candidates(raw)
        by_id = {h["chunk_id"]: h for h in raw}
        for h in weighted:
            r = by_id[h["chunk_id"]]
            self.assertEqual(h["similarity"], r["similarity"])
            self.assertEqual(h["distance"], r["distance"])
            self.assertEqual(h["text"], r["text"])
            self.assertEqual(h["metadata"], r["metadata"])
            self.assertEqual(h["source_type"], r["source_type"])
        # raw hits stay untouched (no weight keys)
        for r in raw:
            self.assertNotIn("weight", r)
            self.assertNotIn("weighted_score", r)

    def test_weighting_puts_current_docs_above_old_blog_for_q01(self):
        # Before weighting the outdated v1.0 blog ("5 GB") has the highest
        # raw similarity — that is exactly the problem weighting must fix.
        raw = self.retriever.retrieve(Q01)
        raw_sim = {h["chunk_id"]: h["similarity"] for h in raw}
        self.assertGreater(raw_sim[OLD_BLOG_STORAGE_ID], raw_sim[DOCS_STORAGE_ID])
        # After weighting the official docs chunk ranks first.
        weighted = retrieve.weight_candidates(raw)
        self.assertEqual(weighted[0]["chunk_id"], DOCS_STORAGE_ID)
        pool_sim = {h["chunk_id"]: h["weighted_score"] for h in weighted}
        self.assertGreater(pool_sim[DOCS_STORAGE_ID], pool_sim[OLD_BLOG_STORAGE_ID])

    def test_single_source_filter_with_weighting(self):
        weighted = self.retriever.retrieve_weighted(
            "sync stuck", sources="forum")
        self.assertTrue(weighted and
                        all(h["source_type"] == "forum" for h in weighted))
        # constant weight within one source -> order matches raw retrieval
        raw = self.retriever.retrieve("sync stuck", sources="forum")
        self.assertEqual([h["chunk_id"] for h in weighted],
                         [h["chunk_id"] for h in raw])
        # pool size only truncates when there are more hits than the pool
        self.assertEqual(len(weighted), config.TOP_K_PER_SOURCE)

    def test_top_k_respected_with_weighting(self):
        raw = self.retriever.retrieve(Q01, top_k=2)
        self.assertEqual(len(raw), 6)
        weighted = self.retriever.retrieve_weighted(Q01, top_k=2)
        self.assertEqual(len(weighted), 6)
        self.assertEqual(len({h["chunk_id"] for h in weighted}), 6)

    def test_deterministic_across_repeated_runs(self):
        first = self.retriever.retrieve_weighted(Q01)
        second = self.retriever.retrieve_weighted(Q01)
        self.assertEqual([h["chunk_id"] for h in first],
                         [h["chunk_id"] for h in second])
        self.assertEqual([h["weighted_score"] for h in first],
                         [h["weighted_score"] for h in second])

    def test_unknown_source_still_raises(self):
        with self.assertRaises(ValueError):
            self.retriever.retrieve_weighted("anything", sources=["wiki"])


if __name__ == "__main__":
    unittest.main()
