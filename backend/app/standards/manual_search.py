"""Keyword search over the Design Manual with SQLite FTS5 (decision 0005).

`docs/manual/{es,en}/NN-topic.md` is split into one passage per `##` section. Each
section carries an explicit anchor (`<a id="skipped-letters"></a>`), the same in both
languages, so a passage has a stable source id such as `02-revisions#skipped-letters`:
the id the validators put in their errors and the assistant cites.

A section may end with a `Keywords:` (EN) or `Palabras clave:` (ES) line of synonyms in
both languages (decision 0021). It is indexed in its own column, so users' words find the
section, but it is not part of the passage text the model reads.

The index lives in memory and is built once per process (a few dozen passages).
"""

from __future__ import annotations

import re
import sqlite3
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path

LANGUAGES = ("en", "es")
MAX_TEXT_CHARS = 900
KEYWORDS_WEIGHT = 2.0  # bm25 weight of the `Keywords:` column (heading 3.0, text 1.0)

_ANCHOR_RE = re.compile(r'^<a id="([a-z0-9-]+)"></a>\s*$')
_WORD_RE = re.compile(r"\w+", re.UNICODE)
_KEYWORDS_RE = re.compile(r"^(?:Keywords|Palabras clave):\s*(.*)$")

# Question and function words that every passage shares (decision 0021). Compared without
# accents. Words that change a rule's meaning stay searchable: no, not, new, nuevo, rev, sap.
_STOPWORDS = frozenset(
    """
    a about after again all also am an and any are as at be been before but by can could
    did do does doing for from get got had has have here how i if in into is it its just
    me might my of on only or our should so some than that the their them then there these
    they this those to up us was we were what when where which who whom whose why will with
    would you your
    al algo algun alguna como con cual cuales cuando de del donde el ella ellos en es esa
    ese eso esta estan este esto estos hay hace hacer hago la las le les lo los me mi mis
    muy nomas o para pero por porque puede pueden puedo que quien quienes se ser si sin
    sobre son su sus te tengo tiene tienen tu tus un una unas uno unos y ya yo
    """.split()  # noqa: SIM905 - one word list per language is easier to edit as text
)


@dataclass(frozen=True)
class Passage:
    source: str  # "02-revisions#skipped-letters"
    lang: str
    document: str  # "02 · Revisions"
    heading: str  # "Skipped letters"
    text: str
    keywords: str = ""  # indexed for search only; never shown to the model

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
    keywords: list[str] = []

    def flush() -> None:
        if heading and anchor:
            text = "\n".join(body).strip()
            passages.append(
                Passage(f"{stem}#{anchor}", lang, document, heading, text, " ".join(keywords))
            )

    for line in path.read_text(encoding="utf-8").splitlines():
        anchor_match = _ANCHOR_RE.match(line)
        if line.startswith("# ") and heading is None:
            document = line[2:].strip()
        elif line.startswith("## "):
            flush()
            heading, anchor, body, keywords = line[3:].strip(), None, [], []
        elif heading is not None and anchor is None and anchor_match:
            anchor = anchor_match.group(1)
        elif heading is not None and (keywords_match := _KEYWORDS_RE.match(line)):
            keywords.append(keywords_match.group(1).strip())
        elif heading is not None:
            body.append(line)
    flush()
    return passages


# Dashes a model may write inside a citation instead of "-" (Groq's gpt-oss writes U+2011).
_DASHES = dict.fromkeys(map(ord, "‐‑‒–—−﹣－"), "-")
_SPACED_REF_RE = re.compile(r"\[\s*([\w-]+)\s*#\s*([\w-]+)\s*\]")


def normalize_refs(text: str) -> str:
    """Citations as the manual writes them: NFKC, every dash as "-", no spaces inside the
    brackets. `[02‑revisions#skipped‑letters]` -> `[02-revisions#skipped-letters]`. Used by
    the eval checker; the chat renderer gets the same rule (decision 0024)."""
    text = unicodedata.normalize("NFKC", text).translate(_DASHES)
    return _SPACED_REF_RE.sub(r"[\1#\2]", text)


def _plain(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", word) if not unicodedata.combining(c))


def fts_query(text: str) -> str:
    """Free text -> an FTS5 query that can't be a syntax error: quoted words joined by OR.
    Stopwords are dropped, unless nothing else is left."""
    words = [w for w in _WORD_RE.findall(text.lower()) if len(w) > 1]
    content = [w for w in words if _plain(w) not in _STOPWORDS]
    return " OR ".join(f'"{w}"' for w in dict.fromkeys(content or words))


class ManualIndex:
    def __init__(self, manual_dir: Path) -> None:
        self._lock = threading.Lock()
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.execute(
            "CREATE VIRTUAL TABLE passages USING fts5("
            "source UNINDEXED, lang UNINDEXED, document UNINDEXED, heading, text, keywords, "
            "tokenize = 'porter unicode61 remove_diacritics 2')"
        )
        self.passages: list[Passage] = []
        for lang in LANGUAGES:
            for path in sorted((manual_dir / lang).glob("*.md")):
                self.passages.extend(parse_manual_file(path, lang))
        self._db.executemany(
            "INSERT INTO passages VALUES (?, ?, ?, ?, ?, ?)",
            [(p.source, p.lang, p.document, p.heading, p.text, p.keywords) for p in self.passages],
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
        # One weight per column: source, lang, document (not indexed), heading, text, keywords.
        sql += f" ORDER BY bm25(passages, 0.0, 0.0, 0.0, 3.0, 1.0, {KEYWORDS_WEIGHT}) LIMIT ?"
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
