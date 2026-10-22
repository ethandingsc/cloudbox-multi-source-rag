"""Offline unit tests for the 120-case evaluation helpers."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import evaluate  # noqa: E402


def hit(chunk_id, derived_from=None, status="kept"):
    metadata = {"title": chunk_id}
    if derived_from:
        metadata["derived_from"] = derived_from
    return {"chunk_id": chunk_id, "conflict_status": status,
            "source_type": "documentation", "metadata": metadata,
            "text": chunk_id}


class FakeEncoder:
    def __init__(self, vectors):
        self.vectors = vectors

    def encode(self, texts, normalize_embeddings=True):
        return self.vectors


class TestDataset(unittest.TestCase):
    def test_real_dataset_passes(self):
        data = evaluate.load_queries()
        self.assertEqual(len(data["queries"]), 120)
        self.assertEqual(evaluate.validate_dataset(data), [])
        self.assertEqual(sum("alignment_audit" in q for q in data["queries"]), 25)

    def test_validation_catches_count_and_duplicates(self):
        data = evaluate.load_queries()
        bad = {"queries": data["queries"][:119]}
        self.assertTrue(any("expected 120" in p
                            for p in evaluate.validate_dataset(bad)))
        dup = {"queries": [dict(q, id="q001") for q in data["queries"]]}
        self.assertTrue(any("not unique" in p
                            for p in evaluate.validate_dataset(dup)))


class TestRetrievalMetrics(unittest.TestCase):
    def test_exact_and_derived_hits(self):
        hits = [hit("docs:x"), hit("docs:synthetic", "docs:b"), hit("docs:a")]
        found, rank = evaluate.hit_rank(["docs:a", "docs:b"], hits)
        self.assertTrue(found)
        self.assertEqual(rank, 2)
        self.assertAlmostEqual(evaluate.reciprocal_rank(rank), 0.5)
        self.assertEqual(evaluate.recall_at_k(["docs:a", "docs:b"], hits), 1.0)

    def test_miss(self):
        found, rank = evaluate.hit_rank(["docs:a"], [hit("docs:x")])
        self.assertFalse(found)
        self.assertIsNone(rank)
        self.assertEqual(evaluate.reciprocal_rank(rank), 0.0)

    def test_evidence_groups_treat_ids_as_alternatives(self):
        groups = [["forum:a", "docs:a"], ["docs:b"]]
        hits = [hit("docs:a"), hit("docs:b")]
        found, rank = evaluate.hit_rank_groups(groups, hits)
        self.assertTrue(found)
        self.assertEqual(rank, 1)
        self.assertEqual(evaluate.recall_groups(groups, hits), 1.0)


class TestAnswerScoring(unittest.TestCase):
    def test_similarity_and_numbers_required(self):
        encoder = FakeEncoder([[1.0, 0.0], [0.8, 0.6]])
        score = evaluate.score_answer("10 GB", "The plan has 10 GB", encoder)
        self.assertEqual(score["label"], "Correct")
        score = evaluate.score_answer("10 GB", "The plan has storage", encoder)
        self.assertEqual(score["label"], "Partially Correct")
        self.assertEqual(score["missing_numbers"], ["10"])


class TestCitationValidation(unittest.TestCase):
    def test_correctness_uses_expected_evidence_and_derived_from(self):
        evidence = [hit("docs:synthetic", "docs:a"), hit("docs:b")]
        result = {
            "evidence": evidence,
            "citations": [
                {"n": 1, "chunk_id": "docs:synthetic"},
                {"n": 2, "chunk_id": "docs:b"},
            ],
            "invalid_citations": [9],
        }
        check = evaluate.validate_citations(result, ["docs:a"])
        self.assertEqual(check["total"], 3)
        self.assertEqual(check["correct"], 1)
        self.assertEqual(check["incorrect"], 2)


class TestSummary(unittest.TestCase):
    def test_summary_math(self):
        records = [
            {"raw_hit_at_5": True, "raw_recall_at_5": 1.0,
             "raw_reciprocal_rank": 1.0,
             "final_hit_at_5": True, "final_recall_at_5": 1.0,
             "final_reciprocal_rank": 1.0,
             "answer": "a", "answer_score": {"label": "Correct"},
             "citation_check": {"total": 2, "correct": 2}},
            {"raw_hit_at_5": True, "raw_recall_at_5": 1.0,
             "raw_reciprocal_rank": 0.5,
             "final_hit_at_5": True, "final_recall_at_5": 0.5,
             "final_reciprocal_rank": 0.5,
             "answer": "b", "answer_score": {"label": "Partially Correct"},
             "citation_check": {"total": 2, "correct": 1}},
            {"raw_hit_at_5": False, "raw_recall_at_5": 0.0,
             "raw_reciprocal_rank": 0.0,
             "final_hit_at_5": False, "final_recall_at_5": 0.0,
             "final_reciprocal_rank": 0.0,
             "answer": None},
        ]
        summary = evaluate.summarize(records)
        self.assertEqual(summary["hit_at_5_hits"], 2)
        self.assertAlmostEqual(summary["recall_at_5"], 0.5)
        self.assertAlmostEqual(summary["mrr_at_5"], 0.5)
        self.assertIsNone(summary["answer_accuracy"])
        self.assertAlmostEqual(summary["citation_correctness"], 0.75)


if __name__ == "__main__":
    unittest.main()
