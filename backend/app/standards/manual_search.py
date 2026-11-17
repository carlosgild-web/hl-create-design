"""Keyword search over the Design Manual with SQLite FTS5 (decision 0005).

`docs/manual/{es,en}/NN-topic.md` is split into one passage per `##` section. Each
section carries an explicit anchor (`<a id="skipped-letters"></a>`), the same in both
languages, so a passage has a stable source id such as `02-revisions#skipped-letters`:
the id the validators put in their errors and the assistant cites.

The index lives in memory and is built once per process (a few dozen passages).
"""

from __future__ import annotations

import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

LANGUAGES = ("en", "es")
MAX_TEXT_CHARS = 900

_ANCHOR_RE = re.compile(r'^<a id="([a-z0-9-]+)"></a>\s*$')
_WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class Passage:
    source: str  # "02-revisions#skipped-letters"
    lang: str
    document: str  # "02 · Revisions"
    heading: str  # "Skipped letters"
    text: str

    def to_dict(self, max_chars: int = MAX_TEXT_CHARS) -> dict[str, str]:
        text = self.text if len(self.text) <= max_chars else self.text[:max_chars] + " …"
        return {"source": self.source, "lang": self.lang, "heading": self.heading, "text": text}


def parse_manual_file(path: Path, lang: str) -> list[Passage]:
    """The `##` sections of one manual file that have an anchor."""
    stem = path.stem
    document = stem
    passages: list[Passage] = []
    heading: str | None = None
    anchor: str | None = None
    body: list[str] = []

    def flush() -> None:
        if heading and anchor:
            text = "\n".join(body).strip()
            passages.append(Passage(f"{stem}#{anchor}", lang, document, heading, text))

    for line in path.read_text(encoding="utf-8").splitlines():
        anchor_match = _ANCHOR_RE.match(line)
        if line.startswith("# ") and heading is None:
            document = line[2:].strip()
        elif line.startswith("## "):
            flush()
            heading, anchor, body = line[3:].strip(), None, []
        elif heading is not None and anchor is None and anchor_match:
            anchor = anchor_match.group(1)
        elif heading is not None:
            body.append(line)
    flush()
    return passages


def fts_query(text: str) -> str:
    """Free text -> an FTS5 query that can't be a syntax error: quoted words joined by OR."""
    words = [w for w in _WORD_RE.findall(text.lower()) if len(w) > 1]
    return " OR ".join(f'"{w}"' for w in dict.fromkeys(words))


class ManualIndex:
    def __init__(self, manual_dir: Path) -> None:
        self._lock = threading.Lock()
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.execute(
            "CREATE VIRTUAL TABLE passages USING fts5("
            "source UNINDEXED, lang UNINDEXED, document UNINDEXED, heading, text, "
            "tokenize = 'porter unicode61 remove_diacritics 2')"
        )
        self.passages: list[Passage] = []
        for lang in LANGUAGES:
            for path in sorted((manual_dir / lang).glob("*.md")):
                self.passages.extend(parse_manual_file(path, lang))
        self._db.executemany(
            "INSERT INTO passages VALUES (?, ?, ?, ?, ?)",
            [(p.source, p.lang, p.document, p.heading, p.text) for p in self.passages],
        )
        self._by_key = {(p.source, p.lang): p for p in self.passages}

    def search(self, query: str, lang: str | None = None, limit: int = 4) -> list[Passage]:
        """Best passages first (bm25, headings weigh more). Without `lang`, each source
        appears once, in whichever language matched best."""
        match = fts_query(query)
        if not match:
            return []
        sql = "SELECT source, lang FROM passages WHERE passages MATCH ?"
        params: list[object] = [match]
        if lang in LANGUAGES:
            sql += " AND lang = ?"
            params.append(lang)
        # One weight per column: source, lang, document (not indexed), heading, text.
        sql += " ORDER BY bm25(passages, 0.0, 0.0, 0.0, 3.0, 1.0) LIMIT ?"
        params.append(limit * 2)
        with self._lock:
            rows = self._db.execute(sql, params).fetchall()
        found: list[Passage] = []
        seen: set[str] = set()
        for source, row_lang in rows:
            if source in seen:
                continue
            seen.add(source)
            found.append(self._by_key[(source, row_lang)])
            if len(found) == limit:
                break
        return found

    def get(self, source: str, lang: str = "en") -> Passage | None:
        return self._by_key.get((source, lang))
