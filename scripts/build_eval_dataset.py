"""Build the 120-case, source-grounded CloudBox evaluation dataset.

The 90 direct cases are derived deterministically from every original
(non-synthetic) chunk: 43 documentation sections, 20 forum threads, and 27
blog sections.  Thirty curated cases exercise multi-source retrieval and the
four known version/content conflicts.  No model or network call is used.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import chunkers, config, loaders  # noqa: E402


def first_sentence(text: str) -> str:
    body = text.split("\n\n", 1)[-1].strip()
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", body, maxsplit=1)
    return parts[0].strip()


def direct_cases() -> list[dict]:
    cases = []
    docs = chunkers.chunk_documentation(loaders.load_documentation(False))
    forums = chunkers.chunk_forums(loaders.load_forums(False))
    blogs = chunkers.chunk_blogs(loaders.load_blogs(False))

    for chunk in docs:
        section = chunk["section"]
        cases.append({
            "category": "direct",
            "query": f"What is the current CloudBox guidance for {section}?",
            "expected_sources": ["documentation"],
            "expected_answer": first_sentence(chunk["text"]),
            "expected_evidence_ids": [chunk["chunk_id"]],
            "conflict_case": None,
        })

    forum_items = {item["source_id"]: item for item in loaders.load_forums(False)}
    for chunk in forums:
        item = forum_items[chunk["source_id"]]
        accepted = next((a for a in item["answers"] if a.get("accepted")),
                        item["answers"][0])
        cases.append({
            "category": "direct",
            "query": item["question"]["body"],
            "expected_sources": ["forum"],
            "expected_answer": accepted["body"],
            "expected_evidence_ids": [chunk["chunk_id"]],
            "conflict_case": None,
        })

    for chunk in blogs:
        cases.append({
            "category": "direct",
            "query": (f"According to the CloudBox blog, what should a user know "
                      f"about {chunk['section']}?"),
            "expected_sources": ["blog"],
            "expected_answer": first_sentence(chunk["text"]),
            "expected_evidence_ids": [chunk["chunk_id"]],
            "conflict_case": None,
        })
    return cases


def curated_cases() -> list[dict]:
    def case(category, query, answer, evidence, sources, conflict=None):
        return {
            "category": category,
            "query": query,
            "expected_sources": sources,
            "expected_answer": answer,
            "expected_evidence_ids": evidence,
            "conflict_case": conflict,
        }

    cases = [
        # Storage conflict: current docs must beat the 5 GB/15 GB claims.
        case("conflict", "Is CloudBox Free storage 5 GB, 10 GB, or 15 GB today?",
             "The current Free plan includes 10 GB; 5 GB was the pre-2.0 limit and 15 GB was a limited promotion.",
             ["docs:storage-limits:free-plan-storage"], ["documentation", "forum", "blog"], "storage"),
        case("conflict", "An old blog says the free plan has 5 GB. What is the maintained limit?",
             "The maintained CloudBox documentation says the current free-plan limit is 10 GB.",
             ["docs:storage-limits:free-plan-storage"], ["documentation", "blog"], "storage"),
        case("conflict", "A forum user claims everyone receives 15 GB free. Is that current policy?",
             "No. The standard current free-plan quota is 10 GB; 15 GB applied only to an old promotion.",
             ["docs:storage-limits:free-plan-storage"], ["documentation", "forum"], "storage"),
        case("conflict", "When did CloudBox raise its standard free quota, and what is it now?",
             "CloudBox raised the standard free quota from 5 GB to 10 GB in version 2.0 in September 2023.",
             ["docs:storage-limits:free-plan-storage"], ["documentation", "blog"], "storage"),

        # Upload-size conflict: old 5 GB material must lose to channel-specific limits.
        case("conflict", "Is CloudBox's single-file upload limit still 5 GB?",
             "No. Desktop, mobile, and API uploads support up to 20 GB; browser uploads are capped at 2 GB.",
             ["docs:storage-limits:maximum-upload-size", "docs:file-sharing:uploading-through-the-web-app"],
             ["documentation", "forum", "blog"], "upload-size"),
        case("conflict", "Which current upload limit replaces the old 5 GB guidance?",
             "The current limit is 20 GB through desktop, mobile, and API, with a separate 2 GB web-app cap.",
             ["docs:storage-limits:maximum-upload-size"], ["documentation", "blog"], "upload-size"),
        case("conflict", "Why does a 2.4 GB browser upload fail when a forum says 5 GB is allowed?",
             "Browser uploads are limited to 2 GB. Use desktop, mobile, or API for files up to 20 GB; the 5 GB claim is outdated.",
             ["docs:file-sharing:uploading-through-the-web-app", "docs:storage-limits:maximum-upload-size"],
             ["documentation", "forum", "blog"], "upload-size"),
        case("conflict", "Can I upload an 8 GB file through the API under current CloudBox limits?",
             "Yes. The API supports resumable uploads up to 20 GB; the 2 GB cap applies only to the web app.",
             ["docs:api:uploading-files-via-the-api", "docs:storage-limits:maximum-upload-size"],
             ["documentation", "forum"], "upload-size"),

        # 2FA conflict.
        case("conflict", "Can an organization administrator disable 2FA in CloudBox 2.1?",
             "No. 2FA is mandatory for all organization accounts in CloudBox 2.1, and administrators cannot disable it.",
             ["docs:security:two-factor-authentication-policy"], ["documentation", "forum", "blog"], "2fa"),
        case("conflict", "A forum post says team 2FA is optional. Which policy is current?",
             "The current policy requires 2FA for every organization account; personal accounts may keep it optional.",
             ["docs:security:two-factor-authentication-policy"], ["documentation", "forum"], "2fa"),
        case("conflict", "What happens if an organization member does not enroll in 2FA after CloudBox 2.1?",
             "They have 14 days to enroll a TOTP app, after which the account is locked until enrollment.",
             ["docs:security:two-factor-authentication-policy"], ["documentation", "blog"], "2fa"),
        case("conflict", "Does SSO replace the 2FA requirement for Business and Enterprise teams?",
             "No. SAML or OIDC SSO can be enabled, but it does not replace mandatory 2FA.",
             ["docs:teams:organization-security-requirements"], ["documentation", "forum", "blog"], "2fa"),

        # Linux conflict.
        case("conflict", "Does CloudBox currently provide an official Linux desktop client?",
             "Yes. It has been available since version 2.0 for Ubuntu 20.04+ and Fedora 36+.",
             ["docs:sync:linux-desktop-client"], ["documentation", "forum", "blog"], "linux"),
        case("conflict", "An older forum says Linux users must use the web app. Is that still true?",
             "No. CloudBox 2.0 introduced an official Linux desktop client with feature parity.",
             ["docs:sync:linux-desktop-client"], ["documentation", "forum"], "linux"),
        case("conflict", "Which Linux distributions and package formats does CloudBox support?",
             "Ubuntu 20.04 LTS or newer and Fedora 36 or newer are supported, with .deb packages and AppImages.",
             ["docs:sync:linux-desktop-client", "blog:linux-client-arrives:supported-distributions"],
             ["documentation", "blog"], "linux"),
        case("conflict", "Does the Linux desktop client support selective sync and bandwidth throttling?",
             "Yes. The current Linux client includes selective sync and bandwidth throttling like Windows and macOS.",
             ["docs:sync:linux-desktop-client", "blog:linux-client-arrives:the-long-wait-is-over"],
             ["documentation", "blog", "forum"], "linux"),

        # Multi-source synthesis.
        case("multi_source", "What limits should a free-plan nightly API backup handle?",
             "API uploads can be resumable up to 20 GB, requests are limited to 1000 per hour per token with 429/Retry-After handling, and free plans have 200 GB daily transfer.",
             ["docs:api:uploading-files-via-the-api", "docs:api:rate-limits", "docs:storage-limits:transfer-and-bandwidth-limits", "forum:thread-011"],
             ["documentation", "forum"]),
        case("multi_source", "After downgrading while over quota, what can clients do through existing shared links?",
             "For 90 days they can view and download but cannot upload; after 90 days the over-quota files enter the recycle bin and the links expire.",
             ["docs:billing:downgrading-your-plan", "forum:thread-016"], ["documentation", "forum"]),
        case("multi_source", "How can I share a folder with an external editor and protect the link?",
             "Create an Edit link for the external user, who need not have an account, and optionally set a password and expiration date; their uploads count against the owner's quota.",
             ["docs:file-sharing:sharing-files-and-folders", "docs:file-sharing:link-permissions-and-expiry", "docs:file-sharing:external-users", "forum:thread-017"],
             ["documentation", "forum"]),
        case("multi_source", "Can a deleted file from 45 days ago be recovered, and when is recovery impossible?",
             "It is outside the 30-day Free window but inside the 90-day paid window unless the bin was emptied; purged or emptied items cannot be recovered even by support.",
             ["docs:recycle-bin:retention-periods-by-plan", "docs:recycle-bin:permanent-deletion", "forum:thread-006", "forum:thread-019"],
             ["documentation", "forum"]),
        case("multi_source", "How do I save laptop disk space with selective sync, and what limitations remain?",
             "Use Preferences > Sync > Selective Sync and uncheck folders. They stay cloud-only, still count toward storage quota, settings are per device, and mobile does not support selective sync.",
             ["docs:selective-sync:setting-up-selective-sync", "docs:selective-sync:limitations-and-best-practices", "blog:selective-sync-tutorial:step-by-step-setup"],
             ["documentation", "blog"]),
        case("multi_source", "How are CloudBox files encrypted, and is the service zero-knowledge?",
             "Files use AES-256 at rest and TLS 1.3 in transit. CloudBox manages the keys, so the service is not zero-knowledge.",
             ["docs:security:encryption-at-rest-and-in-transit", "blog:encryption-deep-dive:aes-256-at-rest", "blog:encryption-deep-dive:key-management"],
             ["documentation", "blog"]),
        case("multi_source", "Why can I upload a 3 GB video but not preview it in the browser?",
             "Upload and preview limits differ: non-web clients can upload the file, but browser preview/streaming is capped at 500 MB, so a 3 GB file must be downloaded.",
             ["docs:file-sharing:preview-and-streaming-limits", "forum:thread-010", "blog:preview-and-streaming-limits:current-preview-limits"],
             ["documentation", "forum", "blog"]),
        case("multi_source", "Summarize the current organization 2FA rollout and personal-account exception.",
             "Organization accounts must use 2FA in version 2.1 and receive a 14-day TOTP enrollment window; personal accounts may leave 2FA optional.",
             ["docs:security:two-factor-authentication-policy", "blog:whats-new-21:mandatory-2fa-for-organizations"],
             ["documentation", "blog"]),
        case("multi_source", "What Linux options exist for desktops and headless servers?",
             "Desktops have an official Linux client for Ubuntu 20.04+ and Fedora 36+; headless servers can use the CLI for resumable manual transfers up to 20 GB, but it has no background sync.",
             ["docs:sync:linux-desktop-client", "blog:linux-client-arrives:what-about-headless-servers"],
             ["documentation", "blog"]),
        case("multi_source", "Do version history and deleted items count against quota, and how long are they retained?",
             "Neither file versions nor recycle-bin contents count toward quota. Version history lasts 30 days on Free and 180 days on paid plans; deleted items last 30 days on Free and 90 days on paid plans.",
             ["docs:storage-limits:version-history-quota-rules", "docs:recycle-bin:retention-periods-by-plan", "forum:thread-008"],
             ["documentation", "forum"]),
        case("multi_source", "Give the full troubleshooting sequence for a client stuck on Syncing on a corporate network.",
             "Pause and resume, check proxy/firewall and port 443, clear the local cache, restart, then collect logs and open a support ticket; TLS inspection may require an exception.",
             ["docs:sync:troubleshooting-sync-issues", "docs:desktop-client:proxy-and-firewall-support", "forum:thread-005"],
             ["documentation", "forum"]),
        case("multi_source", "What must a new organization user do to create and secure a CloudBox account?",
             "Use a password of at least 12 characters, verify the email address, and enroll in mandatory organization 2FA; the TOTP enrollment window is 14 days.",
             ["docs:getting-started:creating-an-account", "docs:security:password-and-account-rules", "docs:security:two-factor-authentication-policy"],
             ["documentation"]),
        case("multi_source", "How do offline mobile files and camera uploads affect device space and CloudBox quota?",
             "Available-offline items keep a device copy and sync over Wi-Fi by default; camera uploads preserve original quality and count against CloudBox storage, while uploads require enough device free space.",
             ["docs:mobile:offline-access-and-camera-upload", "docs:mobile:mobile-limitations"],
             ["documentation"]),
        case("multi_source", "How should an organization structure team-folder ownership, roles, and access?",
             "Team folders are organization-owned; admins manage membership, billing, and security, members receive permission-based access, guests are limited to specific folders, and access should be granted to members or groups per folder.",
             ["docs:teams:team-accounts-and-roles", "docs:teams:shared-team-folders", "blog:team-folder-structure:a-structure-that-scales"],
             ["documentation", "blog"]),
    ]
    if len(cases) != 30:
        raise AssertionError(f"expected 30 curated cases, got {len(cases)}")
    return cases


def apply_alignment_audit(queries: list[dict]) -> None:
    """Apply traceable Step 1.6 corrections after stable IDs exist."""
    by_id = {query["id"]: query for query in queries}
    for query in queries:
        groups = [[chunk_id] for chunk_id in query["expected_evidence_ids"]]
        query["raw_evidence_groups"] = groups
        query["final_evidence_groups"] = groups

    corrections = {
        "q046": {
            "category": "conflict",
            "query": "A forum user says an organization admin can disable 2FA. Is that possible under current CloudBox 2.1 policy?",
            "answer": "No. CloudBox 2.1 requires two-factor authentication for organization members, and administrators cannot disable it.",
            "groups": [["docs:security:two-factor-authentication-policy"]],
            "reason": "The generated direct case treated an obsolete forum claim as truth; current-policy intent requires the maintained 2FA policy.",
        },
        "q044": {
            "query": "Under current CloudBox policy, how much standard free storage does an account receive?",
            "answer": "The current standard CloudBox Free plan includes 10 GB of storage.",
            "groups": [["docs:storage-limits:free-plan-storage"]],
            "reason": "The old forum's 15 GB claim was a limited promotion, not current policy.",
        },
        "q045": {
            "query": "Under current CloudBox limits, what is the largest single file I can upload through each channel?",
            "answer": "Desktop, mobile, and API uploads support up to 20 GB per file; browser uploads are capped at 2 GB.",
            "groups": [["docs:storage-limits:maximum-upload-size"]],
            "reason": "The forum's universal 5 GB ceiling is superseded by current channel-specific limits.",
        },
        "q047": {
            "query": "Under current CloudBox 2.1 guidance, is there an official Linux desktop client?",
            "answer": "Yes. CloudBox has provided an official Linux desktop client since version 2.0 for Ubuntu 20.04+ and Fedora 36+.",
            "groups": [["docs:sync:linux-desktop-client"]],
            "reason": "The forum answer predates the official Linux client.",
        },
        "q050": {
            "groups": [["forum:thread-007", "docs:file-sharing:uploading-through-the-web-app", "docs:storage-limits:maximum-upload-size"]],
            "reason": "The forum answer remains correct; maintained documentation is equivalent evidence.",
        },
        "q051": {
            "groups": [["forum:thread-008", "docs:storage-limits:version-history-quota-rules"]],
            "reason": "The dated forum answer and current documentation agree that versions do not consume quota.",
        },
        "q052": {
            "groups": [["forum:thread-009", "docs:sync:local-cache-and-disk-usage"]],
            "reason": "The local-cache explanation remains valid and has a maintained documentation equivalent.",
        },
        "q053": {
            "groups": [["forum:thread-010", "docs:file-sharing:preview-and-streaming-limits", "blog:preview-and-streaming-limits:current-preview-limits"]],
            "reason": "All listed sources support the same 500 MB preview limit.",
        },
        "q054": {
            "groups": [
                ["forum:thread-011", "docs:api:uploading-files-via-the-api", "docs:storage-limits:maximum-upload-size"],
                ["forum:thread-011", "docs:api:rate-limits"],
            ],
            "reason": "The question requires both upload-size and rate-limit evidence; the forum or maintained API pages support them.",
        },
        "q057": {
            "query": "Does current CloudBox provide a native Linux desktop client, distinct from its Chromebook web or Android access?",
            "answer": "Yes. CloudBox provides a native Linux desktop client; Chromebook web or Android access is a separate client path.",
            "groups": [["docs:sync:linux-desktop-client"]],
            "reason": "The original forum conclusion that no native Linux client exists is obsolete.",
        },
        "q058": {
            "groups": [["forum:thread-015", "blog:linux-client-arrives:what-about-headless-servers"]],
            "reason": "No newer source contradicts the NAS/CLI guidance; age alone does not invalidate it.",
        },
        "q060": {
            "groups": [
                ["forum:thread-017", "docs:file-sharing:sharing-files-and-folders"],
                ["forum:thread-017", "docs:file-sharing:external-users"],
            ],
            "reason": "Permission levels and external-account behavior are two required facts with equivalent forum/doc evidence.",
        },
        "q061": {
            "groups": [
                ["forum:thread-018", "docs:security:encryption-at-rest-and-in-transit", "blog:encryption-deep-dive:aes-256-at-rest"],
                ["forum:thread-018", "docs:security:encryption-at-rest-and-in-transit", "blog:encryption-deep-dive:key-management"],
            ],
            "reason": "Encryption and non-zero-knowledge claims remain valid across equivalent sources.",
        },
    }

    historical_versions = {
        "q068": "1.0", "q069": "1.0", "q070": "1.0",
        "q071": "2.0", "q072": "2.0", "q073": "2.0",
        "q074": "2.0", "q075": "2.0", "q076": "2.0",
        "q084": "1.x", "q085": "1.x", "q086": "1.x",
    }
    for query_id, version in historical_versions.items():
        query = by_id[query_id]
        corrections[query_id] = {
            "query": query["query"].replace(
                "According to the CloudBox blog",
                f"According to the historical CloudBox {version} blog"),
            "groups": [[query["expected_evidence_ids"][0]]],
            "reason": ("The question explicitly requests a historical version; "
                       "that version's source is valid historical evidence."),
        }

    for query_id, correction in corrections.items():
        query = by_id[query_id]
        original = {
            "category": query["category"],
            "query": query["query"],
            "expected_sources": list(query["expected_sources"]),
            "expected_answer": query["expected_answer"],
            "expected_evidence_ids": list(query["expected_evidence_ids"]),
        }
        query["category"] = correction.get("category", query["category"])
        query["query"] = correction.get("query", query["query"])
        query["expected_answer"] = correction.get("answer", query["expected_answer"])
        groups = correction["groups"]
        query["raw_evidence_groups"] = groups
        query["final_evidence_groups"] = groups
        query["expected_evidence_ids"] = list(dict.fromkeys(
            chunk_id for group in groups for chunk_id in group))
        source_names = {
            "docs": "documentation",
            "forum": "forum",
            "blog": "blog",
        }
        query["expected_sources"] = list(dict.fromkeys(
            source_names[chunk_id.split(":", 1)[0]]
            for chunk_id in query["expected_evidence_ids"]
        ))
        query["alignment_audit"] = {
            "original": original,
            "reason": correction["reason"],
            "changed_category": query["category"] != original["category"],
            "changed_query": query["query"] != original["query"],
            "changed_evidence": (query["expected_evidence_ids"] !=
                                 original["expected_evidence_ids"]),
        }


def build() -> dict:
    queries = direct_cases() + curated_cases()
    for index, query in enumerate(queries, 1):
        query["id"] = f"q{index:03d}"
    apply_alignment_audit(queries)
    counts = Counter(q["category"] for q in queries)
    return {
        "_meta": {
            "description": "120 source-grounded evaluation queries for the 540-item / 590-chunk CloudBox knowledge base.",
            "generated_by": "scripts/build_eval_dataset.py",
            "answer_ground_truth": "Every expected answer is copied from or manually synthesized from the listed evidence IDs.",
            "evidence_equivalence": "A retrieved synthetic chunk is relevant when its derived_from value equals an expected evidence ID.",
            "alignment_audit": "The 24 known cases plus one additional invalid direct case retain their originals under alignment_audit and define raw/final evidence groups.",
            "counts": dict(counts),
        },
        "queries": queries,
    }


def main() -> None:
    data = build()
    config.EVAL_QUERIES_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"queries": len(data["queries"]),
                      "categories": data["_meta"]["counts"]}, indent=2))


if __name__ == "__main__":
    main()
