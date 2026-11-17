"""The FTS5 index of the Design Manual."""

import re

from app.core.config import REPO_ROOT
from app.standards.manual_search import fts_query


def test_every_section_of_both_languages_is_indexed(manual):
    en = {p.source for p in manual.passages if p.lang == "en"}
    es = {p.source for p in manual.passages if p.lang == "es"}
    assert en == es
    assert "02-revisions#skipped-letters" in en


def test_every_reference_the_validators_cite_exists(manual):
    code = (REPO_ROOT / "backend" / "app").rglob("*.py")
    refs = {
        ref
        for path in code
        for ref in re.findall(r'"(\d{2}-[a-z-]+#[a-z0-9-]+)"', path.read_text(encoding="utf-8"))
    }
    assert refs
    known = {p.source for p in manual.passages}
    assert refs <= known, refs - known


def test_search_finds_the_rule_in_english(manual):
    sources = [p.source for p in manual.search("letters skipped revision", lang="en")]
    assert "02-revisions#skipped-letters" in sources


def test_search_in_spanish_ignores_accents(manual):
    results = manual.search("revision letras omitidas", lang="es")
    assert results and all(p.lang == "es" for p in results)
    assert "02-revisions#skipped-letters" in [p.source for p in results]


def test_search_without_language_lists_each_source_once(manual):
    sources = [p.source for p in manual.search("SAP maintenance unavailable")]
    assert len(sources) == len(set(sources))
    assert "06-sap-statuses#sap-unavailable" in sources


def test_query_syntax_from_users_cant_break_fts(manual):
    assert manual.search('"unbalanced AND (NEAR OR') is not None
    assert manual.search("???") == []
    assert fts_query('Revision "I" (NEAR revision') == '"revision" OR "near"'


def test_passage_text_is_truncated_for_the_model(manual):
    passage = manual.passages[0]
    assert len(passage.to_dict(max_chars=20)["text"]) <= 22
