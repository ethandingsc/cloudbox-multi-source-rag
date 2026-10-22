"""Step 1.5: failure analysis and four-way retrieval ablation.

No LLM is called. The existing dense pipeline is variant A and is not
modified. Variants B-D use the experimental BM25/RRF utilities in
``src.hybrid_retrieve`` with the same 12-candidate and 6-evidence budgets.
"""

import json
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import evaluate  # noqa: E402
from src import chunkers, config, conflict, hybrid_retrieve, rerank, retrieve  # noqa: E402
from src.answer import kept_evidence  # noqa: E402
from src.embed_store import EmbedStore  # noqa: E402


RRF_K = 60
CANDIDATE_BUDGET = config.CANDIDATE_POOL_SIZE
FINAL_BUDGET = config.FINAL_EVIDENCE_SIZE
DEV_MODULUS = 5  # q005, q010, ...: 24 fixed dev cases; other 96 are holdout.


def equivalent(hit: dict, expected: set[str]) -> bool:
    return (hit["chunk_id"] in expected or
            hybrid_retrieve.canonical_key(hit) in expected)


def expected_rank(expected_ids: list[str], hits: list[dict]) -> int | None:
    expected = set(expected_ids)
    for rank, hit in enumerate(hits, 1):
        if equivalent(hit, expected):
            return rank
    return None


def finalize(evidence: list[dict]) -> dict:
    return conflict.handle_contradictions(evidence[:FINAL_BUDGET])


def baseline_stages(question: str, retriever, cross_encoder) -> dict:
    raw = retriever.retrieve(question)
    pool = retrieve.weight_candidates(raw, pool_size=CANDIDATE_BUDGET)
    reranked = cross_encoder.rerank(question, pool, top_n=FINAL_BUDGET)
    final = conflict.handle_contradictions(reranked)
    return {"raw": raw, "pool": pool, "reranked": reranked, "final": final}


def bm25_only(question: str, bm25) -> dict:
    raw = bm25.retrieve(question)
    pool = hybrid_retrieve.weighted_unique(
        raw, "bm25_score", limit=CANDIDATE_BUDGET)
    return finalize(pool)


def hybrid_pool(question: str, retriever, bm25) -> list[dict]:
    dense = hybrid_retrieve.dense_weighted_ranking(
        retriever.retrieve(question))
    sparse = hybrid_retrieve.bm25_weighted_ranking(
        bm25.retrieve(question))
    return hybrid_retrieve.reciprocal_rank_fusion(
        [dense, sparse], rrf_k=RRF_K, limit=CANDIDATE_BUDGET)


def hybrid_rrf(question: str, retriever, bm25) -> dict:
    return finalize(hybrid_pool(question, retriever, bm25))


def hybrid_reranked(question: str, retriever, bm25, cross_encoder) -> dict:
    pool = hybrid_pool(question, retriever, bm25)
    evidence = cross_encoder.rerank(question, pool, top_n=FINAL_BUDGET)
    return conflict.handle_contradictions(evidence)


def metric_record(query: dict, final: dict, latency_ms: float) -> dict:
    kept = kept_evidence(final["evidence"])
    top5 = kept[:5]
    hit, rank = evaluate.hit_rank(query["expected_evidence_ids"], top5)
    return {
        "id": query["id"],
        "hit_at_5": hit,
        "recall_at_5": evaluate.recall_at_k(
            query["expected_evidence_ids"], top5),
        "reciprocal_rank": evaluate.reciprocal_rank(rank),
        "first_relevant_rank": rank,
        "latency_ms": latency_ms,
        "kept_ids": [hit["chunk_id"] for hit in kept],
        "kept_canonical_ids": [hybrid_retrieve.canonical_key(hit) for hit in kept],
    }


def aggregate(records: list[dict]) -> dict:
    n = len(records)
    latencies = [record["latency_ms"] for record in records]
    return {
        "queries": n,
        "hit_at_5_hits": sum(record["hit_at_5"] for record in records),
        "hit_at_5": sum(record["hit_at_5"] for record in records) / n,
        "recall_at_5": sum(record["recall_at_5"] for record in records) / n,
        "mrr_at_5": sum(record["reciprocal_rank"] for record in records) / n,
        "average_latency_ms": statistics.mean(latencies),
        "median_latency_ms": statistics.median(latencies),
    }


def split_metrics(records: list[dict]) -> dict:
    dev = [r for r in records if int(r["id"][1:]) % DEV_MODULUS == 0]
    test = [r for r in records if int(r["id"][1:]) % DEV_MODULUS != 0]
    return {"all_120": aggregate(records), "dev_24": aggregate(dev),
            "holdout_96": aggregate(test)}


def expected_policy_mismatch(query: dict, chunk_by_id: dict) -> bool:
    for chunk_id in query["expected_evidence_ids"]:
        chunk = chunk_by_id[chunk_id]
        if (chunk["source_type"] == "blog" and chunk.get("version") and
                chunk["version"] < config.CURRENT_VERSION):
            return True
        if (chunk["source_type"] == "forum" and
                chunk.get("date", "") < config.CURRENT_VERSION_RELEASE_DATE):
            return True
    return False


