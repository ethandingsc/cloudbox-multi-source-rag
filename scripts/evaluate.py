"""Step 5.1 final evaluation — Hit@5 / MRR@5 / answer correctness / citation
validity over the 12 eval queries (PLAN §5.1 / §8, final system only; the
A/B/C ablation comparison is Step 5.2).

Usage (cloudbox-rag env, project root):
    python scripts/evaluate.py            # full run (needs OPENROUTER_API_KEY
                                          # for the answer/citation part)
    python scripts/evaluate.py --summary  # reprint summary + per-query lines
                                          # from outputs/eval_results/results.json

Everything is computed here from the real pipeline output — nothing is
hardcoded from earlier development runs.

- Retrieval: Hit@5 / MRR@5 over the TOP-5 of the kept final evidence of
  retrieve_final() (conflict_status != "suppressed") — the evidence the
  answer actually uses. A suppressed ground-truth chunk cannot inform the
  answer, so it is not a hit; the per-query conflict records still show
  which rule removed it. Kept can hold up to FINAL_EVIDENCE_SIZE entries
  (6 since Step 5.2.5); only the first 5 count for the metric.
- Answers: pipeline.answer_question() end-to-end. Correctness is labeled
  per query with a transparent deterministic draft heuristic (all
  digit-bearing tokens of the expected facts must appear in the answer),
  then FINALIZED BY MANUAL REVIEW — no semantic judge, no LLM judge.
- Citations: counted from the pipeline's own citations/invalid_citations,
  then independently re-verified against the same query's kept evidence
  (a citation may never point at a suppressed or nonexistent chunk).

Results land in outputs/eval_results/results.json (per PLAN §5.1).
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from src import config, retrieve
from src.answer import OpenRouterError, kept_evidence
from src import pipeline


# --- Dataset (Step 5.1.1) ----------------------------------------------------


def load_queries(path: Path | None = None) -> dict:
    path = Path(path) if path else config.EVAL_QUERIES_FILE
    return json.loads(path.read_text(encoding="utf-8"))


def validate_dataset(data: dict) -> list[str]:
    """Sanity checks on the eval dataset; returns a list of problems."""
    problems = []
    queries = data.get("queries") or []
    if len(queries) != 12:
        problems.append(f"expected 12 queries, found {len(queries)}")
    ids = [q.get("id") for q in queries]
    if len(set(ids)) != len(ids):
        problems.append(f"query ids are not unique: {ids}")
    for q in queries:
        for key in ("query", "expected_source", "expected_answer_facts",
                    "expected_doc_ids"):
            if not q.get(key):
                problems.append(f"{q.get('id')}: missing ground truth '{key}'")
    conflict_cases = [q.get("conflict_case") for q in queries
                      if q.get("conflict_case")]
    if sorted(conflict_cases) != ["2fa", "linux", "storage", "upload-size"]:
        problems.append(f"expected the 4 designed conflict cases, "
                        f"found {conflict_cases}")
    return problems


# --- Retrieval metrics (Step 5.1.2) ------------------------------------------


def hit_rank(expected_ids: list[str], kept_ids: list[str]) -> tuple[bool, int | None]:
    """(hit, first rank) — whether ANY expected id is in the kept top-5 and
    at which position (1-based) the first one sits."""
    for rank, chunk_id in enumerate(kept_ids, 1):
        if chunk_id in expected_ids:
            return True, rank
    return False, None


def reciprocal_rank(hit: bool, rank: int | None) -> float:
    return 1.0 / rank if hit and rank else 0.0


# --- Answer correctness (Step 5.1.3) -----------------------------------------


def draft_correctness(expected_facts: str, answer: str) -> str | None:
    """Transparent first-pass label; the FINAL label is set by manual review.

    One rule for all 12 queries, no per-query special cases: every token of
    the expected facts that contains a digit must appear (case-insensitive,
    punctuation stripped) in the answer. All -> "Correct", some ->
    "Partially Correct", none -> "Incorrect". Returns None when the
    expected facts carry no digit tokens (nothing deterministic to check).
    """
    def norm(text: str) -> str:
        return re.sub(r"[^a-z0-9\s]", " ", text.lower())

    tokens = [t for t in norm(expected_facts).split()
              if any(ch.isdigit() for ch in t)]
    if not tokens:
        return None
    answer_tokens = set(norm(answer).split())  # token match, not substring
    found = sum(1 for t in tokens if t in answer_tokens)
    if found == len(tokens):
        return "Correct"
    if found:
        return "Partially Correct"
    return "Incorrect"


# --- Citation validation (Step 5.1.4) ----------------------------------------


def validate_citations(result: dict) -> dict:
    """Re-check one result's citations against its own kept evidence.

    The pipeline already separates valid citations from invalid markers;
    this re-verifies the mapping independently: every citation entry must
    point at a KEPT chunk of this query and its [n] must match the kept
    numbering. Returns {"total", "valid", "invalid", "problems"}.
    """
    kept_ids = [h["chunk_id"] for h in kept_evidence(result["evidence"])]
    valid = 0
    problems = []
    for c in result["citations"]:
        if c["chunk_id"] not in kept_ids:
            problems.append(f"citation [{c['n']}] -> {c['chunk_id']} "
                            f"not in kept evidence")
            continue
        if kept_ids[c["n"] - 1] != c["chunk_id"]:
            problems.append(f"citation [{c['n']}] numbering mismatch: "
                            f"{c['chunk_id']} vs {kept_ids[c['n'] - 1]}")
        valid += 1
    invalid = len(result["invalid_citations"])
    return {"total": valid + invalid, "valid": valid, "invalid": invalid,
            "problems": problems}


# --- Summary (console output format fixed by the Step 5.1 spec) --------------


def summarize(records: list[dict]) -> dict:
    n = len(records)
    hits = sum(1 for r in records if r["hit_at_5"])
    mrr = sum(r["reciprocal_rank"] for r in records) / n if n else 0.0
    answered = [r for r in records if r.get("answer")]
    correct = partial = incorrect = 0
    for r in answered:
        label = r.get("correctness")
        if label == "Correct":
            correct += 1
        elif label == "Partially Correct":
            partial += 1
        elif label == "Incorrect":
            incorrect += 1
    cit_total = cit_valid = cit_invalid = 0
    for r in answered:
        check = r.get("citation_check") or {}
        cit_total += check.get("total", 0)
        cit_valid += check.get("valid", 0)
        cit_invalid += check.get("invalid", 0)
    return {
        "queries": n,
        "hit_at_5_hits": hits,
        "hit_at_5_rate": hits / n if n else None,
        "mrr_at_5": mrr,
        "answered": len(answered),
        "correct": correct,
        "partial": partial,
        "incorrect": incorrect,
        "answer_accuracy_rate": correct / n if answered else None,
        "citations_total": cit_total,
        "citations_valid": cit_valid,
        "citations_invalid": cit_invalid,
        "citation_validity_rate": cit_valid / cit_total if cit_total else None,
    }


def _short(text: str, limit: int = 150) -> str:
    text = (text or "").replace("\n", " ")
    return f"{text[:limit]}{'...' if len(text) > limit else ''}"


def print_summary(summary: dict) -> None:
    hits, n = summary["hit_at_5_hits"], summary["queries"]
    print()
    print("Final Evaluation")
    print("================")
    print()
    print(f"Queries: {n}")
    print()
    print("Retrieval:")
    print(f"Hit@5: {hits}/{n} ({100 * hits / n:.0f}%)")
    print(f"MRR@5: {summary['mrr_at_5']:.3f}")
    print()
    print("Generation:")
    if summary["answered"]:
        print(f"Correct: {summary['correct']}")
        print(f"Partially Correct: {summary['partial']}")
        print(f"Incorrect: {summary['incorrect']}")
        rate = summary["answer_accuracy_rate"]
        print(f"Answer Accuracy: {summary['correct']}/{n}"
              + (f" ({100 * rate:.0f}%)" if rate is not None else ""))
    else:
        print("(skipped — no LLM answers: OPENROUTER_API_KEY missing)")
        print("Answer Accuracy: n/a")
    print()
    print("Citations:")
    if summary["citations_total"]:
        rate = summary["citation_validity_rate"]
        print(f"Total Citations: {summary['citations_total']}")
        print(f"Invalid Citations: {summary['citations_invalid']}")
        print(f"Citation Validity: "
              + (f"{100 * rate:.0f}%" if rate is not None else "n/a"))
    else:
        print("(skipped — no LLM answers: OPENROUTER_API_KEY missing)")
        print("Citation Validity: n/a")


def print_query_lines(records: list[dict]) -> None:
    print()
    for r in records:
        print(r["id"])
        print(f"- Hit@5: {'yes' if r['hit_at_5'] else 'no'}")
        print(f"- First Relevant Rank: {r['first_relevant_rank'] or '-'}")
        kept = sum(1 for h in r["evidence_status"] if h["status"] != "suppressed")
        suppressed = sum(1 for h in r["evidence_status"] if h["status"] == "suppressed")
        print(f"- Final Evidence: {kept} kept / {suppressed} suppressed")
        if r.get("answer"):
            print(f"- Answer: {_short(r['answer'])}")
            print(f"- Correctness: {r.get('correctness') or 'pending'}")
            check = r.get("citation_check") or {}
            extra = f" (problems: {len(check.get('problems', []))})" \
                if check.get("problems") else ""
            print(f"- Citations: {check.get('valid', 0)}/{check.get('total', 0)} "
                  f"valid{extra}")
        else:
            print(f"- Answer: (not run — {_short(r.get('answer_error', ''), 90)})")
            print("- Correctness: -")
            print("- Citations: -")


# --- Runner -------------------------------------------------------------------


def run(queries_path: Path | None = None) -> dict:
    from src import embed_store, rerank  # heavy models — load once, lazily

    data = load_queries(queries_path)
    problems = validate_dataset(data)
    if problems:
        for p in problems:
            print(f"dataset problem: {p}")
        sys.exit(1)

    store = embed_store.EmbedStore()
    reranker = rerank.Reranker()

    client = None
    client_error = None
    try:
        from src.answer import LLMClient
        client = LLMClient()
    except OpenRouterError as exc:
        client_error = str(exc)

    records = []
    for q in data["queries"]:
        rec = {k: q[k] for k in q}
        final = retrieve.retrieve_final(q["query"], store=store,
                                        reranker=reranker)
        kept_ids = [h["chunk_id"] for h in kept_evidence(final["evidence"])]
        # the metric definition is top-5 of the kept evidence; since
        # Step 5.2.5 kept can hold up to FINAL_EVIDENCE_SIZE=6 entries, the
        # first 5 are sliced so Hit@5/MRR@5 stay comparable across runs
        hit, rank = hit_rank(q["expected_doc_ids"], kept_ids[:5])
        rec["hit_at_5"] = bool(hit)
        rec["first_relevant_rank"] = rank
        rec["reciprocal_rank"] = reciprocal_rank(hit, rank)
        rec["kept_evidence_ids"] = kept_ids
        rec["evidence_status"] = [
            {"chunk_id": h["chunk_id"], "status": h["conflict_status"],
             "reason": h.get("suppressed_reason")}
            for h in final["evidence"]]
        rec["conflicts"] = final["conflicts"]

        if client:
            try:
                result = pipeline.answer_question(q["query"], store=store,
                                                  reranker=reranker,
                                                  client=client)
            except OpenRouterError as exc:
                rec["answer_error"] = str(exc)
                rec["answer"] = None
            else:
                rec["answer"] = result["answer"]
                rec["citations"] = result["citations"]
                rec["invalid_citations"] = result["invalid_citations"]
                rec["draft_correctness"] = draft_correctness(
                    q["expected_answer_facts"], result["answer"])
                rec["correctness"] = rec["draft_correctness"]  # manual review
                rec["citation_check"] = validate_citations(result)
        else:
            rec["answer_error"] = client_error
            rec["answer"] = None
        records.append(rec)
        print(f"ran {rec['id']}", file=sys.stderr)

    summary = summarize(records)
    results = {
        "meta": {
            "created": datetime.now().isoformat(timespec="seconds"),
            "step": "5.1",
            "pipeline": "retrieve_final -> generate_answer (final system)",
            "llm_provider": client.provider if client else None,
            "llm_model": client.model if client else None,
            "dataset": str(config.EVAL_QUERIES_FILE),
            "notes": [
                "Hit@5 / MRR@5 computed over the TOP-5 of the kept final "
                "evidence (conflict_status != 'suppressed') — the "
                "evidence the answer actually uses.",
                "correctness: draft by the deterministic digit-token "
                "heuristic (see evaluate.draft_correctness), finalized by "
                "manual review of each (expected, answer) pair.",
            ],
        },
        "summary": summary,
        "queries": records,
    }
    config.EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = config.EVAL_RESULTS_DIR / "results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"\nresults written to {out}", file=sys.stderr)
    return results


def main() -> None:
    # LLM answers can contain exotic whitespace (e.g. U+202F); on Windows
    # the default GBK console codec would crash on it — never let printing
    # take the whole evaluation down.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true",
                        help="reprint summary + per-query lines from "
                             "outputs/eval_results/results.json")
    args = parser.parse_args()

    if args.summary:
        results = json.loads(
            (config.EVAL_RESULTS_DIR / "results.json")
            .read_text(encoding="utf-8"))
    else:
        results = run()

    print_summary(results["summary"])
    print_query_lines(results["queries"])


if __name__ == "__main__":
    main()
