"""Loaders: parse the three raw dataset formats into uniform source items.

- Docs / blogs: Markdown files with a small `key: value` front-matter block
  (parsed by hand — no YAML dependency).
- Forums: one JSON file holding the thread list.

Each loader returns a list of plain dicts — no classes, no framework.
"""

import json
import re
from pathlib import Path

from . import config

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_front_matter(text: str) -> dict:
    """Parse a `key: value` front-matter block; return {} when absent."""
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}
    meta = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta


def _load_markdown_source(path: Path, source_type: str) -> dict:
    text = path.read_text(encoding="utf-8")
    meta = parse_front_matter(text)
    body = FRONT_MATTER_RE.match(text).group(2).strip()
    # Drop the leading "# Title" line — the title already lives in metadata.
    body = re.sub(r"^#[^\n]*\n+", "", body, count=1)
    return {
        "source_type": source_type,
        "source_id": meta["slug"],
        "title": meta["title"],
        "date": meta["date"],
        "version": meta.get("version"),
        "topics": [t.strip() for t in meta["topics"].split(",") if t.strip()],
        "author": meta.get("author"),  # blogs only
        "path": str(path.relative_to(config.ROOT_DIR)),
        "body": body,
    }


def load_documentation() -> list:
    """Load all official documentation items (Markdown + front matter)."""
    return [_load_markdown_source(p, "documentation")
            for p in sorted(config.DOCS_DIR.glob("*.md"))]


def load_blogs() -> list:
    """Load all blog post items (Markdown + front matter)."""
    return [_load_markdown_source(p, "blog")
            for p in sorted(config.BLOGS_DIR.glob("*.md"))]


def load_forums() -> list:
    """Load all forum threads from the single JSON file."""
    data = json.loads(config.FORUMS_FILE.read_text(encoding="utf-8"))
    items = []
    for thread in data["threads"]:
        items.append({
            "source_type": "forum",
            "source_id": thread["id"],
            "title": thread["title"],
            "date": thread["date"],
            "version": None,
            "topics": thread.get("topics", []),
            "path": str(config.FORUMS_FILE.relative_to(config.ROOT_DIR)),
            "question": thread["question"],
            "answers": thread["answers"],
        })
    return items


def load_all() -> list:
    """All source items across the three source types."""
    return load_documentation() + load_forums() + load_blogs()
