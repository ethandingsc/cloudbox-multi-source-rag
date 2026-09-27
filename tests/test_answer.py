"""Minimal tests for Step 4.1 (thin OpenRouter client, mocked/offline),
Step 4.2 (grounded prompt builder, pure function) and Step 4.3 (answer
generation + verified citations, fake client).

The real-network smoke test is `test_smoke_say_hello` — it runs only when
DEEPSEEK_API_KEY or OPENROUTER_API_KEY is set in the environment (skipped
otherwise) and calls whichever provider LLMClient auto-detects.

Run from the project root in the cloudbox-rag env:
    python -m unittest discover -s tests -v
"""

import os
import unittest
from unittest import mock

from src import answer, config


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class TestLLMClient(unittest.TestCase):
    def setUp(self):
        # a fake OpenAI class so no network is ever touched
        self.patcher = mock.patch("src.answer.OpenAI")
        self.fake_openai_cls = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def _make_client(self, env=None, provider=None):
        env = env or {}
        with mock.patch.dict(os.environ, env, clear=False):
            return answer.LLMClient(provider=provider)

    def test_missing_api_key_raises_clear_error(self):
        # no key for either provider — the error must name both
        env = {config.LLM_API_KEY_ENV: "", config.DEEPSEEK_API_KEY_ENV: ""}
        with mock.patch.dict(os.environ, env, clear=False):
            with self.assertRaises(answer.OpenRouterError) as ctx:
                answer.LLMClient()
        self.assertIn(config.LLM_API_KEY_ENV, str(ctx.exception))
        self.assertIn(config.DEEPSEEK_API_KEY_ENV, str(ctx.exception))

    def test_model_resolution_default_then_env_then_param(self):
        provider = config.LLM_PROVIDER_OPENROUTER
        env = {config.LLM_API_KEY_ENV: "test-key", config.LLM_MODEL_ENV: ""}
        client = self._make_client(env, provider)
        self.assertEqual(client.model, config.LLM_MODEL_DEFAULT)

        env = {config.LLM_API_KEY_ENV: "test-key",
               config.LLM_MODEL_ENV: "some/other-model:free"}
        client = self._make_client(env, provider)
        self.assertEqual(client.model, "some/other-model:free")

        env = {config.LLM_API_KEY_ENV: "test-key",
               config.LLM_MODEL_ENV: "some/other-model:free"}
        client = self._make_client(env, provider)
        client2 = answer.LLMClient(model="explicit/model", api_key="test-key",
                                   provider=provider)
        self.assertEqual(client2.model, "explicit/model")

    def test_complete_calls_openrouter_and_returns_text(self):
        fake_client = self.fake_openai_cls.return_value
        fake_client.chat.completions.create.return_value = _FakeResponse(
            "Hello! Nice to meet you.")
        client = answer.LLMClient(
            api_key="test-key", provider=config.LLM_PROVIDER_OPENROUTER)

        text = client.complete("Say hello in one sentence.")

        self.assertEqual(text, "Hello! Nice to meet you.")
        self.fake_openai_cls.assert_called_once_with(
            base_url=config.OPENROUTER_BASE_URL, api_key="test-key")
        kwargs = fake_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], config.LLM_MODEL_DEFAULT)
        self.assertEqual(kwargs["messages"],
                         [{"role": "user", "content": "Say hello in one sentence."}])
        self.assertEqual(kwargs["max_tokens"], config.LLM_MAX_TOKENS)
        self.assertEqual(kwargs["temperature"], config.LLM_TEMPERATURE)
        self.assertNotIn("extra_body", kwargs)  # OpenRouter behavior unchanged

    def test_api_failure_wrapped_in_clear_error(self):
        fake_client = self.fake_openai_cls.return_value
        fake_client.chat.completions.create.side_effect = Exception(
            "401 Unauthorized")
        client = answer.LLMClient(
            api_key="test-key", provider=config.LLM_PROVIDER_OPENROUTER)

        with self.assertRaises(answer.OpenRouterError) as ctx:
            client.complete("hello")
        msg = str(ctx.exception)
        self.assertIn("call failed", msg)
        self.assertIn(client.provider, msg)
        self.assertIn(client.model, msg)
        self.assertIn("401 Unauthorized", msg)

    def test_empty_content_returns_empty_string(self):
        fake_client = self.fake_openai_cls.return_value
        fake_client.chat.completions.create.return_value = _FakeResponse(None)
        client = answer.LLMClient(
            api_key="test-key", provider=config.LLM_PROVIDER_OPENROUTER)
        self.assertEqual(client.complete("anything"), "")

    def test_unexpected_response_shape_wrapped_in_clear_error(self):
        # e.g. choices=None on an upstream hiccup — must be an
        # OpenRouterError, not a bare TypeError (seen once live, 2026-09-27)
        fake_client = self.fake_openai_cls.return_value
        fake_client.chat.completions.create.return_value = _FakeResponse(
            "unused")
        fake_client.chat.completions.create.return_value.choices = None
        client = answer.LLMClient(
            api_key="test-key", provider=config.LLM_PROVIDER_OPENROUTER)
        with self.assertRaises(answer.OpenRouterError):
            client.complete("hello")

    # --- DeepSeek provider (default since 2026-09-27) ------------------------

    def test_deepseek_auto_detected_and_wins_when_both_keys_present(self):
        env = {config.DEEPSEEK_API_KEY_ENV: "ds-key",
               config.LLM_API_KEY_ENV: "or-key"}
        client = self._make_client(env)
        self.assertEqual(client.provider, config.LLM_PROVIDER_DEEPSEEK)
        self.assertEqual(client.model, config.DEEPSEEK_MODEL_DEFAULT)
        self.fake_openai_cls.assert_called_once_with(
            base_url=config.DEEPSEEK_BASE_URL, api_key="ds-key")

    def test_openrouter_used_when_no_deepseek_key(self):
        env = {config.DEEPSEEK_API_KEY_ENV: "",
               config.LLM_API_KEY_ENV: "or-key"}
        client = self._make_client(env)
        self.assertEqual(client.provider, config.LLM_PROVIDER_OPENROUTER)
        self.assertEqual(client.model, config.LLM_MODEL_DEFAULT)

    def test_deepseek_model_env_override(self):
        env = {config.DEEPSEEK_API_KEY_ENV: "ds-key",
               config.DEEPSEEK_MODEL_ENV: "deepseek-flash"}
        client = self._make_client(env)
        self.assertEqual(client.model, "deepseek-flash")

    def test_explicit_provider_overrides_auto_detection(self):
        # only the OpenRouter key is set, but the caller forces DeepSeek
        # and supplies an explicit key for it
        env = {config.DEEPSEEK_API_KEY_ENV: "",
               config.LLM_API_KEY_ENV: "or-key"}
        with mock.patch.dict(os.environ, env, clear=False):
            client = answer.LLMClient(
                api_key="explicit-key",
                provider=config.LLM_PROVIDER_DEEPSEEK)
        self.assertEqual(client.provider, config.LLM_PROVIDER_DEEPSEEK)
        self.fake_openai_cls.assert_called_once_with(
            base_url=config.DEEPSEEK_BASE_URL, api_key="explicit-key")

    def test_deepseek_complete_hits_deepseek_api(self):
        fake_client = self.fake_openai_cls.return_value
        fake_client.chat.completions.create.return_value = _FakeResponse(
            "Hello! Nice to meet you.")
        client = self._make_client({config.DEEPSEEK_API_KEY_ENV: "ds-key"})

        text = client.complete("Say hello in one sentence.")

        self.assertEqual(text, "Hello! Nice to meet you.")
        self.fake_openai_cls.assert_called_once_with(
            base_url=config.DEEPSEEK_BASE_URL, api_key="ds-key")
        kwargs = fake_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], config.DEEPSEEK_MODEL_DEFAULT)
        # Step 5.2.4: DeepSeek thinking is disabled — its hidden reasoning
        # tokens would otherwise eat the max_tokens budget (probed live:
        # 512/512 reasoning tokens, empty content)
        self.assertEqual(kwargs["extra_body"],
                         {"thinking": {"type": "disabled"}})

    def test_deepseek_failure_message_names_provider(self):
        fake_client = self.fake_openai_cls.return_value
        fake_client.chat.completions.create.side_effect = Exception("boom")
        client = self._make_client({config.DEEPSEEK_API_KEY_ENV: "ds-key"})

        with self.assertRaises(answer.OpenRouterError) as ctx:
            client.complete("hello")
        self.assertIn("deepseek call failed", str(ctx.exception))

    @unittest.skipUnless(
        os.environ.get(config.DEEPSEEK_API_KEY_ENV)
        or os.environ.get(config.LLM_API_KEY_ENV),
        "neither DEEPSEEK_API_KEY nor OPENROUTER_API_KEY set — real smoke "
        "skipped")
    def test_smoke_say_hello(self):
        # this is the ONE test meant to hit the network — undo the class-wide
        # OpenAI mock first, otherwise the reply is just a MagicMock
        self.patcher.stop()
        client = answer.LLMClient()  # auto-detect: DeepSeek wins when key set
        text = client.complete("Say hello in one sentence.")
        self.assertTrue(text.strip())
        print(f"\n[smoke] {client.provider} ({client.model}) reply: {text!r}")


