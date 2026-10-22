"""Small Redis/Kafka adapter for the CloudBox demo API and worker."""

import hashlib
import json
import os
import uuid
from functools import lru_cache

from . import config


JOB_TTL = int(os.getenv("JOB_TTL_SECONDS", "3600"))
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
TOPIC = os.getenv("KAFKA_TOPIC", "cloudbox-queries")


class InvalidJobMessage(ValueError):
    """A Kafka record cannot be associated with a valid RAG job."""


@lru_cache(maxsize=1)
def redis_client():
    import redis

    return redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
        socket_connect_timeout=3,
    )


@lru_cache(maxsize=1)
def kafka_producer():
    from kafka import KafkaProducer

    return KafkaProducer(
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        retries=3,
    )


def cache_key(question: str, sources: list[str] | None) -> str:
    payload = json.dumps(
        {"question": question.strip(), "sources": sorted(sources or []),
         "version": os.getenv("KNOWLEDGE_VERSION", "v1")},
        sort_keys=True,
    )
    return "cloudbox:cache:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def job_key(job_id: str) -> str:
    return f"cloudbox:job:{job_id}"


def get_job(job_id: str) -> dict | None:
    raw = redis_client().get(job_key(job_id))
    return json.loads(raw) if raw else None


def set_job(job_id: str, state: dict) -> None:
    redis_client().set(job_key(job_id), json.dumps(state), ex=JOB_TTL)


def append_session(session_id: str | None, question: str, result: dict) -> None:
    if not session_id:
        return
    key = f"cloudbox:session:{session_id}"
    client = redis_client()
    client.rpush(key, json.dumps({"question": question, "answer": result["answer"]}))
    client.ltrim(key, -20, -1)
    client.expire(key, SESSION_TTL)


def get_session(session_id: str) -> list[dict]:
    return [json.loads(value) for value in
            redis_client().lrange(f"cloudbox:session:{session_id}", 0, -1)]


def submit_job(question: str, sources: list[str] | None,
               session_id: str | None = None) -> dict:
    client = redis_client()
    job_id = str(uuid.uuid4())
    cached = client.get(cache_key(question, sources))
    if cached:
        result = json.loads(cached)
        set_job(job_id, {"status": "completed", "result": result, "cached": True})
        append_session(session_id, question, result)
        return {"job_id": job_id, "status": "completed", "cached": True}

    set_job(job_id, {"status": "queued"})
    message = {"job_id": job_id, "question": question,
               "sources": sources, "session_id": session_id}
    try:
        kafka_producer().send(TOPIC, message).get(timeout=10)
    except Exception:
        client.delete(job_key(job_id))
        raise
    return {"job_id": job_id, "status": "queued", "cached": False}


def validate_job_message(message: dict) -> None:
    if not isinstance(message, dict):
        raise InvalidJobMessage("job message must be a JSON object")
    if not isinstance(message.get("job_id"), str) or not message["job_id"]:
        raise InvalidJobMessage("job message has no valid job_id")
    if not isinstance(message.get("question"), str) or not message["question"].strip():
        raise InvalidJobMessage("job message has no valid question")
    sources = message.get("sources")
    if sources is not None and (not isinstance(sources, list) or not sources or
                                any(source not in config.SOURCE_TYPES
                                    for source in sources)):
        raise InvalidJobMessage("job message has invalid sources")
    session_id = message.get("session_id")
    if session_id is not None and not isinstance(session_id, str):
        raise InvalidJobMessage("job message has invalid session_id")


def process_job(message: dict, answer_fn) -> None:
    """Process one delivery; duplicate completed deliveries have no side effects."""
    try:
        validate_job_message(message)
    except InvalidJobMessage as exc:
        job_id = message.get("job_id") if isinstance(message, dict) else None
        if isinstance(job_id, str) and job_id:
            set_job(job_id, {"status": "failed", "error": str(exc)})
        raise
    client = redis_client()
    job_id = message["job_id"]
    current = get_job(job_id)
    if current and current["status"] == "completed":
        return
    lock = f"cloudbox:lock:{job_id}"
    if not client.set(lock, "1", nx=True, ex=600):
        raise RuntimeError("job is already being processed; retry delivery")
    try:
        set_job(job_id, {"status": "processing"})
        result = answer_fn(message["question"], sources=message.get("sources"))
        client.set(cache_key(message["question"], message.get("sources")),
                   json.dumps(result), ex=CACHE_TTL)
        append_session(message.get("session_id"), message["question"], result)
        set_job(job_id, {"status": "completed", "result": result, "cached": False})
    except Exception as exc:
        set_job(job_id, {"status": "failed", "error": str(exc)[:500]})
    finally:
        client.delete(lock)
