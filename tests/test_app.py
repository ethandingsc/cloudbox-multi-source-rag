"""Step 5.3 UI tests — the Streamlit app over the real pipeline.

streamlit.testing.v1.AppTest executes app.py headless, so these tests verify
the actual UI flow: source filter -> Ask -> answer -> sources -> RAG trace
expander, plus the error path. The app is a thin presentation layer, so the
pipeline result is read back from session_state and checked against what the
page renders.

Requires the ChromaDB collection, the local models and (like the smoke test)
a real LLM API key for the answer-producing runs.

Run from the project root in the cloudbox-rag env:
    python -m unittest discover -s tests -v
"""

import os
import unittest
from pathlib import Path
from unittest import mock

from streamlit.testing.v1 import AppTest

from src import config
from src.answer import OpenRouterError, kept_evidence

# AppTest.from_file resolves relative paths against the CALLING file's
# directory, so pin the app path explicitly.
APP_PATH = Path(__file__).resolve().parent.parent / "app.py"
SOURCE_LABELS = ["All Sources", "Documentation", "Forums", "Blogs"]


def _has_key() -> bool:
    return bool(os.environ.get(config.DEEPSEEK_API_KEY_ENV)
                or os.environ.get(config.LLM_API_KEY_ENV))


def _run_question(at: AppTest, question: str,
                  source_label: str = "All Sources") -> None:
    at.radio[0].set_value(source_label)
    at.text_input[0].set_value(question)
    at.button[0].click()
    at.run()


class TestAppUi(unittest.TestCase):
    def _check_sources(self, at: AppTest, result: dict) -> None:
        """Sources block must mirror the pipeline's real citations: [n]
        numbering matches kept_evidence() positions, every card's type label
        matches the citation, and suppressed chunks never reach a card."""
        kept_ids = [h["chunk_id"] for h in kept_evidence(result["evidence"])]
        rendered = "\n".join(m.value for m in at.markdown)
        for c in result["citations"]:
            self.assertEqual(kept_ids[c["n"] - 1], c["chunk_id"],
                             f"citation [{c['n']}] must point at kept "
                             f"position")
            self.assertIn(f"**[{c['n']}] {c['source_type'].title()}**",
                          rendered, f"card for citation [{c['n']}] missing")
        captions = "\n".join(c.value for c in at.caption)
        for h in result["evidence"]:
            if h["conflict_status"] == "suppressed":
                prefix = h["text"].replace("\n", " ")[:40]
                self.assertNotIn(prefix, captions,
                                 f"suppressed chunk {h['chunk_id']} leaked "
                                 f"into the Sources block")


    def test_page_structure_before_asking(self):
        at = AppTest.from_file(APP_PATH, default_timeout=60).run()
        self.assertEqual(at.exception, [])
        self.assertEqual(at.title[0].value, "CloudBox Support Assistant")
        self.assertEqual(list(at.radio[0].options), SOURCE_LABELS)
        self.assertEqual(at.radio[0].value, "All Sources")
        self.assertEqual(at.text_input[0].label, "Ask a CloudBox question")
        self.assertEqual(at.button[0].label, "Ask")
        self.assertEqual(len(at.expander), 0)  # trace only after an answer

    def test_empty_question_warns_without_running(self):
        at = AppTest.from_file(APP_PATH, default_timeout=60).run()
        at.button[0].click()
        at.run()
        self.assertEqual(at.exception, [])
        self.assertTrue(at.warning)

    def test_pipeline_error_shows_message_no_crash(self):
        # a failing LLM client (e.g. missing key) must render st.error, not
        # take the page down; no answer/sources/trace may appear
        with mock.patch("src.answer.LLMClient.__init__",
                        side_effect=OpenRouterError("boom: no key")):
            at = AppTest.from_file(APP_PATH, default_timeout=180).run()
            _run_question(at, "Any question?")
        self.assertEqual(at.exception, [])
        self.assertTrue(at.error)
        self.assertIn("boom: no key", at.error[0].value)
        self.assertNotIn("demo_result", at.session_state)
        self.assertEqual(len(at.expander), 0)

    @unittest.skipUnless(_has_key(), "no LLM API key available")
    def test_all_sources_question_end_to_end(self):
        at = AppTest.from_file(APP_PATH, default_timeout=300).run()
        _run_question(at, "How much free storage do I get with CloudBox?")
        self.assertEqual(at.exception, [])
        self.assertFalse(at.error)
        result = at.session_state["demo_result"]
        self.assertTrue(result["answer"])
        subheaders = [s.value for s in at.subheader]
        self.assertIn("Answer", subheaders)
        self.assertIn("Sources", subheaders)
        self.assertTrue(any("[1]" in m.value for m in at.markdown))
        self.assertEqual(len(at.expander), 1)
        self.assertEqual(at.expander[0].label, "View RAG Trace")
        self._check_sources(at, result)

    @unittest.skipUnless(_has_key(), "no LLM API key available")
    def test_documentation_filter(self):
        at = AppTest.from_file(APP_PATH, default_timeout=300).run()
        _run_question(at, "How much free storage do I get with CloudBox?",
                      "Documentation")
        self.assertEqual(at.exception, [])
        self.assertFalse(at.error)
        result = at.session_state["demo_result"]
        self.assertTrue(result["answer"])
        # PLAN §5.4: single-source modes skip the cross-source conflict rules
        self.assertEqual(result["conflicts"], [])
        cited = {c["source_type"] for c in result["citations"]}
        if cited:  # the model may or may not cite; when it does, docs only
            self.assertEqual(cited, {"documentation"})
        self._check_sources(at, result)

    @unittest.skipUnless(_has_key(), "no LLM API key available")
    def test_forums_filter(self):
        at = AppTest.from_file(APP_PATH, default_timeout=300).run()
        _run_question(at, "My sync client has been stuck on 'Syncing…' for "
                          "hours. What should I do?", "Forums")
        self.assertEqual(at.exception, [])
        self.assertFalse(at.error)
        result = at.session_state["demo_result"]
        self.assertTrue(result["answer"])
        self.assertEqual(result["conflicts"], [])
        cited = {c["source_type"] for c in result["citations"]}
        if cited:
            self.assertEqual(cited, {"forum"})
        self._check_sources(at, result)

    @unittest.skipUnless(_has_key(), "no LLM API key available")
    def test_blogs_filter(self):
        at = AppTest.from_file(APP_PATH, default_timeout=300).run()
        _run_question(at, "What are best practices for organizing team "
                          "folders at scale?", "Blogs")
        self.assertEqual(at.exception, [])
        self.assertFalse(at.error)
        result = at.session_state["demo_result"]
        self.assertTrue(result["answer"])
        self.assertEqual(result["conflicts"], [])
        cited = {c["source_type"] for c in result["citations"]}
        if cited:
            self.assertEqual(cited, {"blog"})
        self._check_sources(at, result)


if __name__ == "__main__":
    unittest.main()
