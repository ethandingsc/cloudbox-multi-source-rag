"""Offline contract tests for the new API and queue adapter."""

import unittest
from unittest import mock

from fastapi import HTTPException

import api
from src.answer import OpenRouterError
from src import service


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.lists = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def delete(self, key):
        self.values.pop(key, None)

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def ltrim(self, key, start, stop):
        self.lists[key] = self.lists[key][start:stop + 1 if stop != -1 else None]

    def expire(self, key, seconds):
        return True

    def lrange(self, key, start, stop):
        return self.lists.get(key, [])[start:stop + 1 if stop != -1 else None]


class FakeFuture:
    def __init__(self, error=None):
        self.error = error

    def get(self, timeout):
        if self.error:
            raise self.error
        return None


class FakeProducer:
    def __init__(self):
        self.messages = []
        self.error = None

    def send(self, topic, message):
        self.messages.append((topic, message))
        return FakeFuture(self.error)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.producer = FakeProducer()
        self.redis_patch = mock.patch.object(service, "redis_client",
                                             return_value=self.redis)
        self.producer_patch = mock.patch.object(service, "kafka_producer",
                                                return_value=self.producer)
        self.redis_patch.start()
        self.producer_patch.start()
        self.addCleanup(self.redis_patch.stop)
        self.addCleanup(self.producer_patch.stop)

    def test_job_lifecycle_and_cache(self):
        submitted = service.submit_job("How much storage?", None, "demo")
        self.assertEqual(submitted["status"], "queued")
        self.assertEqual(len(self.producer.messages), 1)
        payload = self.producer.messages[0][1]
        answer = {"answer": "10 GB [1]", "citations": [{"n": 1}]}
        compute = mock.Mock(return_value=answer)
        service.process_job(payload, compute)
        self.assertEqual(service.get_job(submitted["job_id"])["status"],
                         "completed")
        service.process_job(payload, compute)
        compute.assert_called_once()
        cached = service.submit_job("How much storage?", None, "demo")
        self.assertTrue(cached["cached"])
        self.assertEqual(len(self.producer.messages), 1)
        self.assertEqual(service.get_job(cached["job_id"])["result"], answer)
        self.assertEqual(len(service.get_session("demo")), 2)

    def test_cache_key_isolates_different_queries_and_source_filters(self):
        first = service.submit_job("Question A", ["documentation"])
        service.process_job(self.producer.messages[0][1],
                            mock.Mock(return_value={"answer": "A"}))

        second = service.submit_job("Question B", ["documentation"])
        third = service.submit_job("Question A", ["forum"])

        self.assertFalse(second["cached"])
        self.assertFalse(third["cached"])
        self.assertEqual(len(self.producer.messages), 3)

    def test_kafka_failure_removes_queued_job(self):
        self.producer.error = RuntimeError("Kafka unavailable")
        with self.assertRaisesRegex(RuntimeError, "Kafka unavailable"):
            service.submit_job("Question", None)
        self.assertFalse(any(key.startswith("cloudbox:job:")
                             for key in self.redis.values))

    def test_malformed_message_marks_known_job_failed(self):
        service.set_job("known-job", {"status": "queued"})
        with self.assertRaises(service.InvalidJobMessage):
            service.process_job({"job_id": "known-job"}, mock.Mock())
        state = service.get_job("known-job")
        self.assertEqual(state["status"], "failed")
        self.assertIn("question", state["error"])

    def test_failed_job_has_status(self):
        submitted = service.submit_job("Question", ["documentation"])
        payload = self.producer.messages[0][1]
        service.process_job(payload, mock.Mock(side_effect=RuntimeError("LLM down")))
        state = service.get_job(submitted["job_id"])
        self.assertEqual(state["status"], "failed")
        self.assertIn("LLM down", state["error"])


class ApiTests(unittest.TestCase):
    def test_sync_query_and_validation(self):
        with mock.patch.object(api, "run_rag", return_value={"answer": "ok"}):
            self.assertEqual(api.health(), {"status": "ok"})
            self.assertEqual(api.query(api.QueryRequest(question="Hi"))["answer"],
                             "ok")
            with self.assertRaises(HTTPException) as raised:
                api.query(api.QueryRequest(question="Hi", sources=["unknown"]))
            self.assertEqual(raised.exception.status_code, 422)

            with self.assertRaises(HTTPException) as raised:
                api.query(api.QueryRequest(question="   "))
            self.assertEqual(raised.exception.status_code, 422)

    def test_ready_checks_loaded_index(self):
        store = mock.Mock()
        store.count.return_value = 590
        with mock.patch("pathlib.Path.exists", return_value=True), \
             mock.patch.object(api, "rag_resources",
                               return_value=(store, mock.Mock())):
            result = api.ready()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["index_records"], 590)

        store.count.return_value = 589
        with mock.patch("pathlib.Path.exists", return_value=True), \
             mock.patch.object(api, "rag_resources",
                               return_value=(store, mock.Mock())):
            with self.assertRaises(HTTPException) as raised:
                api.ready()
        self.assertEqual(raised.exception.status_code, 503)

    def test_query_reports_provider_and_pipeline_failures(self):
        request = api.QueryRequest(question="How much storage?")
        with mock.patch.object(api, "run_rag",
                               side_effect=OpenRouterError("connection error")):
            with self.assertRaises(HTTPException) as raised:
                api.query(request)
        self.assertEqual(raised.exception.status_code, 502)

        with mock.patch.object(api, "run_rag",
                               side_effect=RuntimeError("internal detail")):
            with self.assertRaises(HTTPException) as raised:
                api.query(request)
        self.assertEqual(raised.exception.status_code, 503)
        self.assertNotIn("internal detail", raised.exception.detail)

    def test_async_api_contract(self):
        with mock.patch.object(api.service, "submit_job", return_value={
                "job_id": "123", "status": "queued", "cached": False}), \
             mock.patch.object(api.service, "get_job", return_value={
                "status": "completed", "result": {"answer": "ok"}}):
            self.assertEqual(api.submit(api.QueryRequest(question="Hi"))
                             ["status"], "queued")
            self.assertEqual(api.job("123")["result"]["answer"],
                             "ok")

    def test_async_missing_job_and_dependency_errors(self):
        with mock.patch.object(api.service, "get_job", return_value=None):
            with self.assertRaises(HTTPException) as raised:
                api.job("missing")
        self.assertEqual(raised.exception.status_code, 404)

        request = api.QueryRequest(question="Hi")
        with mock.patch.object(api.service, "submit_job",
                               side_effect=RuntimeError("Kafka down")):
            with self.assertRaises(HTTPException) as raised:
                api.submit(request)
        self.assertEqual(raised.exception.status_code, 503)

        with mock.patch.object(api.service, "get_session",
                               side_effect=RuntimeError("Redis down")):
            with self.assertRaises(HTTPException) as raised:
                api.session("demo")
        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
