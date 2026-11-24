# Create Design · User Q&A for the assistant

Draft source material for the Create Design assistant. Each answer is grounded in the Design
Manual (`docs/manual/en/`) or in the current code. The `Ref:` line is the manual anchor the
assistant should cite. App-usage answers cite chapter 08 (`08-using-create-design`). The search test
`backend/tests/test_faq_retrieval.py` checks that each question finds its section
(questions and paraphrases in `backend/app/evals/faq_questions.json`).

---

## 1. Getting started

### What does Create Design do?
It starts a KiCad 9 project from the company template with the title block already filled
in: design number, revision, SAP material, project, department, designer, date. It exports a
PDF and a preview, and offers a zip and an **Open in KiCad** button.
Ref: 03-title-block#fields

### New design or new revision: which one do I pick?
- **New revision (same number):** the same design changes (a fix, a component swap, a layout
  change) and the new board can replace the old one. Pick **From existing design**.
- **New number:** the function changes, it is a different product, or the new board can't
  replace the old one. Pick **New design**.
Ref: 01-design-numbering#new-number-or-revision

### What do I need before I start a new design?
Department, a design name in English, and your name as designer (`C. Velazquez`). SAP gives
the number, material and project when you click **Get SAP number**. The description is
optional.
Ref: 08-using-create-design#start-panel

### What do I need for a new revision?
Pick the design from the SAP list in the Start panel. Department, number, name and the next
revision are filled in and locked. You only add the designer and, if you want, a description.
Ref: 03-title-block#name-from-sap

### Can the assistant fill the form for me?
Yes. Describe the design in one sentence ("revision C of the bead sorter vision board" or
"new controller board for the drilling machine, Hardware") and it proposes the values. You
still review them and click **Confirm**.
Ref: 08-using-create-design#assistant-fills-form

### Can it guide me one field at a time?
Yes: click **Guide me step by step**. It asks one short question per reply.
Ref: 08-using-create-design#step-by-step

### Does the assistant create anything on its own?
No. It explains rules, looks things up in SAP and proposes values. A number is reserved, or
files are created, only when you click **Confirm** on a card. The checks in the code decide
whether a value is valid, not the assistant, and the assistant can be wrong.
Ref: 07-faq#assistant

---

## 2. Design numbers

### Can I choose my own design number?
No. Only SAP issues numbers. Use **Get SAP number** (new design) or pick an existing design.
Ref: 01-design-numbering#issued-by-sap

### What is the format of a design number?
`HL-<DEPT>-<YY>-<NNNN>`, for example `HL-HW-26-0042`: capital letters, hyphens, no spaces, a
two-digit year and a four-digit sequence.
Ref: 01-design-numbering#format

### Why is `HL-HW-26-42` (or `hl-hw-26-0042`, `HL-HW-2026-0042`) wrong?
The sequence needs four digits (`0042`), the letters must be capitals, and the year has two
digits (`26`).
Ref: 01-design-numbering#quick-check

### Why does it say my number "doesn't exist in SAP"?
Only numbers that SAP issued can be used. Check for a typo, or reserve a new number.
Ref: 01-design-numbering#issued-by-sap

### Why does it say the number "belongs to department HW, not PWR"?
The department code is part of the number. A number reserved for one department can't be
used under another.
Ref: 01-design-numbering#format

### Which year goes in the number? The work continues next year.
The year the number was reserved. It never changes, also for later revisions.
Ref: 01-design-numbering#year

### I see gaps in the numbers (0041, then 0044). Is something wrong?
No. Reserved but unused numbers are never issued again, so gaps are normal.
Ref: 01-design-numbering#sequence

### I reserved a number by mistake. Can I give it back?
No. It stays as a gap. Tell your lead so nobody uses it.
Ref: 07-faq#wrong-reservation

### I clicked **Undo** after reserving. Is the number released?
No. **Undo** only removes the number from the form. The reservation stays in SAP.
Ref: 08-using-create-design#undo-number

---

## 3. Revisions

