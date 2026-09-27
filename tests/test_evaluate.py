"""Minimal tests for Step 5.1: the evaluation script's pure helpers.

Only the metric/validation functions are tested here (offline, no
ChromaDB / models / network); the full evaluation run is done with
`python scripts/evaluate.py` and its numbers are read from its output.

Run from the project root in the cloudbox-rag env:
    python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import evaluate  # noqa: E402  (scripts/ is not a package — import directly)


def _evidence_entry(chunk_id, status="kept"):
    return {"chunk_id": chunk_id, "conflict_status": status,
            "source_type": "documentation",
            "metadata": {"title": chunk_id}, "text": chunk_id}


class TestDataset(unittest.TestCase):
    def test_real_dataset_passes_all_checks(self):
        data = evaluate.load_queries()
        self.assertEqual(len(data["queries"]), 12)
        self.assertEqual(evaluate.validate_dataset(data), [])
        # the 4 designed contradiction cases are all present
        cases = [q["conflict_case"] for q in data["queries"]
                 if q["conflict_case"]]
        self.assertEqual(sorted(cases), ["2fa", "linux", "storage", "upload-size"])

    def test_validation_catches_bad_datasets(self):
        data = evaluate.load_queries()
        bad = {"queries": data["queries"][:11]}  # missing one
        problems = evaluate.validate_dataset(bad)
        self.assertTrue(any("expected 12" in p for p in problems))
        dup = {"queries": [dict(q, id="q01") for q in data["queries"][:12]]}
        problems = evaluate.validate_dataset(dup)
        self.assertTrue(any("not unique" in p for p in problems))


class TestRetrievalMetrics(unittest.TestCase):
    def test_hit_rank_and_reciprocal_rank(self):
        # expected ids need not be consecutive; first match wins
        hit, rank = evaluate.hit_rank(["docs:a", "docs:b"],
                                      ["docs:x", "docs:b", "docs:a"])
        self.assertTrue(hit)
        self.assertEqual(rank, 2)
        self.assertAlmostEqual(evaluate.reciprocal_rank(hit, rank), 0.5)

        hit, rank = evaluate.hit_rank(["docs:a"], ["docs:a", "docs:b"])
        self.assertTrue(hit)
        self.assertEqual(rank, 1)
        self.assertAlmostEqual(evaluate.reciprocal_rank(hit, rank), 1.0)

        hit, rank = evaluate.hit_rank(["docs:a"], ["docs:x", "docs:y"])
        self.assertFalse(hit)
        self.assertIsNone(rank)
        self.assertEqual(evaluate.reciprocal_rank(hit, rank), 0.0)


class TestDraftCorrectness(unittest.TestCase):
    def test_all_digit_tokens_present_is_correct(self):
        self.assertEqual(evaluate.draft_correctness(
            "The free plan includes 10 GB of storage.",
            "You get 10 GB on the free plan."), "Correct")

    def test_some_digit_tokens_is_partial(self):
        self.assertEqual(evaluate.draft_correctness(
            "20 GB through desktop clients; 2 GB through the web app.",
            "You can upload up to 20 GB."), "Partially Correct")

    def test_no_digit_tokens_is_incorrect(self):
        self.assertEqual(evaluate.draft_correctness(
            "The free plan includes 10 GB of storage.",
            "CloudBox has several paid plans."), "Incorrect")

    def test_no_digit_tokens_in_expected_facts_needs_manual_review(self):
        self.assertIsNone(evaluate.draft_correctness(
            "Create a share link with View/Edit/Comment permission.",
            "Anything at all."))


class TestCitationValidation(unittest.TestCase):
    def _result(self, kept, citations, invalid):
        return {
            "evidence": [_evidence_entry(c) for c in kept],
            "citations": [{"n": n, "chunk_id": cid,
                           "source_type": "documentation", "title": cid}
                          for n, cid in citations],
            "invalid_citations": invalid,
        }

    def test_all_citations_map_to_kept_evidence(self):
        check = evaluate.validate_citations(
            self._result(["docs:a", "docs:b"], [(1, "docs:a"), (2, "docs:b")],
                         []))
        self.assertEqual(check, {"total": 2, "valid": 2, "invalid": 0,
                                 "problems": []})

    def test_citation_to_suppressed_or_missing_chunk_is_a_problem(self):
        result = self._result(
            ["docs:a", "docs:b"],  # kept
            [(1, "docs:a"), (2, "forum:old")],  # forum:old not kept
            [7])
        check = evaluate.validate_citations(result)
        self.assertEqual(check["valid"], 1)   # only [1] is a real source
        self.assertEqual(check["invalid"], 1)  # the [7] marker
        self.assertEqual(check["total"], 2)
        self.assertTrue(any("not in kept evidence" in p
                            for p in check["problems"]))

    def test_numbering_mismatch_is_a_problem(self):
        check = evaluate.validate_citations(
            self._result(["docs:a", "docs:b"], [(2, "docs:a")], []))
        self.assertTrue(any("numbering mismatch" in p
                            for p in check["problems"]))


class TestSummary(unittest.TestCase):
    def test_summary_math_on_synthetic_records(self):
        def rec(hit, rr, answer, correctness, valid, invalid):
            r = {"hit_at_5": hit, "reciprocal_rank": rr,
                 "evidence_status": [_evidence_entry("docs:a")]}
            if answer:
                r["answer"] = answer
                r["correctness"] = correctness
                r["citation_check"] = {"total": valid + invalid,
                                       "valid": valid, "invalid": invalid,
                                       "problems": []}
            else:
                r["answer"] = None
            return r

        records = [
            rec(True, 1.0, "a", "Correct", 2, 0),
            rec(True, 0.5, "b", "Partially Correct", 1, 1),
            rec(False, 0.0, None, None, 0, 0),
        ]
        s = evaluate.summarize(records)
        self.assertEqual(s["queries"], 3)
        self.assertEqual(s["hit_at_5_hits"], 2)
        self.assertAlmostEqual(s["mrr_at_5"], (1.0 + 0.5 + 0.0) / 3)
        self.assertEqual(s["answered"], 2)
        self.assertEqual(s["correct"], 1)
        self.assertEqual(s["partial"], 1)
        self.assertAlmostEqual(s["answer_accuracy_rate"], 1 / 3)
        self.assertEqual(s["citations_total"], 4)
        self.assertEqual(s["citations_invalid"], 1)
        self.assertAlmostEqual(s["citation_validity_rate"], 3 / 4)


if __name__ == "__main__":
    unittest.main()
