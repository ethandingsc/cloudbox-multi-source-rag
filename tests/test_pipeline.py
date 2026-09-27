"""Minimal tests for Step 4.4: end-to-end pipeline orchestration.

retrieve_final() and generate_answer() are faked in most tests so the
orchestration layer stays fast and offline (no ChromaDB / models /
network); one test wires the REAL Step 3.3 retrieval to check the actual
integration. The stages themselves are covered by their own test files.

Run from the project root in the cloudbox-rag env:
    python -m unittest discover -s tests -v
"""

import unittest
from unittest import mock

from src import answer, pipeline, retrieve


def _hit(chunk_id, source_type="documentation", title="A title",
         conflict_status="kept", suppressed_reason=None, rerank_score=5.0):
    """Fake Step 3.3 evidence entry shaped like the real retrieve_final hits."""
    return {
        "chunk_id": chunk_id,
        "source_type": source_type,
        "text": f"Text of {chunk_id}.",
        "metadata": {"title": title, "date": "2024-05-12", "version": "2.1",
                     "topics": ["storage"]},
        "similarity": 0.6, "weighted_score": 0.6, "rerank_score": rerank_score,
        "conflict_status": conflict_status,
        "suppressed_reason": suppressed_reason,
    }


EVIDENCE = [
    _hit("docs:storage-limits:free-plan-storage", title="Storage Limits"),
    _hit("forum:thread-001", source_type="forum", title="Free storage?",
         conflict_status="suppressed",
         suppressed_reason="superseded_by_current_docs"),
    _hit("docs:billing:plans-and-pricing", title="Billing and Plans",
         rerank_score=4.2),
]
CONFLICTS = [{"rule": "superseded_by_current_docs",
              "chunk_id": "forum:thread-001",
              "winner_id": "docs:storage-limits:free-plan-storage",
              "note": "forum dated 2023-02-10, before the current docs "
                      "release 2024-05-12"}]
FINAL = {"evidence": EVIDENCE, "conflicts": CONFLICTS}

QUESTION = "How much free storage do I get with CloudBox?"


class TestAnswerQuestion(unittest.TestCase):
    def _fake_generate(self, calls):
        def fake(question, evidence, **kwargs):
            calls.append((question, evidence))
            return {
                "answer": "The free plan includes 10 GB [1].",
                "citations": [{"n": 1,
                               "chunk_id": "docs:storage-limits:free-plan-storage",
                               "source_type": "documentation",
                               "title": "Storage Limits"}],
                "invalid_citations": [7],
            }
        return fake

    def _patch_stages(self):
        calls = []
        retr = mock.patch("src.pipeline.retrieve.retrieve_final",
                          return_value=dict(FINAL))
        gen = mock.patch("src.pipeline.generate_answer",
                         self._fake_generate(calls))
        return retr, gen, calls

    def test_end_to_end_result_carries_everything(self):
        retr, gen, _ = self._patch_stages()
        with retr, gen:
            result = pipeline.answer_question(QUESTION)
        self.assertEqual(result["question"], QUESTION)
        self.assertEqual(result["answer"], "The free plan includes 10 GB [1].")
        self.assertEqual(result["citations"][0]["chunk_id"],
                         "docs:storage-limits:free-plan-storage")
        self.assertEqual(result["invalid_citations"], [7])
        self.assertEqual(result["evidence"], EVIDENCE)  # full Step 3.3 list
        self.assertEqual(result["conflicts"], CONFLICTS)

    def test_generate_answer_receives_the_final_evidence(self):
        retr, gen, calls = self._patch_stages()
        with retr, gen:
            pipeline.answer_question(QUESTION)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], QUESTION)          # question passed on
        self.assertEqual(calls[0][1], EVIDENCE)          # final evidence as-is
        # every stage reused as-is — nothing copied or rewritten here
        self.assertIs(calls[0][1][1], EVIDENCE[1])       # same objects
        self.assertIn("suppressed",
                      calls[0][1][1]["conflict_status"])  # status preserved

    def test_source_filter_and_sizes_forwarded(self):
        retr, gen, _ = self._patch_stages()
        with retr as m_retr, gen:
            pipeline.answer_question(QUESTION, sources="forum", top_k=3,
                                     pool_size=9, final_size=4)
        self.assertEqual(m_retr.call_args.args, (QUESTION,))
        self.assertEqual(m_retr.call_args.kwargs,
                         {"sources": "forum",
                          "top_k": 3, "pool_size": 9, "final_size": 4,
                          "store": None, "reranker": None})
        with retr as m_retr, gen:
            pipeline.answer_question(QUESTION,
                                     sources=["documentation", "blog"])
        self.assertEqual(m_retr.call_args.kwargs["sources"],
                         ["documentation", "blog"])
        with retr as m_retr, gen:
            pipeline.answer_question(QUESTION)  # default = all three sources
        self.assertIsNone(m_retr.call_args.kwargs["sources"])

    def test_insufficient_evidence_short_circuits_without_llm(self):
        # all final evidence suppressed -> the pipeline must return the
        # fixed grounded reply without ever constructing an LLM client
        final = {"evidence": [dict(h) for h in EVIDENCE
                              if h["chunk_id"] == "forum:thread-001"],
                 "conflicts": CONFLICTS}
        with mock.patch("src.pipeline.retrieve.retrieve_final",
                        return_value=final):
            result = pipeline.answer_question(QUESTION)  # real generate_answer
        self.assertEqual(result["answer"],
                         answer.INSUFFICIENT_EVIDENCE_ANSWER)
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["invalid_citations"], [])
        self.assertEqual(result["evidence"], final["evidence"])
        self.assertEqual(result["conflicts"], CONFLICTS)

    def test_retrieval_error_propagates(self):
        retr = mock.patch("src.pipeline.retrieve.retrieve_final",
                          side_effect=ValueError("unknown source_type"))
        with retr, mock.patch("src.pipeline.generate_answer") as gen:
            with self.assertRaises(ValueError) as ctx:
                pipeline.answer_question(QUESTION, sources="wiki")
        self.assertIn("unknown source_type", str(ctx.exception))
        gen.assert_not_called()  # nothing runs after a failed stage

    def test_answer_error_propagates(self):
        gen = mock.patch("src.pipeline.generate_answer",
                         side_effect=answer.OpenRouterError("api down"))
        with mock.patch("src.pipeline.retrieve.retrieve_final",
                        return_value=dict(FINAL)), gen:
            with self.assertRaises(answer.OpenRouterError) as ctx:
                pipeline.answer_question(QUESTION)
        self.assertIn("api down", str(ctx.exception))