def analyze_failure(query: dict, stages: dict, chunk_by_id: dict) -> dict:
    expected = query["expected_evidence_ids"]
    kept = kept_evidence(stages["final"]["evidence"])
    if expected_policy_mismatch(query, chunk_by_id):
        reason = "ground_truth_conflicts_with_suppression_policy"
    elif expected_rank(expected, stages["raw"]) is None:
        reason = "dense_not_recalled"
    elif expected_rank(expected, stages["pool"]) is None:
        reason = "source_weighting_or_candidate_pool_drop"
    elif expected_rank(expected, stages["reranked"]) is None:
        reason = "crossencoder_drop"
    elif any(equivalent(hit, set(expected)) and
             hit.get("conflict_status") == "suppressed"
             for hit in stages["final"]["evidence"]):
        reason = "conflict_suppressed"
    elif expected_rank(expected, kept[:5]) is None and expected_rank(expected, kept):
        reason = "top5_cutoff"
    else:
        reason = "evidence_equivalence_or_annotation_issue"
    return {
        "id": query["id"], "query": query["query"], "reason": reason,
        "expected_evidence_ids": expected,
        "raw_rank": expected_rank(expected, stages["raw"]),
        "weighted_pool_rank": expected_rank(expected, stages["pool"]),
        "reranked_rank": expected_rank(expected, stages["reranked"]),
        "kept_rank": expected_rank(expected, kept),
    }


def timed(callable_):
    start = time.perf_counter()
    result = callable_()
    return result, (time.perf_counter() - start) * 1000.0


def main() -> None:
    data = evaluate.load_queries()
    chunks = chunkers.run()
    chunk_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    problems = evaluate.validate_dataset(data, set(chunk_by_id))
    if problems:
        raise ValueError("; ".join(problems))

    store = EmbedStore()
    dense = retrieve.Retriever(store)
    cross_encoder = rerank.Reranker()
    bm25 = hybrid_retrieve.BM25Index(chunks)

    # One untimed warm-up removes model initialization from latency metrics.
    warm = data["queries"][0]["query"]
    warm_dense = dense.retrieve(warm)
    cross_encoder.rerank(warm, retrieve.weight_candidates(warm_dense),
                         top_n=FINAL_BUDGET)
    bm25.retrieve(warm)

    records = {name: [] for name in ("A_baseline", "B_bm25_only",
                                      "C_dense_bm25_rrf", "D_hybrid_reranked")}
    failures = []
    for query in data["queries"]:
        stages, latency = timed(
            lambda q=query: baseline_stages(q["query"], dense, cross_encoder))
        records["A_baseline"].append(metric_record(query, stages["final"], latency))
        if not records["A_baseline"][-1]["hit_at_5"]:
            failures.append(analyze_failure(query, stages, chunk_by_id))

        result, latency = timed(lambda q=query: bm25_only(q["query"], bm25))
        records["B_bm25_only"].append(metric_record(query, result, latency))

        result, latency = timed(
            lambda q=query: hybrid_rrf(q["query"], dense, bm25))
        records["C_dense_bm25_rrf"].append(metric_record(query, result, latency))

        result, latency = timed(
            lambda q=query: hybrid_reranked(
                q["query"], dense, bm25, cross_encoder))
        records["D_hybrid_reranked"].append(metric_record(query, result, latency))
        print(f"ran {query['id']}", file=sys.stderr)

    metrics = {name: split_metrics(items) for name, items in records.items()}
    baseline_test = metrics["A_baseline"]["holdout_96"]
    hybrid_test = metrics["D_hybrid_reranked"]["holdout_96"]
    hit_delta = hybrid_test["hit_at_5"] - baseline_test["hit_at_5"]
    recall_delta = hybrid_test["recall_at_5"] - baseline_test["recall_at_5"]
    mrr_delta = hybrid_test["mrr_at_5"] - baseline_test["mrr_at_5"]
    latency_ratio = (hybrid_test["average_latency_ms"] /
                     baseline_test["average_latency_ms"])
    adopt = (hit_delta >= 0.02 and recall_delta >= 0.0 and
             mrr_delta >= -0.01 and latency_ratio <= 2.0)

    output = {
        "meta": {
            "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "queries": len(data["queries"]), "documents": 540,
            "chunks": len(chunks), "candidate_budget": CANDIDATE_BUDGET,
            "final_evidence_budget": FINAL_BUDGET,
            "metric_cutoff": 5, "bm25_k1": bm25.k1, "bm25_b": bm25.b,
            "rrf_k": RRF_K, "tokenizer": hybrid_retrieve.TOKEN_RE.pattern,
            "split": "qNNN % 5 == 0 -> dev (24); otherwise holdout (96)",
            "parameter_search": "none; one predeclared configuration",
            "latency_scope": "warm per-query retrieval through conflict handling; BM25 index build excluded",
        },
        "failure_summary": dict(Counter(f["reason"] for f in failures)),
        "failures": failures,
        "metrics": metrics,
        "decision": {
            "rule": "adopt only if holdout Hit@5 improves >=2 points, Recall@5 does not decline, MRR@5 declines by <1 point, and latency <=2x",
            "holdout_hit_delta": hit_delta,
            "holdout_recall_delta": recall_delta,
            "holdout_mrr_delta": mrr_delta,
            "holdout_latency_ratio": latency_ratio,
            "adopt_hybrid": adopt,
        },
        "per_query": records,
    }
    out = config.EVAL_RESULTS_DIR / "hybrid_ablation_120.json"
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(json.dumps({"failure_summary": output["failure_summary"],
                      "all_120": {k: v["all_120"] for k, v in metrics.items()},
                      "holdout_96": {k: v["holdout_96"] for k, v in metrics.items()},
                      "decision": output["decision"]}, indent=2))
    print(f"results written to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
