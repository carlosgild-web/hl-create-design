# 03 · Title block

*Hilda & Luna Beadworks · Electronics Engineering Design Manual · Edition 2026.1.
Fictional company; demo content.*

Every schematic sheet uses the company drawing sheet `hl_title_block.kicad_wks`. Create
Design fills in the fields when it creates the project. Don't type them by hand in KiCad's
*Page Settings* dialog: the values come from SAP and from this manual.

## Fields
<a id="fields"></a>

| Field | Example | Comes from |
|---|---|---|
| Logo and company | Hilda & Luna Beadworks | The template |
| Title | `Bead Drill Controller` | You: the design name |
| Design No. | `HL-HW-26-0042` | SAP ([01-design-numbering](01-design-numbering.md)) |
| Rev | `A` | You, checked against [02-revisions](02-revisions.md) |
| SAP material | `40001234` | SAP, shown without leading zeros |
| Project | `P-26-0108` | SAP |
| Department | `HW – Hardware Design` | [05-departments](05-departments.md) |
| Designer | `C. Velazquez` | You |
| Date | `2026-11-17` | The day the revision was created |
| Sheet | `1/1` | KiCad |

## Design name
<a id="design-name"></a>

The design name is the title on every sheet and the short text of the material in SAP.

- **3 to 40 characters.** 40 is the length of the SAP material short text.
- **Allowed characters:** letters `A–Z` and `a–z`, digits, spaces, and `-`, `_`, `.`.
  No accents or other symbols: the name goes to SAP and to supplier systems that can't
  handle them.
- **In English**, because the name appears on supplier documents.
- **Stored in title case:** every word starts with a capital letter. Words already written
  in capitals are kept (`LED`, `USB`, `24V`). Create Design converts the name for you:
  `bead drill controller` becomes `Bead Drill Controller`.
- Spaces at the start and the end are removed, and repeated spaces become one.
- **Describe the function.** Don't put the design number, the revision or words like
  `new`, `final` or `copy` in the name. `Kiln Thermocouple Interface` is a good name;
  `HL-HW-26-0042 Rev A` and `New Board Final` are not.

## Designer
<a id="designer"></a>

Initial, period, space, surname, as in the company directory: `C. Velazquez`, `E. Marín`.
Accents are allowed here. Maximum 40 characters.

## Date
<a id="date"></a>

ISO 8601 format, `YYYY-MM-DD`: `2026-11-17`. Never `17/11/2026` or `11/17/2026`, which
mean different days in different countries.

## Paper and sheets
<a id="paper"></a>

The template uses A4 landscape. In a hierarchical schematic, every sheet uses the same
drawing sheet, so every page shows the same design number and revision.

## Don't
<a id="dont"></a>

- Don't copy the title block, or the whole project, from an old design.
- Don't draw text over the title block or edit `hl_title_block.kicad_wks`.
- Don't change the design number or revision in KiCad; create a new revision instead.
