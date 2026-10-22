"""Deterministic contradiction handling for final evidence.

Step 1.6 narrowed the previous blanket age rule. Only community chunks whose
claims were actually audited as obsolete are suppressed. Older but still valid
material remains usable, and an explicit historical-version query may retrieve
the corresponding obsolete source as historical evidence.
"""

import re


OBSOLETE_COMMUNITY_IDS = {
    "forum:thread-001",  # promotional 15 GB vs current standard 10 GB
    "forum:thread-002",  # old 5 GB upload ceiling
    "forum:thread-003",  # organization 2FA described as optional
    "forum:thread-004",  # says no Linux desktop client
    "forum:thread-014",  # says no native Linux desktop client
    "blog:free-storage-explained:what-the-free-plan-includes",
    "blog:free-storage-explained:watching-your-quota",
    "blog:free-storage-explained:when-to-upgrade",
    "blog:upload-limits-explained:the-5-gb-ceiling",
    "blog:upload-limits-explained:workarounds-for-big-files",
    "blog:upload-limits-explained:looking-ahead",
}

VERSION_RE = re.compile(r"(?:cloudbox\s+|version\s+|v)?(\d+)\.(\d+|x)", re.I)


def _topics_of(hit: dict) -> set:
    topics = hit["metadata"].get("topics")
    if isinstance(topics, str):
        return {topic.strip() for topic in topics.split(",") if topic.strip()}
    return set(topics or [])


def _docs_authority(hit: dict, evidence: list[dict]):
    topics = _topics_of(hit)
    if not topics:
        return None
    for other in evidence:
        if (other["source_type"] == "documentation" and
                topics & _topics_of(other)):
            return other["chunk_id"]
    return None


def _canonical_id(hit: dict) -> str:
    return hit["metadata"].get("derived_from") or hit["chunk_id"]


def _explicitly_requests_version(question: str | None,
                                 version: str | None) -> bool:
    if not question or not version:
        return False
    actual_major, actual_minor = version.split(".", 1)
    return any(major == actual_major and (minor == "x" or minor == actual_minor)
               for major, minor in VERSION_RE.findall(question))


def handle_contradictions(evidence: list[dict],
                          question: str | None = None) -> dict:
    """Mark obsolete claims and authority conflicts without mutating input."""
    output = []
    conflicts = []
    for hit in evidence:
        item = dict(hit)
        if item["source_type"] == "documentation":
            item["conflict_status"] = "kept"
            output.append(item)
            continue

        winner = _docs_authority(item, evidence)
        canonical = _canonical_id(item)
        version = item["metadata"].get("version")
        historical_request = _explicitly_requests_version(question, version)

        if canonical in OBSOLETE_COMMUNITY_IDS and not historical_request:
            reason = ("superseded_version" if item["source_type"] == "blog"
                      else "superseded_by_current_docs")
            item["conflict_status"] = "suppressed"
            item["suppressed_reason"] = reason
            conflicts.append({
                "rule": reason,
                "chunk_id": item["chunk_id"],
                "winner_id": winner,
                "note": "audited obsolete community claim; maintained docs win",
            })
            output.append(item)
            continue

        if winner:
            item["conflict_status"] = "conflict_candidate"
            item["authority"] = "community"
            conflicts.append({
                "rule": "conflict_candidate",
                "chunk_id": item["chunk_id"],
                "winner_id": winner,
                "note": ("community chunk shares topics with current "
                         "documentation; docs win if claims conflict"),
            })
        else:
            item["conflict_status"] = "kept"
        output.append(item)

    return {"evidence": output, "conflicts": conflicts}
