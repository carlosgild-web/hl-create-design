"""Every user question in the FAQ bank finds a manual section that answers it (decision 0021).

The bank (`app/evals/faq_questions.json`) holds the 54 questions of `docs/qa/` in English and
Spanish, each with two paraphrases (informal wording, a typo, Mexican Spanish). A question
counts as found when one of its `accepted_refs` is in the top 3 of `ManualIndex.search` in
its own language. Run with `-s` to see the score table and the misses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from app.core.config import REPO_ROOT

BANK_PATH = REPO_ROOT / "backend" / "app" / "evals" / "faq_questions.json"
TOP_K = 3
TARGET = 0.95


@dataclass(frozen=True)
class Case:
    id: str
    lang: str
    kind: str  # "question" | "paraphrase"
    text: str
    accepted: frozenset[str]


def load_cases() -> list[Case]:
    cases: list[Case] = []
    for entry in json.loads(BANK_PATH.read_text(encoding="utf-8")):
        accepted = frozenset(entry["accepted_refs"])
        cases.append(Case(entry["id"], entry["lang"], "question", entry["question"], accepted))
        for n, text in enumerate(entry["paraphrases"], 1):
            cases.append(Case(f"{entry['id']}.p{n}", entry["lang"], "paraphrase", text, accepted))
    return cases


CASES = load_cases()


def test_the_bank_covers_both_languages_with_paraphrases():
    entries = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    for lang in ("en", "es"):
        mine = [e for e in entries if e["lang"] == lang]
        assert len(mine) == 54
        assert all(len(e["paraphrases"]) >= 2 and e["accepted_refs"] for e in mine)


def test_every_accepted_ref_is_a_manual_section(manual):
    known = {p.source for p in manual.passages}
    missing = {ref for case in CASES for ref in case.accepted} - known
    assert not missing, sorted(missing)


@pytest.mark.parametrize("lang", ["en", "es"])
@pytest.mark.parametrize("kind", ["question", "paraphrase"])
def test_top3_retrieval_meets_the_target(manual, lang, kind):
    cases = [c for c in CASES if c.lang == lang and c.kind == kind]
    misses: list[tuple[Case, list[str]]] = []
    for case in cases:
        found = [p.source for p in manual.search(case.text, lang=lang, limit=TOP_K)]
        if not case.accepted & set(found):
            misses.append((case, found))
    hits = len(cases) - len(misses)
    lines = [f"\n{lang} {kind:<10} top-{TOP_K}: {hits}/{len(cases)} ({hits / len(cases):.0%})"]
    for case, found in misses:
        lines.append(f"  miss {case.id}: {case.text!r} -> {found} (want {sorted(case.accepted)})")
    report = "\n".join(lines)
    try:
        print(report)
    except UnicodeEncodeError:  # a Windows console without UTF-8
        print(report.encode("ascii", "backslashreplace").decode("ascii"))
    assert hits / len(cases) >= TARGET
