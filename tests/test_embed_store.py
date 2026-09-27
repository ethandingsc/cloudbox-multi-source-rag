"""Minimal tests for Step 2.2: embedding + ChromaDB ingestion.

Requires the Step 2.2 dependencies (chromadb, sentence-transformers) and a
HuggingFace download of all-MiniLM-L6-v2 on first run. Ingestion is
idempotent, so tests re-embedding the same chunks are safe.

Run from the project root in the cloudbox-rag env:
    python -m unittest discover -s tests -v
"""

import unittest

from src import chunkers, config, embed_store


class TestEmbedStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chunks = chunkers.run()
        cls.store = embed_store.EmbedStore()
        cls.store.upsert_chunks(cls.chunks)

    def test_collection_and_dimension(self):
        self.assertEqual(self.store.collection.name, config.CHROMA_COLLECTION)
        # all-MiniLM-L6-v2 produces 384-dim embeddings
        self.assertEqual(self.store.embedding_dim, 384)

    def test_total_count_matches_chunk_count(self):
        self.assertEqual(self.store.count(), len(self.chunks))
        lo, hi = config.TARGET_TOTAL_CHUNKS
        self.assertTrue(lo <= self.store.count() <= hi)

    def test_counts_per_source_type(self):
        for src in ("documentation", "forum", "blog"):
            expected = sum(1 for c in self.chunks if c["source_type"] == src)
            # get() returns a 7-field GetResult namedtuple — count ids, not
            # len(result); explicit limit guards against any default batch cap.
            got = self.store.collection.get(where={"source_type": src},
                                            include=[], limit=10_000)
            self.assertEqual(len(got["ids"]), expected, src)

    def test_known_records_have_text_metadata_and_embeddings(self):
        for cid in ("docs:storage-limits:free-plan-storage",
                    "forum:thread-005",
                    "blog:selective-sync-tutorial:step-by-step-setup"):
            res = self.store.collection.get(
                ids=[cid], include=["documents", "metadatas", "embeddings"])
            self.assertEqual(res["ids"], [cid])
            self.assertTrue(res["documents"][0].strip(), cid)
            meta = res["metadatas"][0]
            self.assertIn(meta["source_type"], config.SOURCE_TYPES)
            self.assertIn(meta["source_id"], cid)
            self.assertTrue(meta["title"])
            self.assertEqual(len(res["embeddings"][0]), 384)
            # Chroma 0.6 allows only scalar metadata: topics is stored joined
            self.assertIsInstance(meta["topics"], str)
            if meta["source_type"] == "forum":
                self.assertNotIn("version", meta)

    def test_reingestion_is_idempotent(self):
        self.store.upsert_chunks(self.chunks)
        self.assertEqual(self.store.count(), len(self.chunks))
        ids = self.store.collection.get(include=[])["ids"]
        self.assertEqual(len(ids), len(set(ids)), "duplicate ids in collection")


if __name__ == "__main__":
    unittest.main()
