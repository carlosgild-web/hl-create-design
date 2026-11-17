# 07 · Frequently asked questions

*Hilda & Luna Beadworks · Electronics Engineering Design Manual · Edition 2026.1.
Fictional company; demo content.*

## Can I choose my own design number?
<a id="own-number"></a>

No. Only SAP issues design numbers; reserve one in Create Design.
See [01-design-numbering](01-design-numbering.md#issued-by-sap).

## Why was revision I rejected?
<a id="revision-i"></a>

`I`, `O`, `Q`, `S`, `X` and `Z` are never used because they look like digits. After `H`
comes `J`. See [02-revisions](02-revisions.md#skipped-letters).

## I reserved a number by mistake. Can I give it back?
<a id="wrong-reservation"></a>

No. A reserved number is never issued again, so it stays as a gap in the sequence. That's
normal; tell your lead so nobody uses it.
See [01-design-numbering](01-design-numbering.md#sequence).

## The revision folder already exists. What now?
<a id="folder-exists"></a>

Create Design never overwrites files. Someone already created that revision: create the
next free revision instead. See [04-folder-structure](04-folder-structure.md#revision-folders).

## Can I start from an old project?
<a id="old-project"></a>

Not by copying its folder: the file names and the title block would be wrong. Create the
new design or revision in Create Design, then copy the circuit in KiCad.
See [04-folder-structure](04-folder-structure.md#revision-folders).

## The design is RELEASED. Can I make a new revision?
<a id="released-revision"></a>

Yes, with a warning: the company process requires an ECO number. Talk to your lead.
See [06-sap-statuses](06-sap-statuses.md#released).

## The design is BLOCKED or OBSOLETE.
<a id="blocked-obsolete"></a>

You can't create a revision. For a blocked design, contact Product Engineering with the
block reason. For an obsolete design, work on its successor.
See [06-sap-statuses](06-sap-statuses.md#blocked).

## Why does the material number have so many zeros?
<a id="material-zeros"></a>

SAP stores material numbers with 18 characters. The title block shows them without the
leading zeros: `000000000040001234` is `40001234`.
See [01-design-numbering](01-design-numbering.md#sap-material).

## Can I write the design name in Spanish?
<a id="name-language"></a>

No. Design names are in English and use no accents, because they go to SAP and to
supplier documents. See [03-title-block](03-title-block.md#design-name).

## Which year goes in a number reserved on 31 December?
<a id="year-end"></a>

The year of the reservation, also when the work continues in January.
See [01-design-numbering](01-design-numbering.md#year).

## Does the assistant create designs on its own?
<a id="assistant"></a>

No. The assistant explains the rules, looks up SAP and proposes values. Creating files or
reserving a number happens only when you click **Confirm**. The checks in Create Design
decide whether a value is valid, not the assistant, and the assistant can be wrong.

## SAP is not answering.
<a id="sap-down"></a>

Create Design creates nothing without SAP. Try again later.
See [06-sap-statuses](06-sap-statuses.md#sap-unavailable).
