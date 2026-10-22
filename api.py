"""HTTP entry point for synchronous demos and Kafka-backed asynchronous jobs."""

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src import config, service
from src.answer import OpenRouterError


app = FastAPI(title="CloudBox Multi-Source RAG", version="1.0")
EXPECTED_INDEX_RECORDS = 590


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    sources: list[str] | None = None
    session_id: str | None = Field(default=None, max_length=100)


def validate_sources(sources: list[str] | None) -> None:
    if sources is not None and (not sources or
            any(source not in config.SOURCE_TYPES for source in sources)):
        raise HTTPException(status_code=422, detail="Invalid source filter")


def normalize_question(question: str) -> str:
    question = question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be blank")
    return question


@lru_cache(maxsize=1)
def rag_resources():
    from src.embed_store import EmbedStore
    from src.rerank import Reranker

    return EmbedStore(), Reranker()


def run_rag(question: str, sources: list[str] | None = None) -> dict:
    from src.pipeline import answer_question

    store, reranker = rag_resources()
    return answer_question(question, sources=sources, store=store,
                           reranker=reranker)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not (config.CHROMA_DIR / "chroma.sqlite3").exists():
        raise HTTPException(status_code=503, detail="ChromaDB index missing")
    try:
        store, _ = rag_resources()
        records = store.count()
    except Exception as exc:
        raise HTTPException(status_code=503,
                            detail="RAG resources failed to load") from exc
    if records != EXPECTED_INDEX_RECORDS:
        raise HTTPException(
            status_code=503,
            detail=(f"ChromaDB record count mismatch: expected "
                    f"{EXPECTED_INDEX_RECORDS}, found {records}"),
        )
    return {
        "status": "ready",
        "index_records": records,
        "embedding_model": config.EMBED_MODEL,
        "rerank_model": config.RERANK_MODEL,
    }


@app.post("/query")
def query(request: QueryRequest):
    validate_sources(request.sources)
    try:
        return run_rag(normalize_question(request.question), request.sources)
    except HTTPException:
        raise
    except OpenRouterError as exc:
        raise HTTPException(status_code=502,
                            detail=f"LLM provider unavailable: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=503,
                            detail="RAG pipeline unavailable") from exc


@app.post("/jobs", status_code=202)
def submit(request: QueryRequest):
    validate_sources(request.sources)
    try:
        return service.submit_job(normalize_question(request.question), request.sources,
                                  request.session_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Queue unavailable: {exc}") from exc


@app.get("/jobs/{job_id}")
def job(job_id: str):
    try:
        state = service.get_job(job_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Result store unavailable") from exc
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    return {"job_id": job_id, **state}


@app.get("/sessions/{session_id}")
def session(session_id: str):
    try:
        return {"session_id": session_id, "history": service.get_session(session_id)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Session store unavailable") from exc
