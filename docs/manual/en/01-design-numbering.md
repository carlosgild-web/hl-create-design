# 01 · Design numbering

*Hilda & Luna Beadworks · Electronics Engineering Design Manual · Edition 2026.1.
Fictional company; demo content.*

Every electronic design (a schematic project and the boards made from it) has exactly one
design number. The number identifies the design in SAP, on the title block, in the folder
name and in every conversation about it.

## Format
<a id="format"></a>

`HL-<DEPT>-<YY>-<NNNN>`

| Part | Meaning | Values |
|---|---|---|
| `HL` | Company prefix | Always `HL` |
| `DEPT` | Department code | `HW`, `PWR`, `EMB`, `TFX` (see [05-departments](05-departments.md)) |
| `YY` | Year the number was reserved | Two digits, for example `26` |
| `NNNN` | Sequence per department and year | Four digits, `0001` to `9999` |

Example: `HL-HW-26-0042` is the 42nd number that Hardware Design reserved in 2026.

Write it in capital letters with hyphens and no spaces. These are all wrong:
`hl-hw-26-0042`, `HL-HW-2026-0042`, `HL_HW_26_0042`, `HL-HW-26-42`, `HL-HWD-26-0042`.

## Only SAP issues numbers
<a id="issued-by-sap"></a>

Never invent a number, copy one from another design, or take "the next one" by looking at
the folder list. Reserve the number in Create Design: SAP returns the design number, the
SAP material number and the project (WBS element) together.

*Why:* before 2024, two engineers picking the "next" number on the same day is how
duplicate numbers reached the workshop.

## The year in the number
<a id="year"></a>

`YY` is the year the number was **reserved**, not the year the design is finished or
released. It never changes: a number reserved on 30 December 2025 stays `HL-xx-25-NNNN`
in every revision, also when revision C is made in 2027.

## The sequence
<a id="sequence"></a>

`NNNN` starts at `0001` for each department every year, and SAP issues the next free
value. Gaps are normal: a number that was reserved and then not used is never issued
again. A number is never reused, not even for a cancelled or obsolete design.

## New number or new revision?
<a id="new-number-or-revision"></a>

- **New revision, same number:** you change the same design (a fix, a component change,
  a layout change) and the new board can replace the old one. See [02-revisions](02-revisions.md).
- **New number:** the function changes, it is a different product, or the new board can't
  replace the old one. Product Engineering usually sets the old design to `OBSOLETE` with
  the new one as its successor (see [06-sap-statuses](06-sap-statuses.md)).

## SAP material number
<a id="sap-material"></a>

Each design number has one SAP material: the electronic assembly. The material number
has **18 characters with leading zeros**, in the range `000000000040000000` to
`000000000049999999` (the range for electronic assemblies).

- On the title block and in documents it is shown **without leading zeros**: `40001234`.
- In SAP and in data exchange it always has 18 characters: `000000000040001234`.
- SAP assigns it together with the design number. Never type it by hand.

## Project (WBS element)
<a id="wbs"></a>

Format `P-<YY>-<NNNN>`, for example `P-26-0108`. Every design books its engineering hours
to a project. When a number is reserved, SAP uses the department's default project for
that year (see [05-departments](05-departments.md#default-projects)). Product Engineering
can move a design to another project in SAP later.

## Quick check
<a id="quick-check"></a>

| Number | Valid? | Why |
|---|---|---|
| `HL-PWR-25-0006` | Yes | |
| `HL-HW-26-42` | No | The sequence needs four digits: `0042` |
| `HL-HW-2026-0042` | No | The year has two digits: `26` |
| `HL-MECH-26-0003` | No | `MECH` is not an Electronics Engineering department |
| `hl-emb-26-0007` | No | Capital letters only |
