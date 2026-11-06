"""Move the shared locality corpus in and out of MongoDB as a file under version control.

Only the corpus travels: per-locality dossiers and the city-wide percentile stats. Users,
reports, chats and community posts stay in the database they were created in.

Usage:
    python seed.py export       # MongoDB -> seed/corpus.json.gz
    python seed.py import       # seed/corpus.json.gz -> MongoDB (upsert, never deletes)
"""
import asyncio
import gzip
import sys
from pathlib import Path

from bson import json_util

sys.path.insert(0, ".")

from app.db import db  # noqa: E402

SEED_FILE = Path(__file__).resolve().parent / "seed" / "corpus.json.gz"
# collection -> the field that identifies a document across databases
COLLECTIONS = {"dossiers": "locality_slug", "city_stats": "key"}


async def export_corpus():
    corpus = {name: await db[name].find({}, {"_id": 0}).sort(key, 1).to_list(None)
              for name, key in COLLECTIONS.items()}
    SEED_FILE.parent.mkdir(exist_ok=True)
    with gzip.open(SEED_FILE, "wt", encoding="utf-8") as handle:
        handle.write(json_util.dumps(corpus, indent=1))
    for name, docs in corpus.items():
        print(f"{name}: {len(docs)} exported")
    print(f"written to {SEED_FILE} ({SEED_FILE.stat().st_size // 1024} KB)")


async def import_corpus():
    with gzip.open(SEED_FILE, "rt", encoding="utf-8") as handle:
        corpus = json_util.loads(handle.read())
    for name, key in COLLECTIONS.items():
        docs = corpus.get(name, [])
        for doc in docs:
            await db[name].replace_one({key: doc[key]}, doc, upsert=True)
        print(f"{name}: {len(docs)} imported")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command not in ("export", "import"):
        raise SystemExit(__doc__)
    asyncio.run(export_corpus() if command == "export" else import_corpus())
