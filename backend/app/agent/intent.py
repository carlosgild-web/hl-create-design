"""Is a chat message a question about the rules or the app? (decision 0024)

The backend uses the answer to search the Design Manual itself before the first model
call (pre-retrieval): small local models sometimes skip the search or write the call as
text. This is a pure, deterministic function. It only decides whether to *add* a search
result to the conversation; it never decides validity (invariant 1) and never opens a card.

A message is a `rule_question` when it reads like a question or a problem report, and it
does not name a design number together with a revision. "Create HL-HW-26-0042 rev C …" is
a form fill: the model validates it instead.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

Intent = Literal["rule_question", "other"]

_NUMBER_RE = re.compile(r"\bHL-[A-Z]{2,4}-\d{2,4}-\d{1,4}\b", re.IGNORECASE)
# Checked on the text without accents, so "revisión C" matches too.
_REVISION_RE = re.compile(r"\b(rev|revision)\.?\s*[a-z]{1,2}\b")


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


# All compared without accents, in lowercase, with apostrophes removed ("didn't" -> "didnt").
_QUESTION_STARTS = _words(
    """
    why how what when where which who whom whose can could may must should shall do does did
    is are was were will would have has
    por como que cual cuales cuando donde quien quienes puedo puede pueden debo debe hay
    se es son esta estan tengo tiene
    """
)
# Question words that may come a little later ("in which folder…") or last ("…, why").
_QUESTION_WORDS = _words("why how what which where when por como cual cuales donde cuando")
_QUESTION_WINDOW = 3
# Words that make a statement a problem report or a question about a state ("Open in KiCad
# didn't work", "my design is blocked in SAP", "sap is down").
_PROBLEM_WORDS = _words(
    """
    didnt doesnt dont cant cannot wont isnt arent not failed fails failing error broken
    missing expired slow timeout timed stuck wrong rejected says mean means meaning blocked
    obsolete down locked deleted gone changed skip skips already shows instead
    no falla fallo funciona funciono caduco caducada caducado lento tarda rechaza rechazo
    dice significa falta encuentra aparece responde respondio bloqueado bloqueada obsoleto
    cayo borro borraron borrada cambio brincan saltan sale equivoque ya
    """
)
_REPLY_RE = re.compile(r"^(no|not|ya)\b\s*[,.!;]|^not that\b")
# An order ("Create …", "Crea …") is a form fill, unless it reports a problem.
_COMMANDS = _words(
    """
    create make reserve get look find delete give add open start set use fill
    crea crear haz hacer reserva reservar busca dame abre usa rellena llena pon
    """
)


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).replace("'", "")


def classify(message: str) -> Intent:
    text = message.strip()
    if not text:
        return "other"
    plain = _plain(text)
    if _NUMBER_RE.search(text) and _REVISION_RE.search(plain):
        return "other"
    words = re.findall(r"[a-z0-9]+", plain)
    if not words:
        return "other"
    if text.endswith("?") or text.startswith("¿"):
        return "rule_question"
    # "No, use HW" / "Ya, crea la revisión" answer the assistant: that first word is no report.
    reported = words[1:] if _REPLY_RE.match(plain) else words
    if set(reported) & _PROBLEM_WORDS:  # a report wins over a verb: "Open in KiCad didn't work"
        return "rule_question"
    if words[0] in _COMMANDS:
        return "other"
    if words[0] in _QUESTION_STARTS or set(words[:_QUESTION_WINDOW]) & _QUESTION_WORDS:
        return "rule_question"
    if words[-1] in _QUESTION_WORDS:
        return "rule_question"
    return "other"