def _hit(chunk_id, source_type="documentation", text="Evidence text.",
         title="A title", date="2024-05-12", version="2.1",
         conflict_status="kept", authority=None):
    """Fake Step 3.3 evidence entry shaped like the real retrieve_final hits."""
    return {
        "chunk_id": chunk_id,
        "source_type": source_type,
        "text": text,
        "metadata": {"title": title, "date": date, "version": version,
                     "topics": ["storage"]},
        "conflict_status": conflict_status,
        "authority": authority,
    }


class TestBuildGroundedPrompt(unittest.TestCase):
    """Step 4.2: the prompt builder is a pure function — no models, no DB."""

    QUESTION = "How much free storage do I get with CloudBox?"

    def _evidence(self):
        # one kept doc, one suppressed forum, one flagged blog — the three
        # statuses retrieve_final() can produce
        return [
            _hit("docs:storage-limits:free-plan-storage",
                 text="The free plan includes 10 GB of storage.",
                 title="Storage limits"),
            _hit("forum:thread-001", source_type="forum",
                 text="The free plan gives you 15 GB.",
                 title="Free storage size?", date="2023-02-10", version=None,
                 conflict_status="suppressed"),
            _hit("blog:free-storage-explained:what-the-free-plan-includes",
                 source_type="blog",
                 text="The free plan includes 5 GB.",
                 title="Free storage explained", date="2024-08-20",
                 version="2.1", conflict_status="conflict_candidate",
                 authority="community"),
        ]

    def test_question_enters_prompt(self):
        prompt = answer.build_grounded_prompt(self.QUESTION, self._evidence())
        self.assertIn(f"Question: {self.QUESTION}", prompt)
        self.assertTrue(prompt.rstrip().endswith("Answer:"))

    def test_kept_evidence_enters_prompt_with_text(self):
        evidence = self._evidence()
        prompt = answer.build_grounded_prompt(self.QUESTION, evidence)
        for h in answer.kept_evidence(evidence):
            self.assertIn(h["text"], prompt)
            self.assertIn(f"chunk: {h['chunk_id']}", prompt)

    def test_suppressed_evidence_never_in_context(self):
        evidence = self._evidence()
        prompt = answer.build_grounded_prompt(self.QUESTION, evidence)
        kept = answer.kept_evidence(evidence)
        self.assertEqual([h["chunk_id"] for h in kept],
                         ["docs:storage-limits:free-plan-storage",
                          "blog:free-storage-explained:what-the-free-plan-includes"])
        for h in evidence:
            if h["conflict_status"] == "suppressed":
                self.assertNotIn(h["chunk_id"], prompt)
                self.assertNotIn(h["text"], prompt)

    def test_numbering_stable_and_in_rerank_order(self):
        evidence = self._evidence()
        p1 = answer.build_grounded_prompt(self.QUESTION, evidence)
        p2 = answer.build_grounded_prompt(self.QUESTION, evidence)
        self.assertEqual(p1, p2)  # same evidence -> same numbering, always
        kept = answer.kept_evidence(evidence)
        positions = [p1.index(f"[{i}] source: {h['source_type']}")
                     for i, h in enumerate(kept, 1)]
        self.assertEqual(positions, sorted(positions))  # [1] before [2]
        for i, h in enumerate(kept, 1):
            self.assertIn(f"[{i}] source: {h['source_type']}", p1)

    def test_source_metadata_traceable(self):
        prompt = answer.build_grounded_prompt(self.QUESTION, self._evidence())
        self.assertIn("[1] source: documentation", prompt)
        self.assertIn("title: Storage limits", prompt)
        self.assertIn("chunk: docs:storage-limits:free-plan-storage", prompt)
        self.assertIn("version: 2.1", prompt)
        self.assertIn("date: 2024-05-12", prompt)
        # the Step 3.3 authority flag on community chunks is passed through
        self.assertIn("authority: community", prompt)

    def test_grounding_rules_present(self):
        prompt = answer.build_grounded_prompt(self.QUESTION, self._evidence())
        for phrase in ("using ONLY the evidence below",
                       "Do not use outside knowledge",
                       "information is insufficient",
                       "Never guess",
                       "Cite each fact",
                       "official documentation is authoritative",
                       "Do not re-judge authority",
                       "concise"):
            self.assertIn(phrase, prompt)

    def test_empty_evidence_explicitly_forbids_guessing(self):
        prompt = answer.build_grounded_prompt(self.QUESTION, [])
        self.assertIn("do not guess", prompt)
        self.assertIn("insufficient", prompt)
        self.assertNotIn("chunk:", prompt)

    def test_all_suppressed_evidence_treated_as_empty(self):
        evidence = [_hit("forum:thread-001", source_type="forum",
                         text="The free plan gives you 15 GB.",
                         title="Free storage size?", date="2023-02-10",
                         version=None, conflict_status="suppressed")]
        prompt = answer.build_grounded_prompt(self.QUESTION, evidence)
        self.assertNotIn("thread-001", prompt)
        self.assertNotIn("15 GB", prompt)
        self.assertIn("do not guess", prompt)


