# 0022: Rule messages by code, and validators that match the manual

**Status:** accepted (2026-11-21)

## Context

Phase 9 block 9b (`docs/plans/PLAN-phase-9-review-and-faq.md`, findings 2, 3, 5, 6, 10, 15). The
Spanish UI showed every validator message in English. The designer check rejected real
names (`C. de la Torre`, `J. C. Pérez`). Title case mangled `LEDs` and `iPhone`. The words
`rev` and `revision` were forbidden anywhere, although the manual didn't list them, so
"Copy Stand Controller" and "Revision Counter Board" were rejected. Spanish names and names
that SAP already has passed without a word.

## Decision

1. **Messages by code.** `Issue` gets `params`. `message` stays English, because the model,
   the traces and the logs read it. The UI renders `issue.<code>` from `messages.ts`, or
   `issue.<code>.<variant>` when `params.variant` is set, and fills in the params
   (`lib/issues.ts`, `issueText`). If there's no template, it shows `message`.
   - Variants cover the codes that have several English wordings: `number_format`
     (capitals, hyphens, department, year, sequence), `department_unknown.suggest`,
     `rev_reused.older`, `status_blocked.reason`, `status_obsolete.successor`.
   - `test_issue_i18n.py` reads `messages.ts`. It checks that every code in `validators.py`
     has EN and ES templates. It also runs a battery that produces every code and variant,
     and checks that each template's placeholders are in that issue's params.
   - `Issue.to_dict()` is now the only serializer (API, cards, tools).
2. **Designer (Q1).** One or two initials, then a surname. Lowercase particles are allowed
   (`de`, `del`, `la`, `las`, `los`, `y`, `van`, `von`, `der`, `den`, `da`, `do`, `dos`),
   and so are apostrophes and hyphens. The surname's last word starts with a capital and
   has at least two letters. Digits are rejected, and so are three initials.
3. **Title case.** All-caps words and words with a capital after the first letter are kept
   (`LED`, `USB-C`, `LEDs`, `iPhone`). Lowercase hyphenated words get each part capitalized
   (`burn-in` → `Burn-In`). Underscores are not split (`Power_sink`), as before.
4. **Version words (Q2, with one refinement).**
   - **Errors:** `new` or `final` as the first word, `new`, `final` or `copy` as the last
     word, and `rev`/`revision` followed by a letter or a number (`Rev A`, `Revision 2`).
   - **Warnings:** any other use (`name_word_check`).
   - The refinement is that `copy` as the **first** word is only a warning, so the plan's
     example "Copy Stand Controller" passes (a copy stand is a device). "Final Board",
     "Board Copy" and "Rev A" stay errors.
5. **Warnings, never errors** (the code still decides validity):
   - `name_looks_spanish`: two or more words from a list of Spanish-only words (`de`,
     `placa`, `fuente`, `prueba`…), or a one-word name from the list. Words that are English
     too (`control`, `sensor`, `motor`) are not on the list, so "Motor Sensor Interface"
     passes. Cites `07-faq#name-language`.
   - `name_exists_in_sap`: another SAP design (a different number) has the same name after
     title case. It runs in `check_fields` (the inline check and the assistant's tool)
     through `sap_names_for`, which calls `SapClient.list_designs` once per check. If SAP
     fails, the warning is skipped and the check doesn't fail. Cites `07-faq#same-name`.
6. **Revision hint:** "Letters, starting at A (after Y comes AA). Never I, O, Q, S, X or Z."
7. **Manual:** `03-title-block#design-name` and `#designer` in EN and ES state the new rules.
   `design-name` was already over the 900 characters a search passage may have, so the
   model saw it cut off. It's rewritten to fit, and a test now checks that every section
   fits whole.

## Consequences

- The invariant 1 tests are unchanged; the eval with `--fake` is still 34/34.
- A new code needs an EN and an ES template, or `test_issue_i18n` fails.
- Still English in the Spanish UI: action failures that aren't validation issues (for
  example "The PDF export failed…" or SAP errors on a card) and the demo notice. 9c (finding
  18) and 9e change those paths.
- The card does not show the new name warnings yet; warnings on the card are 9c (finding 7).
