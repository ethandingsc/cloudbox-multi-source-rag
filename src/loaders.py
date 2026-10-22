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
    item = {
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
    if meta.get("synthetic") == "true":
        item["synthetic"] = True
        item["derived_from"] = meta["derived_from"]
    return item


def load_documentation(include_generated: bool = True) -> list:
    """Load all official documentation items (Markdown + front matter)."""
    paths = sorted(config.DOCS_DIR.glob("*.md"))
    if include_generated:
        paths += sorted((config.GENERATED_DATA_DIR / "docs").glob("*.md"))
    return [_load_markdown_source(p, "documentation") for p in paths]


def load_blogs(include_generated: bool = True) -> list:
    """Load all blog post items (Markdown + front matter)."""
    paths = sorted(config.BLOGS_DIR.glob("*.md"))
    if include_generated:
        paths += sorted((config.GENERATED_DATA_DIR / "blogs").glob("*.md"))
    return [_load_markdown_source(p, "blog") for p in paths]


def load_forums(include_generated: bool = True) -> list:
    """Load all forum threads from the single JSON file."""
    data = json.loads(config.FORUMS_FILE.read_text(encoding="utf-8"))
    items = []
    thread_paths = [(thread, config.FORUMS_FILE)
                    for thread in data["threads"]]
    if include_generated:
        for path in sorted((config.GENERATED_DATA_DIR / "forums").glob("*.json")):
            thread_paths.append((json.loads(path.read_text(encoding="utf-8")), path))
    for thread, path in thread_paths:
        item = {
            "source_type": "forum",
            "source_id": thread["id"],
            "title": thread["title"],
            "date": thread["date"],
            "version": None,
            "topics": thread.get("topics", []),
            "path": str(path.relative_to(config.ROOT_DIR)),
            "question": thread["question"],
            "answers": thread["answers"],
        }
        if thread.get("synthetic"):
            item["synthetic"] = True
            item["derived_from"] = thread["derived_from"]
        items.append(item)
    return items


def load_all() -> list:
    """All source items across the three source types."""
    return load_documentation() + load_forums() + load_blogs()