class _FakeLLM:
    """Records the prompt it received and returns a canned reply (offline)."""

    def __init__(self, reply):
        self.reply = reply
        self.prompt = None

    def complete(self, prompt, **kwargs):
        self.prompt = prompt
        return self.reply


class TestGenerateAnswer(unittest.TestCase):
    """Step 4.3: prompt -> LLM -> answer with citations (fake client)."""

    QUESTION = "How much free storage do I get with CloudBox?"

    def _evidence(self):
        # raw list order: docs (kept), forum (suppressed), blog (flagged)
        # -> kept_evidence numbering: [1] = docs, [2] = blog
        return [
            _hit("docs:storage-limits:free-plan-storage",
                 text="The free plan includes 10 GB of storage.",
                 title="Storage limits"),
            _hit("forum:thread-001", source_type="forum",
                 text="The free plan gives you 15 GB.",
                 title="Free storage size?", date="2023-02-10", version=None,
                 conflict_status="suppressed"),
            _hit("blog:free-storage-explained:what-the-free-plan-includes",
                 source_type="blog",
                 text="The free plan includes 5 GB.",
                 title="Free storage explained", date="2024-08-20",
                 version="2.1", conflict_status="conflict_candidate",
                 authority="community"),
        ]

    def test_normal_answer_with_citations(self):
        reply = ("The free plan includes 10 GB [1]. For more space, "
                 "upgrade to Plus with 2 TB [2].")
        client = _FakeLLM(reply)
        result = answer.generate_answer(self.QUESTION, self._evidence(),
                                        client=client)
        self.assertEqual(result["answer"], reply)
        self.assertEqual(result["invalid_citations"], [])
        # the LLM received exactly the Step 4.2 grounded prompt
        self.assertEqual(client.prompt,
                         answer.build_grounded_prompt(self.QUESTION,
                                                      self._evidence()))
        self.assertEqual([c["n"] for c in result["citations"]], [1, 2])

    def test_citations_map_only_to_kept_evidence(self):
        client = _FakeLLM("10 GB [1]. The old forum said 15 GB [2].")
        result = answer.generate_answer(self.QUESTION, self._evidence(),
                                        client=client)
        # [2] is the SECOND kept entry (the blog) — the suppressed forum
        # between them in the raw list is not part of the numbering
        self.assertEqual(
            [(c["n"], c["chunk_id"], c["source_type"], c["title"])
             for c in result["citations"]],
            [(1, "docs:storage-limits:free-plan-storage", "documentation",
              "Storage limits"),
             (2, "blog:free-storage-explained:what-the-free-plan-includes",
              "blog", "Free storage explained")])

    def test_suppressed_evidence_cannot_become_citation(self):
        client = _FakeLLM("The free plan includes 10 GB [1]. "
                          "Some users mention 15 GB [2].")
        result = answer.generate_answer(self.QUESTION, self._evidence(),
                                        client=client)
        ids = [c["chunk_id"] for c in result["citations"]]
        self.assertNotIn("forum:thread-001", ids)
        self.assertNotIn("15 GB", client.prompt)  # not even in the prompt

    def test_invalid_citation_markers_dropped_and_reported(self):
        reply = "10 GB [1], see also [7] and [0] and [7]."
        result = answer.generate_answer(self.QUESTION, self._evidence(),
                                        client=_FakeLLM(reply))
        self.assertEqual([c["n"] for c in result["citations"]], [1])
        self.assertEqual(result["invalid_citations"], [7, 0])  # deduped
        self.assertEqual(result["answer"], reply)  # text unchanged

    def test_duplicate_markers_deduplicated_in_appearance_order(self):
        client = _FakeLLM("Upgrade: 2 TB [2]. Free: 10 GB [1]. Again [2].")
        result = answer.generate_answer(self.QUESTION, self._evidence(),
                                        client=client)
        self.assertEqual([c["n"] for c in result["citations"]], [2, 1])

    def test_empty_evidence_never_calls_llm(self):
        client = _FakeLLM("should not be used")
        result = answer.generate_answer(self.QUESTION, [], client=client)
        self.assertIsNone(client.prompt)
        self.assertEqual(result["answer"],
                         answer.INSUFFICIENT_EVIDENCE_ANSWER)
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["invalid_citations"], [])

    def test_all_suppressed_evidence_is_empty_evidence(self):
        evidence = [_hit("forum:thread-001", source_type="forum",
                         text="The free plan gives you 15 GB.",
                         title="Free storage size?", date="2023-02-10",
                         version=None, conflict_status="suppressed")]
        client = _FakeLLM("should not be used")
        result = answer.generate_answer(self.QUESTION, evidence, client=client)
        self.assertIsNone(client.prompt)
        self.assertIn("insufficient", result["answer"])

    def test_llm_failure_propagates(self):
        class _Broken:
            def complete(self, prompt, **kwargs):
                raise answer.OpenRouterError("OpenRouter call failed: boom")
        with self.assertRaises(answer.OpenRouterError) as ctx:
            answer.generate_answer(self.QUESTION, self._evidence(),
                                   client=_Broken())
        self.assertIn("boom", str(ctx.exception))

    def test_missing_api_key_raises_without_client(self):
        # no key for either provider (the .env may contain real keys)
        env = {config.LLM_API_KEY_ENV: "", config.DEEPSEEK_API_KEY_ENV: ""}
        with mock.patch.dict(os.environ, env, clear=False):
            with self.assertRaises(answer.OpenRouterError):
                answer.generate_answer(self.QUESTION, self._evidence())


if __name__ == "__main__":
    unittest.main()