### Why was revision `I` (or `O`, `Q`, `S`, `X`, `Z`) rejected?
These letters are never used because they look like digits or marks: after `H` comes `J`,
after `N` comes `P`, after `R` comes `T`, after `W` comes `Y`.
Ref: 02-revisions#skipped-letters

### What is the full revision sequence?
`A B C D E F G H J K L M N P R T U V W Y`, then `AA`, `AB`, `AC`…
Ref: 02-revisions#sequence

### Can I start at revision 0, 01, P1 or `-`?
No. Every new design starts at `A`, prototypes too, and there are no sub-revisions like `A1`.
Ref: 02-revisions#first-revision

### The change is big. Can I jump from C to F?
No. After `C` comes `D`, whatever the size of the change. The form shows the next free letter.
Ref: 02-revisions#next-revision

### Revision C was abandoned and its folder deleted. Can I reuse C?
No. A letter that was ever created stays used; the next one is `D`.
Ref: 02-revisions#never-reuse

### The SAP list says "latest B → rev E". Why not C?
Revisions C and D exist as folders but not in SAP (created before Create Design recorded
revisions in SAP). The next free letter counts both, and a letter is never reused. Revisions
created now are recorded in SAP when you confirm, so the list shows them as the latest.
Ref: 08-using-create-design#next-free-revision, 02-revisions#never-reuse

### The revision folder already exists. What now?
Create Design never overwrites files. Someone already created that revision; create the next
free one.
Ref: 04-folder-structure#revision-folders

---

## 4. SAP status

### The design is RELEASED. Can I make a new revision?
Yes, with a warning. The company process requires an ECO number before the revision is
released. Create Design doesn't check it; tell your lead.
Ref: 06-sap-statuses#released

### The design is BLOCKED. What do I do?
You can't create a revision. Contact Product Engineering with the design number and the block
reason SAP shows.
Ref: 06-sap-statuses#blocked

### The design is OBSOLETE. What do I do?
Work on the successor shown in SAP (**Use successor** in the Start panel). If there's no
successor and you need the function again, reserve a new number.
Ref: 06-sap-statuses#obsolete

### Can I change the status of a design here?
No. Product Engineering changes statuses in SAP; Create Design only reads them.
Ref: 06-sap-statuses#who-changes

### SAP is not answering (503, timeout). What happens?
Nothing is created or reserved, not even halfway. Try again later.
Ref: 06-sap-statuses#sap-unavailable

---

## 5. Design name, description, designer

### What are the rules for the design name?
3–40 characters; letters A–Z, digits, spaces and `- _ .`; no accents; in English; describes
the function. It's stored in title case.
Ref: 03-title-block#design-name

### Why did my name change from `bead drill controller` to `Bead Drill Controller`?
Names are stored in title case, also each part of a hyphenated word (`Burn-In`). Words written
with capitals (`LED`, `24V`, `LEDs`) are kept.
Ref: 03-title-block#design-name

### Why can't I use "New", "Final" or "Copy" in the name?
The name describes the function. `New` or `Final` as the first word, `New`, `Final` or `Copy`
as the last word, and `Rev A` are rejected. Inside the name they're only a warning
(`Copy Stand Controller` passes). The version goes in the revision.
Ref: 03-title-block#design-name

### Can I write the name in Spanish or with accents?
No. Names go to SAP and to supplier documents. Use the description for Spanish text.
Ref: 07-faq#name-language

### Can two designs have the same name?
Create Design doesn't stop it: the design number is what identifies a design. Before you
reserve a new number, search the SAP list in **From existing design**. If the board can
replace the old one, you want a new revision, not a new number.
Ref: 07-faq#same-name

### Why is the name locked in a new revision?
A new revision keeps the name SAP has. For a different name, ask your lead for a new number.
Ref: 03-title-block#name-from-sap

### What is the description for?
One optional line (max 60 characters) in small italics under the title, for example "Rev C:
second source for the gate driver". Accents and Spanish are fine. `${` isn't allowed.
Ref: 03-title-block#description

### How do I write the designer?
One or two initials with a period, a space and the surname, as in the company directory:
`C. Velazquez`, `J. C. Pérez`, `C. de la Torre`. Accents are allowed; maximum 40 characters.
Ref: 03-title-block#designer, 07-faq#designer-format

