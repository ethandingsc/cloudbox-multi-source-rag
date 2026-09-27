"""Minimal tests for Step 3.2: CrossEncoder reranking.

Requires the ChromaDB collection from Step 2.2 (run scripts/ingest.py first)
and the cross-encoder/ms-marco-MiniLM-L-6-v2 model (downloaded on first use).

Run from the project root in the cloudbox-rag env:
    python -m unittest discover -s tests -v
"""

import unittest

from src import config, embed_store, rerank, retrieve


Q01 = "How much free storage do I get with CloudBox?"
DOCS_STORAGE_ID = "docs:storage-limits:free-plan-storage"


class TestReranker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store = embed_store.EmbedStore()
        cls.retriever = retrieve.Retriever(store)
        cls.reranker = rerank.Reranker()  # model loaded once per test run

    def test_rerank_scores_sorted_and_truncated(self):
        pool = self.retriever.retrieve_weighted(Q01)
        self.assertEqual(len(pool), config.CANDIDATE_POOL_SIZE)  # 12
        final = self.reranker.rerank(Q01, pool)
        self.assertEqual(len(final), config.FINAL_EVIDENCE_SIZE)  # 5
        scores = [h["rerank_score"] for h in final]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for h in final:
            self.assertIsInstance(h["rerank_score"], float)

    def test_all_stage_scores_and_fields_preserved(self):
        pool = self.retriever.retrieve_weighted(Q01)
        final = self.reranker.rerank(Q01, pool)
        by_id = {h["chunk_id"]: h for h in pool}
        for h in final:
            p = by_id[h["chunk_id"]]
            # retrieval + weighting stages untouched by reranking
            self.assertEqual(h["similarity"], p["similarity"])
            self.assertEqual(h["weight"], p["weight"])
            self.assertEqual(h["weighted_score"], p["weighted_score"])
            self.assertEqual(h["distance"], p["distance"])
            self.assertEqual(h["text"], p["text"])
            self.assertEqual(h["metadata"], p["metadata"])
            self.assertEqual(h["source_type"], p["source_type"])
        # reranking never mutates the pool it was given
        for p in pool:
            self.assertNotIn("rerank_score", p)

    def test_ordering_uses_rerank_score_not_weighted_score(self):
        # Real observed behavior: the CrossEncoder reorders the weighted
        # pool (e.g. forum:thread-001 jumps up on pure relevance). If the
        # two orders were identical, reranking would be a no-op.
        pool = self.retriever.retrieve_weighted(Q01)
        final = self.reranker.rerank(Q01, pool)
        reranked_ids = [h["chunk_id"] for h in final]
        weighted_top = sorted(pool, key=lambda h: h["weighted_score"],
                              reverse=True)[:len(final)]
        self.assertNotEqual(reranked_ids, [h["chunk_id"] for h in weighted_top])

    def test_retrieve_reranked_integration_and_filters(self):
        # All Sources: weighted pool -> CrossEncoder -> final evidence
        final = self.retriever.retrieve_reranked(Q01, reranker=self.reranker)
        self.assertEqual(len(final), config.FINAL_EVIDENCE_SIZE)
        # documentation only
        docs = self.retriever.retrieve_reranked(
            Q01, sources=["documentation"], reranker=self.reranker)
        self.assertTrue(docs and
                        all(h["source_type"] == "documentation" for h in docs))
        # forum only
        forum = self.retriever.retrieve_reranked(
            "sync stuck", sources="forum", reranker=self.reranker)
        self.assertTrue(forum and
                        all(h["source_type"] == "forum" for h in forum))
        # blog only
        blog = self.retriever.retrieve_reranked(
            "selective sync save disk space", sources="blog",
            reranker=self.reranker)
        self.assertTrue(blog and
                        all(h["source_type"] == "blog" for h in blog))
        # top_k still shapes the pool the reranker sees (2/source -> 6 -> 6)
        small = self.retriever.retrieve_reranked(
            Q01, top_k=2, reranker=self.reranker)
        self.assertEqual(len(small), config.FINAL_EVIDENCE_SIZE)

    def test_expected_chunk_survives_rerank(self):
        # Real observed behavior (not a hardcoded pipeline answer): the
        # current docs chunk stays in the final evidence for q01. The
        # outdated blog/forum chunks may also still be present — that is
        # Step 3.3's job to resolve, deliberately not done here.
        final = self.retriever.retrieve_reranked(Q01, reranker=self.reranker)
        self.assertIn(DOCS_STORAGE_ID, [h["chunk_id"] for h in final])

    def test_deterministic_repeated_runs(self):
        a = self.retriever.retrieve_reranked(Q01, reranker=self.reranker)
        b = self.retriever.retrieve_reranked(Q01, reranker=self.reranker)
        self.assertEqual([h["chunk_id"] for h in a], [h["chunk_id"] for h in b])
        self.assertEqual([h["rerank_score"] for h in a],
                         [h["rerank_score"] for h in b])

    def test_unknown_source_raises_through_reranked_path(self):
        with self.assertRaises(ValueError):
            self.retriever.retrieve_reranked("anything", sources=["wiki"],
                                             reranker=self.reranker)


if __name__ == "__main__":
    unittest.main()
