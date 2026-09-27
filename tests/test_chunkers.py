"""Minimal stdlib tests for Step 2.1 chunking (no third-party deps).

Run from the project root in the cloudbox-rag env:
    python -m unittest discover -s tests -v
"""

import json
import unittest

from src import chunkers, config, loaders


class TestChunking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = loaders.load_documentation()
        cls.forums = loaders.load_forums()
        cls.blogs = loaders.load_blogs()
        cls.doc_chunks = chunkers.chunk_documentation(cls.docs)
        cls.forum_chunks = chunkers.chunk_forums(cls.forums)
        cls.blog_chunks = chunkers.chunk_blogs(cls.blogs)
        cls.all_chunks = cls.doc_chunks + cls.forum_chunks + cls.blog_chunks

    def test_item_counts(self):
        self.assertEqual(len(self.docs), 12)
        self.assertEqual(len(self.forums), 20)
        self.assertEqual(len(self.blogs), 8)

    def test_chunk_counts(self):
        # docs: one chunk per ## section; forums: one per thread; blogs: per section
        self.assertEqual(len(self.doc_chunks), 43)
        self.assertEqual(len(self.forum_chunks), 20)
        self.assertEqual(len(self.blog_chunks), 27)

    def test_total_chunks_within_target_range(self):
        lo, hi = config.TARGET_TOTAL_CHUNKS
        total = len(self.all_chunks)
        self.assertTrue(lo <= total <= hi,
                        f"total {total} outside target {config.TARGET_TOTAL_CHUNKS}")

    def test_forum_one_chunk_per_thread(self):
        self.assertEqual({c["chunk_id"] for c in self.forum_chunks},
                         {f"forum:{t['source_id']}" for t in self.forums})

    def test_chunk_ids_unique(self):
        ids = [c["chunk_id"] for c in self.all_chunks]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_empty_chunks_and_sane_sizes(self):
        for c in self.all_chunks:
            words = len(c["text"].split())
            self.assertTrue(words > 0, f"empty chunk: {c['chunk_id']}")
            self.assertTrue(20 <= words <= 1000,
                            f"abnormal size ({words} words): {c['chunk_id']}")

    def test_metadata_traceable_to_source(self):
        for c in self.all_chunks:
            for key in ("chunk_id", "source_type", "source_id", "title",
                        "date", "topics", "path"):
                self.assertIn(key, c, f"missing {key}: {c.get('chunk_id')}")
            self.assertIn(c["source_id"], c["chunk_id"])
            if c["source_type"] == "forum":
                self.assertIsNone(c["version"])
            elif c["source_type"] == "documentation":
                self.assertEqual(c["version"], "2.1")
            else:  # blog
                self.assertIn(c["version"], ("1.0", "2.0", "2.1"))

    def test_chunk_ids_match_eval_ground_truth(self):
        queries = json.loads(
            config.EVAL_QUERIES_FILE.read_text(encoding="utf-8"))["queries"]
        expected = {cid for q in queries for cid in q["expected_doc_ids"]}
        have = {c["chunk_id"] for c in self.all_chunks}
        self.assertTrue(expected <= have, f"missing ids: {expected - have}")

    def test_known_facts_present_in_chunks(self):
        by_id = {c["chunk_id"]: c for c in self.all_chunks}
        self.assertIn("10 GB", by_id["docs:storage-limits:free-plan-storage"]["text"])
        self.assertIn("Linux desktop client since version 2.0",
                      by_id["docs:sync:linux-desktop-client"]["text"])
        self.assertIn("2 GB",
                      by_id["docs:file-sharing:uploading-through-the-web-app"]["text"])
        self.assertIn("Pause", by_id["forum:thread-005"]["text"])
        self.assertIn("Selective Sync",
                      by_id["blog:selective-sync-tutorial:step-by-step-setup"]["text"])


if __name__ == "__main__":
    unittest.main()