class TestTraceText(unittest.TestCase):
    def _result(self):
        return {
            "question": QUESTION,
            "answer": "The free plan includes 10 GB [1]. See also [7].",
            "citations": [{"n": 1,
                           "chunk_id": "docs:storage-limits:free-plan-storage",
                           "source_type": "documentation",
                           "title": "Storage Limits"}],
            "invalid_citations": [7],
            "evidence": EVIDENCE,
            "conflicts": CONFLICTS,
        }

    def test_trace_walks_question_to_citations(self):
        trace = pipeline.trace_text(self._result())
        self.assertIn(f"question: {QUESTION}", trace)
        # kept chunks get the stable [n] numbering, in kept order
        self.assertIn("[1] docs:storage-limits:free-plan-storage", trace)
        self.assertIn("[2] docs:billing:plans-and-pricing", trace)
        # the suppressed chunk stays visible for audit but gets NO number
        self.assertIn("forum:thread-001", trace)
        self.assertIn("suppressed", trace)
        self.assertIn("superseded_by_current_docs", trace)
        self.assertNotIn("[2] forum:thread-001", trace)
        # conflicts, answer and the citation -> chunk mapping all appear
        self.assertIn("conflicts:", trace)
        self.assertIn("superseded_by_current_docs: forum:thread-001", trace)
        self.assertIn("winner docs:storage-limits:free-plan-storage", trace)
        self.assertIn("answer:", trace)
        self.assertIn("The free plan includes 10 GB [1]", trace)
        self.assertIn("[1] docs:storage-limits:free-plan-storage  "
                      "(documentation, \"Storage Limits\")", trace)
        self.assertIn("invalid citation markers (dropped): [7]", trace)

    def test_trace_with_no_citations(self):
        result = self._result()
        result["citations"] = []
        result["invalid_citations"] = []
        trace = pipeline.trace_text(result)
        self.assertIn("citations:", trace)
        self.assertIn("none", trace)


class TestRealRetrievalWiring(unittest.TestCase):
    """The one integration test: real Step 3.3 evidence into the pipeline
    (only the LLM call is faked). Needs the Step 2.2 ChromaDB collection
    and the Step 3.2 rerank model, like tests/test_conflict.py."""

    @classmethod
    def setUpClass(cls):
        from src import embed_store, rerank
        cls.retriever = retrieve.Retriever(embed_store.EmbedStore())
        cls.reranker = rerank.Reranker()

    def test_real_final_evidence_flows_into_generate_answer(self):
        calls = []
        with mock.patch("src.pipeline.generate_answer") as gen:
            gen.side_effect = lambda q, ev, **kw: (
                calls.append((q, ev)) or {
                    "answer": "canned", "citations": [],
                    "invalid_citations": []})
            pipeline.answer_question(
                "How much free storage do I get with CloudBox?",
                store=self.retriever.store, reranker=self.reranker)
        self.assertEqual(len(calls), 1)
        evidence = calls[0][1]
        by_id = {h["chunk_id"]: h for h in evidence}
        # the designed contradiction case: old forum claim suppressed,
        # current docs kept — exactly what Step 3.3 produces
        self.assertEqual(by_id["forum:thread-001"]["conflict_status"],
                         "suppressed")
        self.assertEqual(by_id["docs:storage-limits:free-plan-storage"]
                         ["conflict_status"], "kept")
        self.assertTrue(all("rerank_score" in h for h in evidence))


if __name__ == "__main__":
    unittest.main()