### Why does the material number have so many zeros?
SAP stores 18 characters; the title block shows it without leading zeros:
`000000000040001234` is `40001234`.
Ref: 01-design-numbering#sap-material

### Where does the project (P-26-0108) come from?
SAP assigns the department's default project for the year. Product Engineering can move it
later.
Ref: 05-departments#default-projects

---

## 6. Departments

### Which department do I pick?
By the main function of the board. HW: control and interface boards. PWR: supplies, motor and
heater drivers. EMB: microcontroller boards. TFX: test jigs and fixtures (always TFX, even
with a supply or processor inside). When in doubt, ask the lead before reserving.
Ref: 05-departments#choosing

### Who are the department leads?
HW: E. Marín · PWR: L. Brandt · EMB: A. Kowalski · TFX: R. Navarro.
Ref: 05-departments#list

### I picked the wrong department after reserving. Can I change it?
No. The code is part of the number, and a number never changes. Reserve a new number in the
right department and tell your lead about the unused one.
Ref: 05-departments#choosing, 07-faq#wrong-reservation

---

## 7. Files, PDF and KiCad

### Why does my new design already have a 24 V to 5 V circuit?
That's the template's example circuit; it shows that the sheet and the title block work.
Delete it and draw your own circuit. For a new revision, copy the circuit from the previous
revision in KiCad.
Ref: 08-using-create-design#template-circuit

### Where are my files saved?
`<designs root>/<DEPT>/<DesignNumber>/<Rev>/`, with files named `<DesignNumber>_<Rev>`. The PDF
and SVG go to `output/`.
Ref: 04-folder-structure#layout

### Can I save the project on my desktop or another drive?
No. Everything stays under the designs root. Absolute paths, `..` and drive letters are refused.
Ref: 04-folder-structure#designs-root

### How do I continue from my previous revision?
Create the new revision here, then open both projects in KiCad and copy the schematic content.
Don't copy the whole folder.
Ref: 04-folder-structure#revision-folders

### **Open in KiCad** didn't work.
Open the project file shown under the preview in KiCad 9 (*File › Open Project…*). You can also
download the project as a zip.
Ref: 08-using-create-design#open-in-kicad

### There's no PDF or preview.
The PDF needs `kicad-cli` (KiCad 9). Without it the design is still created, without the PDF
and the preview, and the card says why. Open the project in KiCad, and tell your administrator,
who installs KiCad 9 or sets `KICAD_CLI` if KiCad isn't on the PATH.
Ref: 08-using-create-design#no-pdf

### Can I edit the title block in KiCad's Page Settings?
No. The values come from SAP and the manual. To change the number or revision, create a new
revision; never edit `hl_title_block.kicad_wks`.
Ref: 03-title-block#dont

---

## 8. Cards, the assistant and errors

### What is the card in the chat?
A confirmation card. Nothing happens until you click **Confirm**; **Cancel** leaves everything
unchanged.
Ref: 08-using-create-design#confirmation-cards

### My card says "expired".
Cards expire after 30 minutes. Ask again, or use the form button to get a new card.
Ref: 08-using-create-design#card-expired

### What is "Agent steps"?
A log of what the assistant did: model calls, tools used and their results. Use it to see why
it answered the way it did.
Ref: 08-using-create-design#agent-steps

### The assistant only answers "Demo mode: no language model is configured".
No AI model is connected, so the demo assistant answers with simple rules: questions from the
manual with a reference, the form from a sentence, and the card when the checks pass. For the
rest, fill in the form yourself; the checks, SAP and the cards work as usual.
Ref: 08-using-create-design#demo-mode

### The assistant is slow or says it timed out.
The local model (Ollama) can be slow on CPU. Wait, press **Stop**, or fill in the form
directly: the form works without the assistant.
Ref: 08-using-create-design#slow-assistant

### The assistant and the form disagree. Which one is right?
The form's checks. The assistant only explains their results and can be wrong.
Ref: 07-faq#assistant
