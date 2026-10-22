# CloudBox Multi-Source RAG

CloudBox is a portfolio-scale retrieval-augmented generation system for a fictional cloud-storage support product. It answers questions from three source types—official documentation, customer forums, and technical blogs—while handling differences in source authority, product version, and publication date.

The project demonstrates practical SWE/MLE work: reproducible retrieval evaluation, grounded answer generation, a FastAPI service, Docker, Kafka-backed asynchronous jobs, Redis caching, and offline CI.

## Architecture

```text
Documentation / Forums / Blogs
              |
       source-aware chunking
              |
 Chroma dense retrieval (per source)
              |
 source weighting -> CrossEncoder reranking
              |
 version-aware conflict resolution
              |
 grounded LLM answer -> verified chunk citations

Client -> FastAPI -> Kafka -> Worker -> RAG pipeline
                  Redis <- job state / cache / session history
```

The default production path remains **dense retrieval with source weighting, CrossEncoder reranking, and deterministic conflict resolution**. BM25 and hybrid retrieval are implemented only for the recorded ablation study; they are not the default retrieval strategy.

## Core Features

- Three source-specific loaders and chunking strategies.
- ChromaDB retrieval with `all-MiniLM-L6-v2` embeddings.
- Source-authority weighting and `cross-encoder/ms-marco-MiniLM-L-6-v2` reranking.
- Version- and date-aware conflict handling before generation.
- Grounded answers whose `[n]` markers are mapped back to real chunk IDs.
- Synchronous (`POST /query`) and Kafka-backed asynchronous (`POST /jobs`) FastAPI endpoints.
- Redis job state, one-hour answer cache, and bounded session history.
- Fail-closed LLM configuration: OpenRouter's free router is the default; paid models require explicit opt-in and are never automatic fallbacks.

## Dataset and Evaluation

The knowledge base is an **internally constructed, synthetic technical-support scenario**, not real customer data or a public benchmark. It contains 540 source items and 590 chunks. The fixed retrieval evaluation set contains 120 queries with traceable reference answers and evidence IDs.

| Evaluation stage | Hit@5 | Recall@5 | MRR@5 |
|---|---:|---:|---:|
| Raw dense retrieval | 90.83% | 86.74% | 0.7979 |
| Final evidence selection | **95.00%** | **93.54%** | **0.9069** |

`Final evidence selection` includes the existing downstream reranking and version-aware conflict rules. The two rows describe different pipeline stages; they are not presented as a controlled algorithm-to-algorithm improvement.

The full 120-query **Answer Accuracy** and **Citation Correctness** evaluation has not yet been validated with live LLM generation, so no claim is made for those metrics.

## Docker Quick Start

Requirements: Docker Desktop (or Docker Engine with Compose) and an OpenRouter API key.

```bash
cp .env.example .env
# Set OPENROUTER_API_KEY in .env. Do not commit this file.

docker compose up --build -d
docker compose ps
curl http://localhost:8000/ready
```

Readiness should report `index_records: 590`. The default model is `openrouter/free`, and `CLOUDBOX_ALLOW_PAID_LLM=0` prevents accidental paid calls.

Synchronous request:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"How much free storage does CloudBox provide?"}'
```

Asynchronous request:

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"question":"How much free storage does CloudBox provide?","session_id":"demo"}'

curl http://localhost:8000/jobs/JOB_ID
curl http://localhost:8000/sessions/demo
```

In one validated Windows Docker run, the first asynchronous request completed in 21,306 ms and the identical Redis cache hit returned in 48 ms. These are single-run observations, not average latency or load-test results.

## Testing

Run the non-live regression suite after the local models and index are available:

```bash
CLOUDBOX_SKIP_UI_TESTS=1 \
CLOUDBOX_RUN_LIVE_LLM_TESTS=0 \
python -m unittest discover -s tests -p 'test_*.py' -v
```

The latest local run passed 120 tests; 8 configuration-gated tests were skipped. The suite covers retrieval, reranking, conflict handling, citation mapping, API contracts, queue/cache behavior, and error states without making live LLM calls.

GitHub Actions builds the Docker image (including the static 590-chunk index and local retrieval models), checks Python syntax, and runs the same offline tests inside that image. CI requires no API secrets and performs no deployment.

## Scope and Limitations

- The corpus and evaluation questions are synthetic and product-specific.
- Free model availability is controlled by OpenRouter and may vary.
- Kafka and Redis are single-instance, ephemeral services for a portfolio demonstration rather than a production distributed deployment.
- Retrieval metrics are validated; full live answer/citation evaluation across all 120 questions remains future work.
