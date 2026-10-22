"""Run the reproducible 120-case CloudBox retrieval and answer evaluation.

Retrieval metrics use the final, non-suppressed top five evidence items. A
synthetic item is evidence-equivalent to its canonical source via
``derived_from``. Answer accuracy uses a pre-declared automatic check: answer
and reference cosine similarity >= 0.70, with every reference number present.
Citation correctness requires a valid marker that maps to expected evidence.
Paid providers/models are refused unless ``--allow-paid`` is explicit.
"""

import argparse
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, conflict, pipeline, retrieve
from src.answer import LLMClient, OpenRouterError, kept_evidence

ANSWER_SIMILARITY_THRESHOLD = 0.70
PARTIAL_SIMILARITY_THRESHOLD = 0.55
EXPECTED_QUERY_COUNT = 120
EXPECTED_CATEGORY_COUNTS = {"direct": 89, "conflict": 17, "multi_source": 14}


class EvaluationClient:
    """Force temperature zero while preserving the configured client/model."""

    def __init__(self, client: LLMClient):
        self._client = client
        self.provider = client.provider
        self.model = client.model

    def complete(self, prompt: str, max_tokens: int | None = None,
                 temperature: float | None = None) -> str:
        return self._client.complete(prompt, max_tokens=max_tokens,
                                     temperature=0.0)


def load_queries(path: Path | None = None) -> dict:
    path = Path(path) if path else config.EVAL_QUERIES_FILE
    return json.loads(path.read_text(encoding="utf-8"))


def validate_dataset(data: dict, chunk_ids: set[str] | None = None) -> list[str]:
    problems = []
    queries = data.get("queries") or []
    if len(queries) != EXPECTED_QUERY_COUNT:
        problems.append(f"expected {EXPECTED_QUERY_COUNT} queries, found {len(queries)}")
    ids = [q.get("id") for q in queries]
    if len(set(ids)) != len(ids):
        problems.append("query ids are not unique")
    counts = Counter(q.get("category") for q in queries)
    if dict(counts) != EXPECTED_CATEGORY_COUNTS:
        problems.append(f"category counts {dict(counts)} != {EXPECTED_CATEGORY_COUNTS}")
    covered_sources = set()
    for q in queries:
        for key in ("query", "expected_answer", "expected_evidence_ids",
                    "expected_sources", "category", "raw_evidence_groups",
                    "final_evidence_groups"):
            if not q.get(key):
                problems.append(f"{q.get('id')}: missing ground truth '{key}'")
        covered_sources.update(q.get("expected_sources") or [])
        if chunk_ids is not None:
            grouped_ids = {
                chunk_id
                for key in ("raw_evidence_groups", "final_evidence_groups")
                for group in (q.get(key) or [])
                for chunk_id in group
            }
            missing = grouped_ids - chunk_ids
            if missing:
                problems.append(f"{q.get('id')}: unknown evidence IDs {sorted(missing)}")
    if covered_sources != set(config.SOURCE_TYPES):
        problems.append(f"source coverage {sorted(covered_sources)} is incomplete")
    conflict_counts = Counter(q.get("conflict_case") for q in queries
                              if q.get("conflict_case"))
    expected_conflicts = Counter({"storage": 4, "upload-size": 4,
                                  "2fa": 4, "linux": 4})
    if conflict_counts != expected_conflicts:
        problems.append(f"conflict coverage is wrong: {dict(conflict_counts)}")
    return problems


def canonical_id(hit: dict) -> str:
    return hit.get("metadata", {}).get("derived_from") or hit["chunk_id"]


def hit_rank(expected_ids: list[str], kept_hits: list[dict]) -> tuple[bool, int | None]:
    expected = set(expected_ids)
    for rank, hit in enumerate(kept_hits, 1):
        if canonical_id(hit) in expected or hit["chunk_id"] in expected:
            return True, rank
    return False, None


def recall_at_k(expected_ids: list[str], kept_hits: list[dict]) -> float:
    expected = set(expected_ids)
    found = set()
    for hit in kept_hits:
        if canonical_id(hit) in expected:
            found.add(canonical_id(hit))
        if hit["chunk_id"] in expected:
            found.add(hit["chunk_id"])
    return len(found) / len(expected) if expected else 0.0


def hit_rank_groups(groups: list[list[str]], hits: list[dict]) -> tuple[bool, int | None]:
    """First rank matching any acceptable evidence alternative."""
    acceptable = {chunk_id for group in groups for chunk_id in group}
    return hit_rank(list(acceptable), hits)


