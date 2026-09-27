"""CloudBox Multi-Source RAG — CLI.

Usage (in the cloudbox-rag env, from the project root):
    python main.py "How much free storage do I get with CloudBox?"
        full grounded pipeline: answer + sources used (Step 4.4)
    python main.py --debug "How much free storage do I get?"
        full pipeline, but prints the end-to-end trace: question -> final
        evidence + conflict status -> conflicts -> answer -> citations
    python main.py --sources documentation "Can I use CloudBox on Linux?"
        restrict the pipeline to one source type (documentation/forum/blog)
    python main.py --debug --weighted "How much free storage do I get?"
    python main.py --debug --rerank "How much free storage do I get?"
    python main.py --debug --resolve "How much free storage do I get?"
        intermediate per-stage views (no LLM call): raw retrieval with
        similarity scores, the Step 3.1 weighted pool, the Step 3.2
        reranked evidence, the Step 3.3 contradiction-aware evidence.

Single-source queries skip the conflict rules (PLAN §5.4).
"""

import argparse
import sys

from src import config, retrieve


def _run_pipeline(args, sources) -> None:
    """Step 4.4: full grounded pipeline — plain run prints answer + sources,
    --debug prints the end-to-end trace."""
    from src import pipeline
    from src.answer import OpenRouterError
    try:
        result = pipeline.answer_question(args.query, sources=sources,
                                          top_k=args.top_k)
    except OpenRouterError as exc:
        print(f"error: {exc}")
        sys.exit(1)
    if args.debug:
        print(pipeline.trace_text(result))
    else:
        print(result["answer"])
        if result["citations"]:
            print("\nSources used:")
            for c in result["citations"]:
                print(f"  [{c['n']}] {c['title']} ({c['source_type']}) — "
                      f"{c['chunk_id']}")


def _print_group(title: str, hits: list[dict]) -> None:
    print(f"\n=== {title} ===")
    if not hits:
        print("  (no results)")
        return
    for rank, h in enumerate(hits, 1):
        print(f"  [{rank}] {h['chunk_id']}   sim={h['similarity']:.4f}")
        print(f"       {h['metadata'].get('title', '(untitled)')}")
        text = h["text"].replace("\n", " ")
        print(f"       {text[:150]}{'...' if len(text) > 150 else ''}")


def _print_weighted_pool(hits: list[dict]) -> None:
    pool = retrieve.weight_candidates(hits)
    print(f"\n=== Weighted candidate pool (Step 3.1) — top {len(pool)} by weighted_score ===")
    for rank, h in enumerate(pool, 1):
        print(f"  [{rank}] {h['chunk_id']}  ({h['source_type']})")
        print(f"       sim={h['similarity']:.4f} × weight={h['weight']} "
              f"= weighted={h['weighted_score']:.4f}")


def _print_reranked(query: str, hits: list[dict], reranker) -> None:
    pool = retrieve.weight_candidates(hits)
    final = reranker.rerank(query, pool)
    print(f"\n=== Reranked final evidence (Step 3.2) — top {len(final)} by rerank_score ===")
    for rank, h in enumerate(final, 1):
        print(f"  [{rank}] {h['chunk_id']}  ({h['source_type']})")
        print(f"       sim={h['similarity']:.4f} × weight={h['weight']} "
              f"= weighted={h['weighted_score']:.4f} | rerank={h['rerank_score']:.4f}")


def _print_resolved(query: str, hits: list[dict], reranker, single_source: bool) -> None:
    from src import conflict  # lazy: only when --resolve is used
    pool = retrieve.weight_candidates(hits)
    evidence = reranker.rerank(query, pool)
    if single_source:
        # PLAN §5.4: single-source modes skip cross-source conflict handling
        result = {"evidence": [dict(h, conflict_status="kept") for h in evidence],
                  "conflicts": []}
    else:
        result = conflict.handle_contradictions(evidence)
    print(f"\n=== Contradiction-aware final evidence (Step 3.3) ===")
    for rank, h in enumerate(result["evidence"], 1):
        detail = ""
        if h["conflict_status"] == "suppressed":
            detail = f"  ({h['suppressed_reason']})"
        elif h["conflict_status"] == "conflict_candidate":
            detail = f"  (authority: {h['authority']})"
        print(f"  [{rank}] {h['chunk_id']}  ({h['source_type']})  "
              f"rerank={h['rerank_score']:.4f}  {h['conflict_status']}{detail}")
    if result["conflicts"]:
        print("  conflicts:")
        for c in result["conflicts"]:
            print(f"    {c['rule']}: {c['chunk_id']} -> winner {c['winner_id']}")
    else:
        print("  conflicts: none")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="technical support question")
    parser.add_argument("--debug", action="store_true",
                        help="print per-source retrieval results with scores")
    parser.add_argument("--weighted", action="store_true",
                        help="with --debug: also apply Step 3.1 source weights "
                             "and show the re-sorted candidate pool")
    parser.add_argument("--rerank", action="store_true",
                        help="with --debug: also run the Step 3.2 CrossEncoder "
                             "reranking and show the final evidence list")
    parser.add_argument("--resolve", action="store_true",
                        help="with --debug: also run the Step 3.3 deterministic "
                             "conflict rules and show status + reasons")
    parser.add_argument("--sources", default=None,
                        help="comma-separated source types "
                             "(documentation,forum,blog); default: all three")
    parser.add_argument("--top-k", type=int, default=None,
                        help="hits per source (default: config.TOP_K_PER_SOURCE)")
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",")] if args.sources else None

    if not args.debug:
        _run_pipeline(args, sources)
        return

    hits = retrieve.retrieve(args.query, sources=sources, top_k=args.top_k)

    shown = sources or config.SOURCE_TYPES
    top_k = args.top_k or config.TOP_K_PER_SOURCE
    print(f"query: {args.query}")
    print(f"sources: {', '.join(shown)} | top_k per source: {top_k}")
    for src in shown:
        _print_group(src.title(),
                     [h for h in hits if h["source_type"] == src])
    print(f"\ntotal candidates: {len(hits)} (sorted by raw similarity, best first)")

    if args.weighted:
        _print_weighted_pool(hits)

    reranker = None
    if args.rerank or args.resolve:
        from src import rerank as rerank_mod  # lazy: load CrossEncoder only when asked
        reranker = rerank_mod.Reranker()

    if args.rerank:
        _print_reranked(args.query, hits, reranker)
    if args.resolve:
        single_source = sources is not None and len(sources) == 1
        _print_resolved(args.query, hits, reranker, single_source)

    # plain --debug (no intermediate flag): the full grounded pipeline,
    # printed as the end-to-end trace (Step 4.4)
    if not (args.weighted or args.rerank or args.resolve):
        _run_pipeline(args, sources)


if __name__ == "__main__":
    main()
