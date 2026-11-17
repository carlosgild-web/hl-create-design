# 02 · Revisions

*Hilda & Luna Beadworks · Electronics Engineering Design Manual · Edition 2026.1.
Fictional company; demo content.*

A revision letter identifies one version of a design. The design number plus the
revision identify exactly one set of files: `HL-HW-26-0042` revision `B`.

## The sequence
<a id="sequence"></a>

`A B C D E F G H J K L M N P R T U V W Y`

After `Y` comes `AA`, then `AB`, `AC`… with the same letters skipped in each position.
Twenty revisions of one design is very unusual; if you get there, talk to your lead.

## Skipped letters
<a id="skipped-letters"></a>

The letters **I, O, Q, S, X and Z are never used**, in capitals or lowercase. On a printed
title block, a silkscreen or a label they are easily read as something else:

| Letter | Mistaken for |
|---|---|
| `I` | the digit `1` |
| `O` | the digit `0` |
| `Q` | `O` or `0` |
| `S` | the digit `5` |
| `X` | a cross-out mark or the multiplication sign |
| `Z` | the digit `2` |

So after `H` comes `J`, after `N` comes `P`, after `R` comes `T`, and after `W` comes `Y`.

## The first revision
<a id="first-revision"></a>

A new design starts at revision **`A`**. There is no revision `0`, `-`, `01` or `P1`.
Prototypes use letters too, and there are no sub-revisions such as `A1` or `A.2`.

## The next revision
<a id="next-revision"></a>

The next revision is the next letter of the sequence after the highest revision that
exists. Don't jump ahead: after `C` comes `D`, even when the change is large. Create Design
checks the existing revisions and suggests the next free letter.

## Never reuse a letter
<a id="never-reuse"></a>

A letter that was ever created stays used, even if its folder was deleted or the
revision was abandoned. If revision `C` was started and abandoned, the next one is `D`.

*Why:* the PDFs of `C` may already have gone to the workshop or a supplier. Two different
boards with the same number and letter would be indistinguishable.

## Revisions and the SAP status
<a id="revisions-and-status"></a>

| Design status in SAP | New revision |
|---|---|
| `IN_WORK` | Allowed |
| `RELEASED` | Allowed, with a warning: the company process requires an ECO number (not checked by this version of Create Design) |
| `BLOCKED` | Not allowed |
| `OBSOLETE` | Not allowed: use the successor design |

See [06-sap-statuses](06-sap-statuses.md).

## Quick check
<a id="quick-check"></a>

| Existing revisions | Requested | Valid? | Why |
|---|---|---|---|
| none | `A` | Yes | New designs start at `A` |
| none | `B` | No | New designs start at `A` |
| `A B C D E F G H` | `I` | No | `I` is skipped; the next is `J` |
| `A B C` | `E` | No | Don't jump ahead; the next is `D` |
| `A B` | `B` | No | `B` exists; letters are never reused |
| `A B C D E F G H J K L M N` | `P` | Yes | `O` is skipped |
