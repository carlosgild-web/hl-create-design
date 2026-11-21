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
| Description (optional) | `Six-axis stepper drive for the bead drill` | You |
| Design No. | `HL-HW-26-0042` | SAP ([01-design-numbering](01-design-numbering.md)) |
| Rev | `A` | You, checked against [02-revisions](02-revisions.md) |
| SAP material | `40001234` | SAP, shown without leading zeros |
| Project | `P-26-0108` | SAP |
| Department | `HW – Hardware Design` | [05-departments](05-departments.md) |
| Designer | `C. Velazquez` | You |
| Date | `2026-11-17` | The day the revision was created |
| Sheet | `1/1` | KiCad |

Keywords: title block, fields, what is filled, cajetín, campos, qué se rellena

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

Keywords: name rules, design name, length, how long, characters, allowed, title case, capitals, capitalized, new, final, copy, rejected word, reglas del nombre, nombre del diseño, largo, caracteres, mayúsculas, palabra rechazada

## Name of an existing design
<a id="name-from-sap"></a>

A new revision keeps the name the design already has in SAP. The name is the short text of
the SAP material, so every revision of a design carries the same title.

- When the design number exists in SAP, the design name **must be SAP's name** (after the
  formatting above: title case, single spaces). Create Design fills it in and locks it.
- To give a design a different name, ask the department lead for a new design number. The
  name of an existing material is never changed from a title block.

Keywords: locked name, rename, change name, revision name, existing design, nombre bloqueado, cambiar el nombre, renombrar, diseño existente

## Description
<a id="description"></a>

An optional line printed in small italics under the title. Use it to say what this design
or revision is for, when the name alone doesn't: `Six-axis stepper drive for the bead
drill`, `Rev C: second source for the gate driver`.

- **Optional**, at most **60 characters**, one line.
- Any language and accents are allowed: unlike the name, it doesn't go to SAP.
- Spaces at the start and the end are removed, and repeated spaces become one.
- Not allowed: tabs or other control characters, and `${`, which KiCad would read as a
  text variable and replace with another field.
- In KiCad it is the title block's *Comment 1* (`${COMMENT1}`).

Keywords: description, optional, 60 characters, spanish, how long, descripción, opcional, español, qué tan larga

## Designer
<a id="designer"></a>

Initial, period, space, surname, as in the company directory: `C. Velazquez`, `E. Marín`.
Accents are allowed here. Maximum 40 characters.

Keywords: designer, designer name, format, initial, surname, rejected my name, diseñador, nombre del diseñador, formato, inicial, apellido

## Date
<a id="date"></a>

ISO 8601 format, `YYYY-MM-DD`: `2026-11-17`. Never `17/11/2026` or `11/17/2026`, which
mean different days in different countries.

Keywords: date, issue date, fecha

## Paper and sheets
<a id="paper"></a>

The template uses A4 landscape. In a hierarchical schematic, every sheet uses the same
drawing sheet, so every page shows the same design number and revision.

Keywords: paper, sheet size, A4, A3, sheets, papel, tamaño de hoja, hojas

## Don't
<a id="dont"></a>

- Don't copy the title block, or the whole project, from an old design.
- Don't draw text over the title block or edit `hl_title_block.kicad_wks`.
- Don't change the design number or revision in KiCad; create a new revision instead.

Keywords: page settings, edit title block, change revision in kicad, kicad_wks, drawing sheet, modify, configuración de página, editar cajetín, modificar, hoja
