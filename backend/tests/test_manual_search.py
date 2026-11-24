"""The FTS5 index of the Design Manual."""

import re

from app.core.config import REPO_ROOT
from app.standards.manual_search import MAX_TEXT_CHARS, fts_query


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


def test_stopwords_are_dropped_in_both_languages():
    assert fts_query("What are the rules for the design name?") == '"rules" OR "design" OR "name"'
    spanish = fts_query("¿Qué reglas tiene el nombre del diseño?")
    assert spanish == '"reglas" OR "nombre" OR "diseño"'


def test_words_that_change_a_rule_are_not_stopwords():
    assert fts_query("no new rev in sap") == '"no" OR "new" OR "rev" OR "sap"'


def test_a_query_of_only_stopwords_still_searches():
    assert fts_query("what is it?") == '"what" OR "is" OR "it"'


def test_keywords_are_indexed_but_not_shown_to_the_model(manual):
    passage = manual.get("08-using-create-design#undo-number", "en")
    assert passage and "deshacer" in passage.keywords
    assert "Keywords" not in passage.text and "keywords" not in passage.to_dict()
    sources = [p.source for p in manual.search("deshacer liberar", lang="en", limit=3)]
    assert "08-using-create-design#undo-number" in sources


def test_every_section_reaches_the_model_whole_and_has_keywords(manual):
    for passage in manual.passages:
        assert len(passage.text) <= MAX_TEXT_CHARS, (passage.source, passage.lang)
        assert passage.keywords, (passage.source, passage.lang)


def test_citations_with_unicode_dashes_or_spaces_are_normalized():
    from app.evals.harness import CITATION
    from app.standards.manual_search import normalize_refs

    groq = "No [02‑revisions#skipped‑letters] and [ 07-faq # assistant ]."
    assert CITATION.findall(groq) == []  # the old false negative
    assert CITATION.findall(normalize_refs(groq)) == [
        "02-revisions#skipped-letters",
        "07-faq#assistant",
    ]
    assert normalize_refs("plain text - with a dash") == "plain text - with a dash"
