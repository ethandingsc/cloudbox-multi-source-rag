"""Ingest pipeline (Step 2.2): load -> chunk -> embed -> upsert into ChromaDB.

Usage (from the project root, in the cloudbox-rag env):
    python scripts/ingest.py            # embed all chunks and upsert (idempotent)
    python scripts/ingest.py --reset    # drop the collection first, then rebuild

Chunk ids are deterministic (PLAN.md §4), so re-running the ingestion never
creates duplicate records — every run re-embeds and upserts the same ids.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import chunkers, config, embed_store  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chunk + embed + index all CloudBox sources into ChromaDB.")
    parser.add_argument("--reset", action="store_true",
                        help="delete the existing collection before ingesting")
    args = parser.parse_args()

    chunks = chunkers.run()
    store = embed_store.EmbedStore()
    if args.reset:
        store.reset()

    store.upsert_chunks(chunks)

    print(f"collection: '{config.CHROMA_COLLECTION}' at {config.CHROMA_DIR}")
    print(f"embedding model: {config.EMBED_MODEL} (dim={store.embedding_dim})")
    print(f"total records: {store.count()}")
    # Pitfall: collection.get() returns a GetResult namedtuple (7 fields), so
    # len(get(...)) is always 7 — index ["ids"] before counting.
    for src in config.SOURCE_TYPES:
        n = len(store.collection.get(where={"source_type": src},
                                     include=[], limit=10_000)["ids"])
        print(f"  {src:<14} {n}")


if __name__ == "__main__":
    main()
