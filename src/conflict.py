"""Deterministic contradiction handling (Step 3.3) — no LLM involved.

Input: the Step 3.2 reranked final evidence (hits whose metadata carries
topics, version, date, source_type). Detection groups evidence by shared
`topics` tags; resolution applies fixed, pre-declared rules in priority
order (PLAN.md §3.3):

  1. Blogs with `version < CURRENT_VERSION` -> suppressed
     (reason `superseded_version`).
  2. Forums with `date < CURRENT_VERSION_RELEASE_DATE` -> suppressed
     (reason `superseded_by_current_docs`).
  3. Documentation is never suppressed — it is the maintained source
     of truth.
  4. Kept community chunks that share a topic group with a documentation
     chunk are flagged `conflict_candidate` with `authority: community`;
     the Step 4 prompt pre-declares that official documentation wins.

Every suppressed/flagged chunk is also recorded in the returned
`conflicts` list (rule + affected id + winner id). The LLM never decides
which conflicting source is correct — the rule is applied before any
prompting.

Pure function: returns NEW hit dicts (input evidence untouched), keeps
the rerank order of kept chunks, and is deterministic by construction
(constant metadata + constant rules).
"""

from . import config


def _topics_of(hit: dict) -> set:
    topics = hit["metadata"].get("topics")
    if isinstance(topics, str):  # tolerate stringified topics from raw Chroma reads
        return {t.strip() for t in topics.split(",") if t.strip()}
    return set(topics or [])


def _docs_authority(hit: dict, evidence: list[dict]):
    """Documentation chunk in the evidence sharing >=1 topic with `hit`."""
    topics = _topics_of(hit)
    if not topics:
        return None
    for other in evidence:
        if other["source_type"] == "documentation" and (topics & _topics_of(other)):
            return other["chunk_id"]
    return None


def handle_contradictions(evidence: list[dict]) -> dict:
    """Apply the deterministic conflict rules to reranked evidence.

    Returns {"evidence": [...], "conflicts": [...]}. Each evidence entry
    is a new dict carrying the unchanged scores/metadata plus a
    `conflict_status` ("kept" | "suppressed" | "conflict_candidate") and,
    when applicable, `suppressed_reason` or `authority`. Suppressed chunks
    stay in the list (marked) so logging can explain the decision; the
    answer stage consumes only non-suppressed entries.
    """
    out = []
    conflicts = []
    for hit in evidence:
        h = dict(hit)
        if h["source_type"] == "documentation":
            # Rule 3: documentation is never suppressed.
            h["conflict_status"] = "kept"
            out.append(h)
            continue

        winner = _docs_authority(hit, evidence)

        # Rule 1: blogs covering a version older than the current release
        # are superseded — their numbers/features may have changed.
        if h["source_type"] == "blog":
            version = h["metadata"].get("version")
            if version and version < config.CURRENT_VERSION:
                h["conflict_status"] = "suppressed"
                h["suppressed_reason"] = "superseded_version"
                conflicts.append({
                    "rule": "superseded_version",
                    "chunk_id": h["chunk_id"],
                    "winner_id": winner,
                    "note": (f"blog covers v{version}; current docs are "
                             f"v{config.CURRENT_VERSION}"),
                })
                out.append(h)
                continue

        # Rule 2: forums predating the current docs release may describe
        # behavior that has since changed — the docs supersede them.
        if h["source_type"] == "forum":
            date = h["metadata"].get("date", "")
            if date < config.CURRENT_VERSION_RELEASE_DATE:
                h["conflict_status"] = "suppressed"
                h["suppressed_reason"] = "superseded_by_current_docs"
                conflicts.append({
                    "rule": "superseded_by_current_docs",
                    "chunk_id": h["chunk_id"],
                    "winner_id": winner,
                    "note": (f"forum dated {date}, before the current docs "
                             f"release {config.CURRENT_VERSION_RELEASE_DATE}"),
                })
                out.append(h)
                continue

        # Rule 4: a kept community chunk sharing topics with current
        # documentation is flagged, not suppressed — the answer prompt
        # pre-declares docs win over it.
        if winner:
            h["conflict_status"] = "conflict_candidate"
            h["authority"] = "community"
            conflicts.append({
                "rule": "conflict_candidate",
                "chunk_id": h["chunk_id"],
                "winner_id": winner,
                "note": "community chunk shares topics with current "
                        "documentation; docs win by pre-declared rule",
            })
        else:
            h["conflict_status"] = "kept"
        out.append(h)

    return {"evidence": out, "conflicts": conflicts}
