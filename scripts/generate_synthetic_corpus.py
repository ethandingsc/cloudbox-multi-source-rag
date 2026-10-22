"""Build 500 local, source-grounded CloudBox support examples.

No network or API key is used. This makes scenario variations of the
original official documentation, not 500 independent product facts.

Usage: python scripts/generate_synthetic_corpus.py
       python scripts/generate_synthetic_corpus.py --validate-only
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import chunkers, config, loaders  # noqa: E402


COUNTS = {"documentation": 100, "forum": 300, "blog": 100}
SUBDIRS = {"documentation": "docs", "forum": "forums", "blog": "blogs"}
DOC_ANGLES = ("Quick reference", "Expected behavior", "Common questions")
BLOG_ANGLES = ("Practical notes", "What to check", "A closer look")
FORUM_QUESTIONS = (
    "I am setting up CloudBox and want to understand {topic}. What does the current documentation say?",
    "I found an older discussion about {topic}. Can someone confirm the current CloudBox behavior?",
    "Before I explain {topic} to my team, what should I verify in the official guide?",
    "I am checking my CloudBox setup. Which documented details matter for {topic}?",
    "Could support clarify {topic} in the current CloudBox version? I want to avoid relying on an outdated post.",
    "I need a short answer about {topic}. What should I expect according to the official documentation?",
    "There seem to be different descriptions of {topic}. What is the maintained CloudBox guidance?",
)
FORUM_TITLE_ANGLES = (
    "Getting started with {section}",
    "Is the guidance on {section} still current?",
    "Clarifying {section} for a team",
    "What to expect from {section}",
    "Conditions to check for {section}",
    "A customer question about {section}",
    "Which guidance applies to {section}?",
)


def anchors() -> list[dict]:
    return chunkers.chunk_documentation(loaders.load_documentation(False))


def assignments(source_type: str, references: list[dict]):
    total = COUNTS[source_type]
    per_anchor, remainder = divmod(total, len(references))
    index = 1
    for ref_number, reference in enumerate(references):
        for variation in range(per_anchor + (ref_number < remainder)):
            yield index, reference, variation
            index += 1


def target_path(source_type: str, index: int) -> Path:
    extension = "json" if source_type == "forum" else "md"
    return (config.GENERATED_DATA_DIR / SUBDIRS[source_type] /
            f"synthetic-{source_type}-{index:03d}.{extension}")


def reference_sentences(reference: dict) -> list[str]:
    body = reference["text"].split("\n\n", 1)[-1]
    body = body.replace("**", "").replace("`", "")
    sentences = [part.strip() for part in
                 re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", body)
                 if part.strip()]
    return sentences or [body.strip()]


def evidence_excerpt(reference: dict, variation: int) -> str:
    sentences = reference_sentences(reference)
    # Rotate the starting point so variants emphasize different sentences,
    # while every factual sentence remains an exact excerpt of the source.
    take = min(len(sentences), max(2, min(4, len(sentences))))
    start = variation % len(sentences)
    chosen = [sentences[(start + offset) % len(sentences)]
              for offset in range(take)]
    return " ".join(chosen)


def context(reference: dict) -> tuple[str, str]:
    title = reference["title"]
    section = reference.get("section") or "product guidance"
    return title, section


def make_article(source_type: str, reference: dict, index: int,
                 variation: int) -> str:
    original_title, section = context(reference)
    topic = section.lower()
    angle = (DOC_ANGLES if source_type == "documentation" else
             BLOG_ANGLES)[variation % 3]
    title = f"{original_title}: {section} — {angle}"
    excerpt = evidence_excerpt(reference, variation)
    if source_type == "documentation":
        body = (f"This CloudBox 2.1 support note focuses on {topic}. "
                f"{excerpt} For the complete explanation and related topics, "
                f"consult the maintained {original_title} documentation. "
                "This note summarizes that source and does not introduce "
                "a separate product policy.")
        heading = "Current documented behavior"
    else:
        body = (f"A practical way to approach {topic} is to start with the "
                f"current {original_title} guide. {excerpt} "
                "When a forum answer or an old screenshot differs, check "
                "the maintained documentation before changing your setup. "
                "This note is a scenario-oriented summary of the same facts.")
        heading = "What the guide says"
    stamp = (date(2024, 7, 1) + timedelta(days=index % 365)).isoformat()
    slug = f"synthetic-{source_type}-{index:03d}"
    front_matter = ("---\n"
                    f"title: {title}\n"
                    f"slug: {slug}\n"
                    f"source_type: {source_type}\n"
                    "version: 2.1\n"
                    f"date: {stamp if source_type == 'blog' else '2024-05-12'}\n"
                    f"topics: {', '.join(reference['topics'])}\n"
                    "synthetic: true\n"
                    f"derived_from: {reference['chunk_id']}\n")
    if source_type == "blog":
        front_matter += "author: CloudBox Editorial\n"
    return (f"{front_matter}---\n\n# {title}\n\n"
            f"## {heading}\n\n{body}\n")


def make_forum(reference: dict, index: int, variation: int) -> dict:
    original_title, section = context(reference)
    topic = section.lower()
    question = FORUM_QUESTIONS[variation % len(FORUM_QUESTIONS)].format(topic=topic)
    excerpt = evidence_excerpt(reference, variation)
    answer = (f"The current {original_title} documentation says: {excerpt} "
              "That official page is the source to follow if a community "
              "reply describes an older version. Check the complete section "
              "there for surrounding conditions before applying it to your case.")
    stamp = (date(2024, 7, 1) + timedelta(days=index % 365)).isoformat()
    return {
        "id": f"synthetic-thread-{index:03d}",
        "title": FORUM_TITLE_ANGLES[variation % len(FORUM_TITLE_ANGLES)].format(
            section=section),
        "date": stamp,
        "topics": reference["topics"],
        "tags": reference["topics"][:2],
        "status": "solved",
        "synthetic": True,
        "derived_from": reference["chunk_id"],
        "question": {"author": f"member_{index:03d}", "body": question},
        "answers": [{"author": "cloudbox_support", "date": stamp,
                     "body": answer, "accepted": True, "upvotes": 3}],
    }


def validate_corpus() -> dict:
    all_items = loaders.load_all()
    generated = [item for item in all_items if item.get("synthetic")]
    counts = Counter(item["source_type"] for item in generated)
    if dict(counts) != COUNTS:
        raise ValueError(f"counts {dict(counts)} != {COUNTS}")
    ids = [(item["source_type"], item["source_id"]) for item in all_items]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate source IDs")
    original_chunk_ids = {chunk["chunk_id"] for chunk in anchors()}
    if any(item["derived_from"] not in original_chunk_ids for item in generated):
        raise ValueError("broken source provenance")
    chunks = chunkers.run()
    chunk_ids = [chunk["chunk_id"] for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("duplicate chunk IDs")
    if len(chunks) != 590:
        raise ValueError(f"expected 590 chunks, got {len(chunks)}")
    if any(not chunk["text"].strip() for chunk in chunks):
        raise ValueError("empty chunk")
    return {"original_items": len(all_items) - len(generated),
            "generated_items": dict(counts),
            "total_items": len(all_items), "total_chunks": len(chunks)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        print(json.dumps(validate_corpus(), indent=2))
        return
    references = anchors()
    for source_type in COUNTS:
        for index, reference, variation in assignments(source_type, references):
            path = target_path(source_type, index)
            path.parent.mkdir(parents=True, exist_ok=True)
            if source_type == "forum":
                content = json.dumps(make_forum(reference, index, variation),
                                     ensure_ascii=False, indent=2) + "\n"
            else:
                content = make_article(source_type, reference, index, variation)
            path.write_text(content, encoding="utf-8")
    summary = validate_corpus()
    manifest = {
        "description": "Locally generated, source-grounded scenario variants; not real customer documents or 500 independent product facts.",
        "generator": "scripts/generate_synthetic_corpus.py",
        "source_of_truth": "original CloudBox documentation chunks",
        **summary,
    }
    (config.GENERATED_DATA_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
