"""Source-specific chunking (Step 2.1).

Strategies, one per source type (chosen to match each format's structure):
  - documentation -> section-based: one chunk per `##` section
  - forum         -> thread-based: one chunk per whole Q&A thread
  - blog          -> section/paragraph-based: one chunk per `##` section

Chunks are DERIVED data: the Step 1 dataset files are only read, never
modified. Chunk ids follow the contract in PLAN.md §4 (the evaluation
ground truth in data/eval_queries.json depends on it):
  docs:<file_slug>:<section_slug> · forum:<thread_id> · blog:<file_slug>:<section_slug>
  slug rule: lowercase, spaces -> hyphens, non-alphanumeric stripped.
"""

import re

from . import config
from . import loaders

SOURCE_PREFIX = {"documentation": "docs", "forum": "forum", "blog": "blog"}

SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
PARAGRAPH_RE = re.compile(r"\n\s*\n")


def slugify(text: str) -> str:
    """lowercase; spaces -> hyphens; non-alphanumeric stripped."""
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


def make_chunk_id(source_type: str, source_id: str, section: str | None = None) -> str:
    prefix = SOURCE_PREFIX[source_type]
    if section:
        return f"{prefix}:{source_id}:{slugify(section)}"
    return f"{prefix}:{source_id}"


def _base_metadata(item: dict, section: str | None = None) -> dict:
    """Common metadata block — every chunk stays traceable to its source item."""
    meta = {
        "chunk_id": make_chunk_id(item["source_type"], item["source_id"], section),
        "source_type": item["source_type"],
        "source_id": item["source_id"],
        "title": item["title"],
        "date": item["date"],
        "version": item["version"],
        "topics": item["topics"],
        "path": item["path"],
    }
    if section is not None:
        meta["section"] = section
    return meta


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Split a Markdown body on `##` headings -> [(heading, section_body), ...].

    `###` sub-headings stay inside their section body. Any preamble text
    before the first heading is attached to the first section.
    """
    parts = SECTION_RE.split(body)  # [preamble, h1, body1, h2, body2, ...]
    preamble = parts[0].strip()
    sections = []
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        section_body = parts[i + 1].strip()
        if preamble and not sections:
            section_body = f"{preamble}\n\n{section_body}"
        sections.append((heading, section_body))
    return sections


def _split_long_section(text: str, max_words: int) -> list[str]:
    """Size guard: split an over-long section into paragraph groups that stay
    under max_words each. Short sections pass through untouched."""
    if len(text.split()) <= max_words:
        return [text]
    pieces: list[str] = []
    current: list[str] = []
    count = 0
    for para in (p.strip() for p in PARAGRAPH_RE.split(text)):
        if not para:
            continue
        words = len(para.split())
        if current and count + words > max_words:
            pieces.append("\n\n".join(current))
            current, count = [], 0
        current.append(para)
        count += words
    if current:
        pieces.append("\n\n".join(current))
    return pieces


def _chunk_markdown_sections(items: list, max_words: int) -> list:
    """Shared Markdown path: one chunk per `##` section, heading chain kept in
    the chunk text ("Title → Section"), long sections split by paragraph
    (id suffix -p2, -p3, ...)."""
    chunks = []
    for item in items:
        for heading, body in _split_sections(item["body"]):
            for idx, piece in enumerate(_split_long_section(body, max_words), start=1):
                chunk = _base_metadata(item, section=heading)
                if idx > 1:
                    chunk["chunk_id"] = f"{chunk['chunk_id']}-p{idx}"
                chunk["text"] = f"{item['title']} → {heading}\n\n{piece}"
                chunks.append(chunk)
    return chunks


def chunk_documentation(items: list) -> list:
    """Documentation: split on `##` sections. Size guard: 800 words
    (config.DOC_SECTION_MAX_WORDS), then split by paragraph."""
    return _chunk_markdown_sections(items, config.DOC_SECTION_MAX_WORDS)


def chunk_blogs(items: list) -> list:
    """Blogs: split on `##` sections; long sections fall back to ~200-word
    paragraph chunks (config.BLOG_PARAGRAPH_WORDS)."""
    return _chunk_markdown_sections(items, config.BLOG_PARAGRAPH_WORDS)


def chunk_forums(items: list, max_replies: int = 2) -> list:
    """Forums: one chunk per thread — question + accepted answer + the
    top `max_replies` other answers. Threads are short; never over-split."""
    chunks = []
    for item in items:
        answers = sorted(item["answers"],
                         key=lambda a: a.get("upvotes", 0), reverse=True)
        accepted = next((a for a in answers if a.get("accepted")), None)
        if accepted is None and answers:
            accepted = answers[0]  # fallback: top-voted answer
        others = [a for a in answers if a is not accepted][:max_replies]

        parts = [
            f"Title: {item['title']}",
            f"Question ({item['question']['author']}): {item['question']['body']}",
        ]
        if accepted:
            parts.append(f"Answer ({accepted['author']}, accepted): {accepted['body']}")
        for a in others:
            parts.append(f"Reply ({a['author']}): {a['body']}")

        chunk = _base_metadata(item)
        chunk["text"] = "\n\n".join(parts)
        chunks.append(chunk)
    return chunks


def run() -> list:
    """Full chunking pipeline: load every source, chunk per strategy."""
    return (chunk_documentation(loaders.load_documentation())
            + chunk_forums(loaders.load_forums())
            + chunk_blogs(loaders.load_blogs()))


def _example(chunk: dict, limit: int = 300) -> str:
    text = chunk["text"].replace("\n", " ")
    if len(text) > limit:
        text = text[:limit] + " …"
    return text


if __name__ == "__main__":
    # Standalone verification runner for Step 2.1.
    chunks = run()
    by_type: dict[str, list] = {}
    for c in chunks:
        by_type.setdefault(c["source_type"], []).append(c)

    item_counts = {
        "documentation": len(loaders.load_documentation()),
        "forum": len(loaders.load_forums()),
        "blog": len(loaders.load_blogs()),
    }
    print("Chunking pipeline (Step 2.1)\n")
    print(f"{'source':<15}{'items':>7}{'chunks':>8}")
    total_items = 0
    total_chunks = 0
    for src in ("documentation", "forum", "blog"):
        n_items = item_counts[src]
        n_chunks = len(by_type.get(src, []))
        total_items += n_items
        total_chunks += n_chunks
        print(f"{src:<15}{n_items:>7}{n_chunks:>8}")
    print(f"{'TOTAL':<15}{total_items:>7}{total_chunks:>8}")
    lo, hi = config.TARGET_TOTAL_CHUNKS
    verdict = "OK" if lo <= total_chunks <= hi else "OUT OF RANGE"
    print(f"target {lo}-{hi}: {verdict}\n")

    for src in ("documentation", "forum", "blog"):
        print(f"Examples — {src}:\n")
        for c in by_type[src][:2]:
            print(f"  {c['chunk_id']}")
            print(f"    source_type={c['source_type']} source_id={c['source_id']} "
                  f"title=\"{c['title']}\" date={c['date']} version={c['version']} "
                  f"topics={c['topics']}")
            print(f"    text: {_example(c)}\n")
