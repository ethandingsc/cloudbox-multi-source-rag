"""Minimal tests for Step 2.3: basic multi-source retrieval (no weighting).

Requires the ChromaDB collection from Step 2.2 (run scripts/ingest.py first).

Run from the project root in the cloudbox-rag env:
    python -m unittest discover -s tests -v
"""

import unittest

from src import config, embed_store, retrieve


class TestRetriever(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store = embed_store.EmbedStore()
        cls.retriever = retrieve.Retriever(store)

    def test_all_sources_return_top_k_with_scores_and_metadata(self):
        hits = self.retriever.retrieve("How much free storage do I get with CloudBox?")
        per_source = {src: [h for h in hits if h["source_type"] == src]
                      for src in config.SOURCE_TYPES}
        # each of the three sources returns exactly TOP_K_PER_SOURCE results
        for src in config.SOURCE_TYPES:
            self.assertEqual(len(per_source[src]), config.TOP_K_PER_SOURCE, src)
        # every hit carries the full contract
        for h in hits:
            self.assertTrue(h["chunk_id"])
            self.assertTrue(h["text"].strip())
            self.assertIn(h["source_type"], config.SOURCE_TYPES)
            self.assertIn("title", h["metadata"])
            self.assertIn("source_id", h["metadata"])
            self.assertIsInstance(h["similarity"], float)
            self.assertIsInstance(h["distance"], float)

    def test_merged_list_sorted_by_similarity_desc(self):
        hits = self.retriever.retrieve("How do I share a file with a link?")
        sims = [h["similarity"] for h in hits]
        self.assertEqual(sims, sorted(sims, reverse=True))
        # within each source Chroma already returns nearest-first (distance asc)
        for src in config.SOURCE_TYPES:
            distances = [h["distance"] for h in hits if h["source_type"] == src]
            self.assertEqual(distances, sorted(distances), src)

    def test_source_filter_restricts_retrieval(self):
        only_docs = self.retriever.retrieve(
            "cloudbox storage", sources=["documentation"])
        self.assertTrue(only_docs and
                        all(h["source_type"] == "documentation" for h in only_docs))
        # string shorthand works too
        only_forum = self.retriever.retrieve("sync stuck", sources="forum")
        self.assertTrue(all(h["source_type"] == "forum" for h in only_forum))

    def test_unknown_source_type_raises(self):
        with self.assertRaises(ValueError):
            self.retriever.retrieve("anything", sources=["wiki"])

    def test_eval_queries_surface_expected_chunks(self):
        # q01 storage (docs-only): current doc chunk ranks first
        hits = self.retriever.retrieve(
            "How much free storage do I get with CloudBox?",
            sources=["documentation"])
        self.assertEqual(hits[0]["chunk_id"], "docs:storage-limits:free-plan-storage")
        # q04 linux (docs-only): current doc chunk ranks first
        hits = self.retriever.retrieve(
            "Does CloudBox have a Linux client?", sources=["documentation"])
        self.assertEqual(hits[0]["chunk_id"], "docs:sync:linux-desktop-client")
        # q06 forum: the accepted-answer thread ranks first
        hits = self.retriever.retrieve(
            "My sync client has been stuck on 'Syncing…' for hours. "
            "What should I do?", sources=["forum"])
        self.assertEqual(hits[0]["chunk_id"], "forum:thread-005")
        # q08 blog: the step-by-step section appears in the blog top-5
        hits = self.retriever.retrieve(
            "How do I set up selective sync to save disk space?",
            sources=["blog"])
        self.assertIn("blog:selective-sync-tutorial:step-by-step-setup",
                      [h["chunk_id"] for h in hits])

    def test_conflict_material_is_retrieved_for_conflict_queries(self):
        # q01: outdated v1.0 blog ("5 GB") and the forum thread about free
        # storage must be surfaced alongside the current docs — Step 3 relies
        # on seeing both sides. (No resolution here: Step 2.3 only retrieves.)
        hits = self.retriever.retrieve(
            "How much free storage do I get with CloudBox?")
        ids = [h["chunk_id"] for h in hits]
        self.assertIn("docs:storage-limits:free-plan-storage", ids)
        self.assertIn("blog:free-storage-explained:what-the-free-plan-includes", ids)
        self.assertIn("forum:thread-001", ids)


if __name__ == "__main__":
    unittest.main()