def recall_groups(groups: list[list[str]], hits: list[dict]) -> float:
    """Macro recall over required fact groups; IDs inside a group are OR."""
    if not groups:
        return 0.0
    found = 0
    for group in groups:
        expected = set(group)
        if any(canonical_id(hit) in expected or hit["chunk_id"] in expected
               for hit in hits):
            found += 1
    return found / len(groups)


def reciprocal_rank(rank: int | None) -> float:
    return 1.0 / rank if rank else 0.0


def numeric_tokens(text: str) -> set[str]:
    return set(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?(?:%|gb|tb|mb)?", text.lower()))


def cosine_similarity(a, b) -> float:
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    na = math.sqrt(sum(float(x) * float(x) for x in a))
    nb = math.sqrt(sum(float(y) * float(y) for y in b))
    return dot / (na * nb) if na and nb else 0.0


def score_answer(expected: str, answer: str, encoder) -> dict:
    vectors = encoder.encode([expected, answer], normalize_embeddings=True)
    similarity = cosine_similarity(vectors[0], vectors[1])
    expected_numbers = numeric_tokens(expected)
    missing_numbers = sorted(expected_numbers - numeric_tokens(answer))
    if similarity >= ANSWER_SIMILARITY_THRESHOLD and not missing_numbers:
        label = "Correct"
    elif similarity >= PARTIAL_SIMILARITY_THRESHOLD:
        label = "Partially Correct"
    else:
        label = "Incorrect"
    return {"label": label, "semantic_similarity": similarity,
            "expected_numbers": sorted(expected_numbers),
            "missing_numbers": missing_numbers}


def validate_citations(result: dict, expected_ids: list[str]) -> dict:
    kept = kept_evidence(result["evidence"])
    kept_by_number = {i: hit for i, hit in enumerate(kept, 1)}
    expected = set(expected_ids)
    correct = 0
    details = []
    for citation in result["citations"]:
        hit = kept_by_number.get(citation["n"])
        marker_valid = bool(hit and hit["chunk_id"] == citation["chunk_id"])
        evidence_correct = bool(marker_valid and
                                (hit["chunk_id"] in expected or
                                 canonical_id(hit) in expected))
        correct += int(evidence_correct)
        details.append({"n": citation["n"], "chunk_id": citation["chunk_id"],
                        "canonical_id": canonical_id(hit) if hit else None,
                        "marker_valid": marker_valid,
                        "evidence_correct": evidence_correct})
    invalid_markers = list(result["invalid_citations"])
    total = len(result["citations"]) + len(invalid_markers)
    return {"total": total, "correct": correct,
            "incorrect": total - correct,
            "invalid_markers": invalid_markers, "details": details}


def summarize(records: list[dict]) -> dict:
    n = len(records)
    answered = [r for r in records if r.get("answer")]
    citations_total = sum((r.get("citation_check") or {}).get("total", 0)
                          for r in answered)
    citations_correct = sum((r.get("citation_check") or {}).get("correct", 0)
                            for r in answered)
    labels = Counter(r.get("answer_score", {}).get("label") for r in answered)
    def stage(prefix: str) -> dict:
        hits = sum(bool(r[f"{prefix}_hit_at_5"]) for r in records)
        return {
            "queries": n,
            "hit_at_5_hits": hits,
            "hit_at_5": hits / n if n else None,
            "recall_at_5": (sum(r[f"{prefix}_recall_at_5"] for r in records) / n
                            if n else None),
            "mrr_at_5": (sum(r[f"{prefix}_reciprocal_rank"] for r in records) / n
                         if n else None),
        }

    raw = stage("raw")
    final = stage("final")
    return {
        "queries": n,
        "successful_retrievals": sum(not r.get("retrieval_error") for r in records),
        "raw_retrieval": raw,
        "final_evidence_selection": final,
        # Backward-compatible aliases remain the final-evidence metrics.
        "hit_at_5_hits": final["hit_at_5_hits"],
        "hit_at_5": final["hit_at_5"],
        "recall_at_5": final["recall_at_5"],
        "mrr_at_5": final["mrr_at_5"],
        "answered": len(answered),
        "correct": labels["Correct"],
        "partial": labels["Partially Correct"],
        "incorrect": labels["Incorrect"],
        "answer_accuracy": (labels["Correct"] / n if len(answered) == n and n
                            else None),
        "citations_total": citations_total,
        "citations_correct": citations_correct,
        "citation_correctness": (citations_correct / citations_total
                                 if citations_total else None),
    }


def corpus_and_index_check(store) -> dict:
    from src import chunkers, loaders

    chunks = chunkers.run()
    chunk_ids = [c["chunk_id"] for c in chunks]
    indexed = store.collection.get(include=["metadatas"])
    index_ids = indexed["ids"]
    return {
        "source_items": len(loaders.load_all()),
        "chunks": len(chunks),
        "index_records": store.count(),
        "chunk_source_counts": dict(Counter(c["source_type"] for c in chunks)),
        "index_source_counts": dict(Counter(m["source_type"] for m in indexed["metadatas"])),
        "duplicate_chunk_ids": len(chunk_ids) - len(set(chunk_ids)),
        "missing_from_index": sorted(set(chunk_ids) - set(index_ids)),
        "extra_in_index": sorted(set(index_ids) - set(chunk_ids)),
    }


def make_client(provider: str | None, allow_paid: bool):
    client = LLMClient(provider=provider)
    is_free = (client.provider == config.LLM_PROVIDER_OPENROUTER and
               ":free" in client.model)
    if not is_free and not allow_paid:
        raise OpenRouterError(
            f"refusing paid evaluation model '{client.model}' on {client.provider}; "
            "use a :free OpenRouter model or pass --allow-paid after approval")
    return EvaluationClient(client)


def run(queries_path: Path | None = None, retrieval_only: bool = False,
        provider: str | None = None, allow_paid: bool = False,
        limit: int | None = None, output: Path | None = None) -> dict:
    from src import embed_store, rerank

    data = load_queries(queries_path)
    store = embed_store.EmbedStore()
    integrity = corpus_and_index_check(store)
    all_chunk_ids = set(store.collection.get(include=[])["ids"])
    problems = validate_dataset(data, all_chunk_ids)
    if integrity["chunks"] != 590 or integrity["source_items"] != 540:
        problems.append("corpus size is not the expected 540 items / 590 chunks")
    if (integrity["index_records"] != integrity["chunks"] or
            integrity["duplicate_chunk_ids"] or integrity["missing_from_index"] or
            integrity["extra_in_index"]):
        problems.append("corpus and Chroma index are inconsistent")
    if problems:
        raise ValueError("; ".join(problems))

    queries = data["queries"][:limit] if limit else data["queries"]
    reranker = rerank.Reranker()
    retriever = retrieve.Retriever(store)
    client = None
    client_error = None
    if not retrieval_only:
        try:
            client = make_client(provider, allow_paid)
        except OpenRouterError as exc:
            client_error = str(exc)

    records = []
    for q in queries:
        rec = dict(q)
        try:
            raw = retriever.retrieve(q["query"])
            pool = retrieve.weight_candidates(raw)
            reranked = reranker.rerank(q["query"], pool)
            final = conflict.handle_contradictions(reranked,
                                                   question=q["query"])
        except Exception as exc:
            rec.update({"retrieval_error": str(exc),
                        "raw_hit_at_5": False, "raw_first_relevant_rank": None,
                        "raw_recall_at_5": 0.0, "raw_reciprocal_rank": 0.0,
                        "final_hit_at_5": False, "final_first_relevant_rank": None,
                        "final_recall_at_5": 0.0, "final_reciprocal_rank": 0.0,
                        "hit_at_5": False, "first_relevant_rank": None,
                        "recall_at_5": 0.0, "reciprocal_rank": 0.0,
                        "raw_evidence_ids": [], "kept_evidence_ids": [],
                        "evidence_status": [], "conflicts": [], "answer": None})
            records.append(rec)
            continue

        raw_top5 = raw[:5]
        kept = kept_evidence(final["evidence"])
        final_top5 = kept[:5]
        raw_hit, raw_rank = hit_rank_groups(q["raw_evidence_groups"], raw_top5)
        final_hit, final_rank = hit_rank_groups(
            q["final_evidence_groups"], final_top5)
        rec.update({
            "raw_hit_at_5": raw_hit,
            "raw_first_relevant_rank": raw_rank,
            "raw_recall_at_5": recall_groups(q["raw_evidence_groups"], raw_top5),
            "raw_reciprocal_rank": reciprocal_rank(raw_rank),
            "final_hit_at_5": final_hit,
            "final_first_relevant_rank": final_rank,
            "final_recall_at_5": recall_groups(
                q["final_evidence_groups"], final_top5),
            "final_reciprocal_rank": reciprocal_rank(final_rank),
            # Backward-compatible aliases are final-evidence metrics.
            "hit_at_5": final_hit,
            "first_relevant_rank": final_rank,
            "recall_at_5": recall_groups(q["final_evidence_groups"], final_top5),
            "reciprocal_rank": reciprocal_rank(final_rank),
            "raw_evidence_ids": [h["chunk_id"] for h in raw_top5],
            "raw_canonical_ids": [canonical_id(h) for h in raw_top5],
            "kept_evidence_ids": [h["chunk_id"] for h in kept],
            "kept_canonical_ids": [canonical_id(h) for h in kept],
            "evidence_status": [
                {"chunk_id": h["chunk_id"], "canonical_id": canonical_id(h),
                 "source_type": h["source_type"],
                 "status": h["conflict_status"],
                 "reason": h.get("suppressed_reason")}
                for h in final["evidence"]],
            "conflicts": final["conflicts"],
        })

        if client:
            try:
                result = pipeline.answer_question(q["query"], store=store,
                                                  reranker=reranker,
                                                  client=client)
                rec["answer"] = result["answer"]
                rec["citations"] = result["citations"]
                rec["invalid_citations"] = result["invalid_citations"]
                rec["answer_score"] = score_answer(
                    q["expected_answer"], result["answer"], store.model)
                rec["citation_check"] = validate_citations(
                    result, q["expected_evidence_ids"])
            except Exception as exc:
                rec["answer"] = None
                rec["answer_error"] = str(exc)
        else:
            rec["answer"] = None
            rec["answer_error"] = ("retrieval-only run" if retrieval_only
                                   else client_error)
        records.append(rec)
        print(f"ran {rec['id']}", file=sys.stderr)

    results = {
        "meta": {
            "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dataset": str(queries_path or config.EVAL_QUERIES_FILE),
            "dataset_queries": len(queries),
            "pipeline": "raw dense top-5 -> weighting -> rerank -> conflict -> final kept top-5",
            "embedding_model": config.EMBED_MODEL,
            "rerank_model": config.RERANK_MODEL,
            "top_k_per_source": config.TOP_K_PER_SOURCE,
            "candidate_pool_size": config.CANDIDATE_POOL_SIZE,
            "final_evidence_size": config.FINAL_EVIDENCE_SIZE,
            "retrieval_metric_cutoff": 5,
            "raw_metric_definition": "top 5 merged dense hits before weighting/reranking/conflict",
            "final_metric_definition": "top 5 non-suppressed evidence after weighting/reranking/conflict",
            "gold_definition": "required evidence groups; IDs within each group are acceptable alternatives",
            "answer_similarity_threshold": ANSWER_SIMILARITY_THRESHOLD,
            "answer_numeric_consistency_required": True,
            "llm_provider": client.provider if client else None,
            "llm_model": client.model if client else None,
            "llm_temperature": 0.0 if client else None,
            "corpus_integrity": integrity,
        },
        "summary": summarize(records),
        "queries": records,
    }
    config.EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = (Path(output) if output else
           config.EVAL_RESULTS_DIR / "results_120_aligned.json")
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"results written to {out}", file=sys.stderr)
    return results


