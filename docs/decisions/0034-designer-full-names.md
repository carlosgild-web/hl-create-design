# 0034: The designer may be written with full given names

**Status:** accepted (2026-11-26). Amends the designer rule in `03-title-block#designer`.

## Context

The rule accepted only initials and a surname (`C. Velazquez`, `J. C. Pérez`), "as in the
company directory". Engineers testing the app typed their full name, `Carlos Velazquez`, and
were refused. The rule's purpose is a consistent, readable designer field in the title
block. It never needed initials: a full name is just as consistent and easier to read.

## Decision

The designer is one or more given names, then a surname, separated by single spaces:

- Each given name is a full name word (`Carlos`) or an initial with a period (`C.`). The
  two kinds can be mixed: `Carlos A. Velazquez`. At most two initials.
- Name words start with a capital and have at least two letters. Accents, apostrophes and
  hyphens are allowed; digits are not.
- Surname particles may be lowercase (`de`, `del`, `la`, `los`, `van`, `von`, `y`, ...).
  An initial after a particle is refused (`C. de A. Torre`).
- At least two words; the last is a capitalized surname. Maximum 40 characters, as before.

Accepted: `Carlos Velazquez`, `Juan Carlos Pérez`, `Carlos A. Velazquez`, `C. Velazquez`,
`J. C. Pérez`, `C. de la Torre`. Refused: `Carlos`, `carlos velazquez`, `C Velazquez`,
`Carlos Velazquez A.`.

The rule stays in `standards/validators.py` (invariant 1). Its error keeps the code
`designer_format`, with new wording in English and Spanish. The manual (`03-title-block`,
`07-faq`), the Q&A documents and the form hint now show both forms.

## Consequences

- Every name the old rule accepted is still accepted, so existing designs and the seed data
  are unaffected.
- The stored eval results in `docs/eval/` quote the old message; they are kept as the
  record of those runs.
