# 07 · Frequently asked questions

*Hilda & Luna Beadworks · Electronics Engineering Design Manual · Edition 2026.1.
Fictional company; demo content.*

## Can I choose my own design number?
<a id="own-number"></a>

No. Only SAP issues design numbers; reserve one in Create Design.
See [01-design-numbering](01-design-numbering.md#issued-by-sap).

Keywords: choose number, own number, make up, pick, elegir número, inventar

## Why was revision I rejected?
<a id="revision-i"></a>

`I`, `O`, `Q`, `S`, `X` and `Z` are never used because they look like digits. After `H`
comes `J`. See [02-revisions](02-revisions.md#skipped-letters).

Keywords: revision I, letter I, rejected, revisión I, letra I, rechazada

## I reserved a number by mistake. Can I give it back?
<a id="wrong-reservation"></a>

No. A reserved number is never issued again, so it stays as a gap in the sequence. That's
normal; tell your lead so nobody uses it.
See [01-design-numbering](01-design-numbering.md#sequence).

Keywords: mistake, wrong, give back, return, cancel reservation, wrong department, error, por error, devolver, regresar, cancelar reserva

## The revision folder already exists. What now?
<a id="folder-exists"></a>

Create Design never overwrites files. Someone already created that revision: create the
next free revision instead. See [04-folder-structure](04-folder-structure.md#revision-folders).

Keywords: folder exists, already exists, overwrite, carpeta existe, ya existe, sobrescribir

## Can I start from an old project?
<a id="old-project"></a>

Not by copying its folder: the file names and the title block would be wrong. Create the
new design or revision in Create Design, then copy the circuit in KiCad.
See [04-folder-structure](04-folder-structure.md#revision-folders).

Keywords: old project, previous revision, copy, reuse, proyecto antiguo, revisión anterior, copiar, reusar

## The design is RELEASED. Can I make a new revision?
<a id="released-revision"></a>

Yes, with a warning: the company process requires an ECO number. Talk to your lead.
See [06-sap-statuses](06-sap-statuses.md#released).

Keywords: released, ECO, liberado

## The design is BLOCKED or OBSOLETE.
<a id="blocked-obsolete"></a>

You can't create a revision. For a blocked design, contact Product Engineering with the
block reason. For an obsolete design, work on its successor.
See [06-sap-statuses](06-sap-statuses.md#blocked).

Keywords: blocked, obsolete, successor, bloqueado, obsoleto, sucesor

## Why does the material number have so many zeros?
<a id="material-zeros"></a>

SAP stores material numbers with 18 characters. The title block shows them without the
leading zeros: `000000000040001234` is `40001234`.
See [01-design-numbering](01-design-numbering.md#sap-material).

Keywords: material, zeros, leading zeros, ceros

## Can I write the design name in Spanish?
<a id="name-language"></a>

No. Design names are in English and use no accents, because they go to SAP and to
supplier documents. See [03-title-block](03-title-block.md#design-name).

Keywords: spanish, accents, language, español, acentos, idioma

## Which year goes in a number reserved on 31 December?
<a id="year-end"></a>

The year of the reservation, also when the work continues in January.
See [01-design-numbering](01-design-numbering.md#year).

Keywords: year, december, january, año, diciembre, enero

## Does the assistant create designs on its own?
<a id="assistant"></a>

No. The assistant explains the rules, looks up SAP and proposes values. Creating files or
reserving a number happens only when you click **Confirm**. The checks in Create Design
decide whether a value is valid, not the assistant, and the assistant can be wrong.

Keywords: assistant, ai, on its own, by itself, disagree, who decides, valid, form error, right, asistente, ia, por su cuenta, solo, no coinciden, quién decide, válido, razón

## SAP is not answering.
<a id="sap-down"></a>

Create Design creates nothing without SAP. Try again later.
See [06-sap-statuses](06-sap-statuses.md#sap-unavailable).

Keywords: sap down, not answering, sap caído, no responde

## How do I write the designer?
<a id="designer-format"></a>

Your first name or initials, a space and the surname, as in the company directory:
`Carlos Velazquez`, `C. Velazquez`, `J. C. Pérez`, `C. de la Torre`. Accents are allowed;
maximum 40 characters. See [03-title-block](03-title-block.md#designer).

Keywords: designer, designer name, write the designer, how to write my name, format, my name, initial, surname, rejected, diseñador, nombre del diseñador, formato, inicial, apellido, no acepta

## Where are my files?
<a id="where-are-my-files"></a>

Under the designs root, in `<DEPT>/<DesignNumber>/<Rev>/`, for example
`HW/HL-HW-26-0042/A/`. The files are named `<DesignNumber>_<Rev>`, and the PDF goes to
`output/`. See [04-folder-structure](04-folder-structure.md#layout).

Keywords: files, folder, where, saved, created, kicad project, location, path, project, pdf, archivos, carpeta, dónde, se guardan, ruta, ubicación, queda

## Who are the department leads?
<a id="department-leads"></a>

HW: E. Marín · PWR: L. Brandt · EMB: A. Kowalski · TFX: R. Navarro. Ask your lead when you
are unsure which department or number to use. See [05-departments](05-departments.md#list).

Keywords: lead, leads, manager, who do I ask, contact, responsable, responsables, jefe, a quién le pregunto, contacto, quién es

## Can two designs have the same name?
<a id="same-name"></a>

Create Design doesn't stop it: the design number identifies a design, not its name. Before
you reserve a new number, search the SAP list in **From existing design**. If the new board
can replace the old one, make a new revision instead of a new number.
See [01-design-numbering](01-design-numbering.md#new-number-or-revision).

Keywords: same name, duplicate, duplicated, already exists, repeat, two designs, mismo nombre, duplicado, repetir, repetido, ya existe, otro diseño
