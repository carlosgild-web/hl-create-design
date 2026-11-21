"""`GET /api/manual/{lang}/{document}/{anchor}`: one Design Manual passage, for the UI.

Read-only, and it serves only passages the search index holds (decision 0026): the path
parts are looked up as an index key, never joined into a file path. A citation such as
`[02-revisions#skipped-letters]` in the chat or on the form opens this passage.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException

from app.api.deps import ManualDep

router = APIRouter(prefix="/api/manual", tags=["manual"])


@router.get("/{lang}/{document}/{anchor}")
def manual_passage(
    lang: Literal["en", "es"], document: str, anchor: str, manual: ManualDep
) -> dict[str, str]:
    passage = manual.get(f"{document}#{anchor}", lang)
    if passage is None:
        raise HTTPException(404, "No such manual section")
    return {
        "source": passage.source,
        "lang": passage.lang,
        "document": passage.document,
        "heading": passage.heading,
        "text": passage.text,
    }
