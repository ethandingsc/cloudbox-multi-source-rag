"""End-to-end pipeline orchestration (Step 4.4) — no new logic, only wiring.

answer_question() chains the finished stages exactly as they were built:

    retrieve_final()  (Steps 2–3: retrieve → weight → rerank → conflict)
      -> final evidence
      -> generate_answer()  (Steps 4.2–4.3: grounded prompt → LLM → citations)

One structured result dict carries everything the caller needs — the
question, the answer, the verified citations, and the full final evidence
with conflict status + scores — so any answer can be traced back to the
chunks that produced it. trace_text() renders that chain as plain text
for --debug; the same result fields are what the Step 4.5 JSONL logging
will record.
"""

from . import retrieve
from .answer import generate_answer, kept_evidence


def answer_question(question: str, sources=None, top_k: int | None = None,
                    pool_size: int | None = None,
                    final_size: int | None = None,
                    store=None, reranker=None,
                    client=None, model=None, api_key=None) -> dict:
    """Run the full grounded RAG pipeline for one question.

    Returns a single dict — every field of generate_answer() plus the
    traceability context:

        question          — the input question, echoed back
        answer            — the LLM answer text (or the fixed insufficient-
                            evidence reply when nothing was kept)
        citations         — [{"n", "chunk_id", "source_type", "title"}, ...],
                            computed from the answer's [n] markers against
                            the kept evidence only (Step 4.3)
        invalid_citations — [n, ...] markers the LLM used that map to no
                            kept evidence (dropped, not sources)
        evidence          — the complete Step 3.3 final evidence list:
                            every chunk with its scores and conflict_status
                            ("kept" | "suppressed" | "conflict_candidate",
                            + suppressed_reason / authority when applicable).
                            Suppressed chunks stay here, marked, so the
                            decision is auditable — they simply never reach
                            the LLM (Steps 4.2–4.3).
        conflicts         — Step 3.3 conflict records (rule + chunk + winner)

    sources / top_k / pool_size / final_size / store / reranker pass
    straight through to retrieve_final(); client / model / api_key to
    generate_answer(). Errors from any stage propagate unchanged.
    """
    final = retrieve.retrieve_final(question, sources=sources, top_k=top_k,
                                    pool_size=pool_size,
                                    final_size=final_size,
                                    store=store, reranker=reranker)
    result = generate_answer(question, final["evidence"],
                             client=client, model=model, api_key=api_key)
    result["question"] = question
    result["evidence"] = final["evidence"]
    result["conflicts"] = final["conflicts"]
    return result


def trace_text(result: dict) -> str:
    """Render one result as a plain-text walkthrough of the full chain.

    question -> final evidence (with [n] numbering for kept chunks and
    conflict status/reason for the others) -> conflict records -> LLM
    answer -> citations mapped back to chunk/source. Deliberately plain
    text — no observability framework; main.py --debug prints it as-is.
    """
    kept = kept_evidence(result["evidence"])
    numbered = {h["chunk_id"]: i for i, h in enumerate(kept, 1)}

    lines = [f"question: {result['question']}", "", "final evidence (Step 3.3):"]
    for h in result["evidence"]:
        prefix = f"  [{numbered[h['chunk_id']]}]" if h["chunk_id"] in numbered \
            else "   - "
        score = (f"  rerank={h['rerank_score']:.4f}"
                 if "rerank_score" in h else "")
        status = h["conflict_status"]
        detail = f"  ({h['suppressed_reason']})" if status == "suppressed" else ""
        lines.append(f"{prefix} {h['chunk_id']}  ({h['source_type']})  "
                     f"{status}{detail}{score}")

    lines += ["", "conflicts:"]
    if not result["conflicts"]:
        lines.append("  none")
    for c in result["conflicts"]:
        lines.append(f"  {c['rule']}: {c['chunk_id']} -> winner {c['winner_id']}")

    lines += ["", "answer:", f"  {result['answer']}", "", "citations:"]
    if not result["citations"]:
        lines.append("  none")
    for c in result["citations"]:
        lines.append(f"  [{c['n']}] {c['chunk_id']}  "
                     f"({c['source_type']}, \"{c['title']}\")")
    if result["invalid_citations"]:
        lines.append(f"invalid citation markers (dropped): "
                     f"{result['invalid_citations']}")
    return "\n".join(lines)