def print_summary(summary: dict) -> None:
    def pct(value):
        return "n/a" if value is None else f"{value * 100:.2f}%"

    print(f"Queries: {summary['queries']}")
    print(f"Successful retrievals: {summary['successful_retrievals']}")
    for label, key in (("Raw Retrieval", "raw_retrieval"),
                       ("Final Evidence", "final_evidence_selection")):
        stage = summary[key]
        print(f"{label} Hit@5: {stage['hit_at_5_hits']}/{summary['queries']} "
              f"({pct(stage['hit_at_5'])})")
        print(f"{label} Recall@5: {pct(stage['recall_at_5'])}")
        print(f"{label} MRR@5: {stage['mrr_at_5']:.4f}")
    print(f"Answers: {summary['answered']}/{summary['queries']}")
    print(f"Answer Accuracy: {pct(summary['answer_accuracy'])}")
    print(f"Citation Correctness: {pct(summary['citation_correctness'])}")


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--provider", choices=[config.LLM_PROVIDER_DEEPSEEK,
                                                config.LLM_PROVIDER_OPENROUTER])
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.summary:
        results = json.loads((config.EVAL_RESULTS_DIR / "results_120_aligned.json")
                             .read_text(encoding="utf-8"))
    else:
        results = run(retrieval_only=args.retrieval_only,
                      provider=args.provider, allow_paid=args.allow_paid,
                      limit=args.limit, output=args.output)
    print_summary(results["summary"])


if __name__ == "__main__":
    main()
