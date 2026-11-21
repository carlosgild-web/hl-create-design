"""Read-only views of what the SSE stream and the trace don't carry (decision 0028).

Runs with the backend's venv and imports the backend's own functions, so what the video
shows is what the code computes, not a copy:

    backend/.venv/Scripts/python video/introspect.py fts "Why was revision I rejected?"
    backend/.venv/Scripts/python video/introspect.py intent "Why was revision I rejected?"

Prints one JSON object. Writes nothing, opens no network connection.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.agent.intent import classify
from app.core.config import MANUAL_DIR
from app.standards.manual_search import KEYWORDS_WEIGHT, ManualIndex, fts_query


def fts(query: str, lang: str, limit: int) -> dict:
    """The words FTS5 gets, and the ranking with the bm25 scores `ManualIndex.search` sorts
    by (same index, same weights). `search` is the method's own answer, to compare."""
    index = ManualIndex(MANUAL_DIR)
    match = fts_query(query)
    rows = index._db.execute(  # the index's in-memory table, read only
        "SELECT source, heading, "
        f"bm25(passages, 0.0, 0.0, 0.0, 3.0, 1.0, {KEYWORDS_WEIGHT}) AS score "
        "FROM passages WHERE passages MATCH ? AND lang = ? ORDER BY score LIMIT ?",
        [match, lang, limit * 2],
    ).fetchall()
    ranked, seen = [], set()
    for source, heading, score in rows:
        if source not in seen:
            seen.add(source)
            ranked.append(
                {"source": source, "heading": heading, "bm25": round(score, 3)}
            )
    return {
        "query": query,
        "terms": match,
        "weights": {"heading": 3.0, "text": 1.0, "keywords": KEYWORDS_WEIGHT},
        "ranked": ranked[:limit],
        "search": [p.source for p in index.search(query, lang, limit)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fts", help="FTS terms and BM25 ranking for a query")
    f.add_argument("query")
    f.add_argument("--lang", default="en")
    f.add_argument("--limit", type=int, default=4)
    i = sub.add_parser("intent", help="the classifier's label for a message")
    i.add_argument("text")
    args = parser.parse_args()
    if args.command == "fts":
        out = fts(args.query, args.lang, args.limit)
    else:
        out = {"text": args.text, "intent": classify(args.text)}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
