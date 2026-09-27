"""Minimal tests for Step 3.3: deterministic contradiction handling (no LLM).

Requires the ChromaDB collection from Step 2.2 and the rerank model from
Step 3.2. All assertions below reflect the real behavior of the dataset's
designed contradiction cases — nothing in the pipeline is hardcoded to
game them.

Run from the project root in the cloudbox-rag env:
    python -m unittest discover -s tests -v
"""

import unittest

from src import conflict, config, embed_store, rerank, retrieve

Q01 = "How much free storage do I get with CloudBox?"
Q02 = "What is the largest file I can upload to CloudBox?"
Q03 = "Is two-factor authentication required for organization accounts?"
Q04 = "Does CloudBox have a Linux client?"

DOCS_STORAGE = "docs:storage-limits:free-plan-storage"
DOCS_UPLOAD = "docs:storage-limits:maximum-upload-size"
DOCS_2FA = "docs:security:two-factor-authentication-policy"
DOCS_LINUX = "docs:sync:linux-desktop-client"

CASES = [
    (Q01, DOCS_STORAGE, [
        ("forum:thread-001", "superseded_by_current_docs"),
        ("blog:free-storage-explained:what-the-free-plan-includes",
         "superseded_version"),
    ]),
    (Q02, DOCS_UPLOAD, [
        ("forum:thread-002", "superseded_by_current_docs"),
        ("blog:upload-limits-explained:the-5-gb-ceiling", "superseded_version"),
    ]),
    (Q03, DOCS_2FA, [
        # post-v2.1 thread (Nov 2024): NOT suppressed by date — flagged
        ("forum:thread-003", "conflict_candidate"),
        ("blog:whats-new-21:mandatory-2fa-for-organizations",
         "conflict_candidate"),
    ]),
    (Q04, DOCS_LINUX, [
        ("blog:linux-client-arrives:the-long-wait-is-over", "superseded_version"),
        ("forum:thread-004", "superseded_by_current_docs"),
    ]),
]

NON_CONFLICT_QUERIES = [
    "How do I share a file with someone outside my organization?",
    "My sync client has been stuck on 'Syncing…' for hours. What should I do?",
    "Can I recover a file I deleted 45 days ago?",
    "How do I set up selective sync to save disk space?",
    "What happens to my shared links when I downgrade my plan?",
    "What are best practices for organizing team folders at scale?",
    "Users report uploads failing for files over 2 GB — why?",
    "Does CloudBox encrypt files at rest?",
]
NON_CONFLICT_EXPECTED = {
    4: ["docs:file-sharing:sharing-files-and-folders",
        "docs:file-sharing:external-users"],
    5: ["forum:thread-005"],
    6: ["forum:thread-006", "docs:recycle-bin:retention-periods-by-plan"],
    7: ["blog:selective-sync-tutorial:step-by-step-setup"],
    8: ["docs:billing:downgrading-your-plan"],
    9: ["blog:team-folder-structure:a-structure-that-scales"],
    10: ["docs:file-sharing:uploading-through-the-web-app"],
    11: ["docs:security:encryption-at-rest-and-in-transit"],
}


class TestConflictHandling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store = embed_store.EmbedStore()
        cls.retriever = retrieve.Retriever(store)
        cls.reranker = rerank.Reranker()

    def _resolve(self, query):
        evidence = self.retriever.retrieve_reranked(
            query, reranker=self.reranker)
        return evidence, conflict.handle_contradictions(evidence)

    def test_four_contradiction_cases_resolved_by_rules(self):
        for query, docs_id, expected_records in CASES:
            evidence, result = self._resolve(query)
            by_id = {h["chunk_id"]: h for h in result["evidence"]}
            # current documentation is kept
            self.assertEqual(by_id[docs_id]["conflict_status"], "kept", query)
            # each designed conflict chunk gets the designed treatment
            for chunk_id, rule in expected_records:
                self.assertIn(chunk_id, by_id, query)
                status = by_id[chunk_id]["conflict_status"]
                if rule == "conflict_candidate":
                    self.assertEqual(status, "conflict_candidate", chunk_id)
                    self.assertEqual(by_id[chunk_id]["authority"], "community")
                else:
                    self.assertEqual(status, "suppressed", chunk_id)
                    self.assertEqual(by_id[chunk_id]["suppressed_reason"], rule)
            # conflicts list records rule + affected id + winner for each case
            records = {(c["chunk_id"], c["rule"]) for c in result["conflicts"]}
            for chunk_id, rule in expected_records:
                self.assertIn((chunk_id, rule), records, query)

    def test_docs_never_suppressed(self):
        for query in (Q01, Q02, Q03, Q04):
            _, result = self._resolve(query)
            for h in result["evidence"]:
                if h["source_type"] == "documentation":
                    self.assertEqual(h["conflict_status"], "kept", h["chunk_id"])

    def test_suppressed_entries_marked_with_valid_reason(self):
        _, result = self._resolve(Q01)
        for h in result["evidence"]:
            if h["conflict_status"] == "suppressed":
                self.assertIn(h["suppressed_reason"],
                              ("superseded_version",
                               "superseded_by_current_docs"))
                # every suppressed chunk is also recorded in conflicts
                ids = {c["chunk_id"] for c in result["conflicts"]}
                self.assertIn(h["chunk_id"], ids)
        # every conflict record names the rule that was applied
        for c in result["conflicts"]:
            self.assertIn(c["rule"],
                          ("superseded_version", "superseded_by_current_docs",
                           "conflict_candidate"))

    def test_non_conflict_queries_expected_evidence_not_suppressed(self):
        # q05-q12 (indexes 4-11 in eval order): no expected chunk may be
        # suppressed — normal queries keep working.
        for idx, query in enumerate(NON_CONFLICT_QUERIES):
            evidence, result = self._resolve(query)
            by_id = {h["chunk_id"]: h for h in result["evidence"]}
            for expected in NON_CONFLICT_EXPECTED[idx + 4]:
                self.assertIn(expected, by_id, query)  # survives into final evidence
                self.assertNotEqual(by_id[expected]["conflict_status"],
                                    "suppressed", expected)

    def test_scores_metadata_preserved_and_input_not_mutated(self):
        evidence, result = self._resolve(Q01)
        by_id = {h["chunk_id"]: h for h in evidence}
        for h in result["evidence"]:
            src = by_id[h["chunk_id"]]
            for key in ("similarity", "weight", "weighted_score",
                        "rerank_score", "distance", "text", "metadata",
                        "source_type"):
                self.assertEqual(h[key], src[key], key)
        # original reranked candidates stay untouched
        for h in evidence:
            self.assertNotIn("conflict_status", h)
            self.assertNotIn("suppressed_reason", h)

    def test_single_source_skips_conflict_rules(self):
        # PLAN §5.4: single-source modes have nothing to compare — the old
        # forum threads must NOT be suppressed in forum-only mode.
        for src in ("documentation", "forum", "blog"):
            result = self.retriever.retrieve_final(
                Q01, sources=src, reranker=self.reranker)
            self.assertEqual(result["conflicts"], [], src)
            self.assertTrue(result["evidence"], src)
            for h in result["evidence"]:
                self.assertEqual(h["source_type"], src)
                self.assertEqual(h["conflict_status"], "kept")

    def test_consistent_query_has_no_suppressions(self):
        # q10 (team folders): the v2.1 team-folder blogs share topics with
        # the current docs chunk docs:teams:shared-team-folders. Since
        # Step 5.2.5 (FINAL_EVIDENCE_SIZE=6) the docs chunk also fits in the
        # evidence — at size 5 it was rank 6 and cut, so no pair existed and
        # conflicts was empty. Designed outcome for the wider window, not a
        # bug: nothing is suppressed — the blogs are flagged
        # conflict_candidate (community authority), the docs chunk stays the
        # winner. The 12-query evaluation confirmed q10 unchanged (Correct).
        evidence, result = self._resolve(
            "What are best practices for organizing team folders at scale?")
        self.assertTrue(evidence)
        records = {(c["chunk_id"], c["rule"]) for c in result["conflicts"]}
        self.assertEqual(records, {
            (f"blog:team-folder-structure:{name}", "conflict_candidate")
            for name in ("a-structure-that-scales",
                         "the-case-against-one-giant-folder",
                         "when-to-reorganize", "naming-conventions")})
        self.assertTrue(all(c["winner_id"] == "docs:teams:shared-team-folders"
                            for c in result["conflicts"]))
        by_id = {h["chunk_id"]: h for h in result["evidence"]}
        self.assertEqual(by_id["docs:teams:shared-team-folders"]
                         ["conflict_status"], "kept")
        for h in result["evidence"]:
            self.assertNotEqual(h["conflict_status"], "suppressed",
                                h["chunk_id"])

    def test_deterministic_repeated_runs(self):
        a = self.retriever.retrieve_final(Q01, reranker=self.reranker)
        b = self.retriever.retrieve_final(Q01, reranker=self.reranker)
        self.assertEqual([(h["chunk_id"], h["conflict_status"])
                          for h in a["evidence"]],
                         [(h["chunk_id"], h["conflict_status"])
                          for h in b["evidence"]])
        self.assertEqual(a["conflicts"], b["conflicts"])


if __name__ == "__main__":
    unittest.main()
