# 08 · Using Create Design

*Hilda & Luna Beadworks · Electronics Engineering Design Manual · Edition 2026.1.
Fictional company; demo content.*

How the Create Design app works: the Start panel, the assistant, the confirmation cards and
the files it makes. The rules themselves are in chapters 01–06.

## What Create Design does
<a id="what-it-does"></a>

Create Design starts a KiCad 9 project from the company template with the title block
already filled in: design number, revision, SAP material, project, department, designer and
date (see [03-title-block](03-title-block.md#fields)). It exports a PDF and a preview, and
offers the project as a zip and an **Open in KiCad** button.

Keywords: purpose, overview, what is this app, app, tool, qué hace, para qué sirve, aplicación, herramienta, genera, kicad project

## New design or a design from SAP
<a id="new-or-existing"></a>

In the Start panel, pick what you want to create:
- **New design** gets a new number from SAP and starts at revision `A`. Use it when the
  function changes or the board can't replace the old one.
- **From existing design** adds the next revision to a design in SAP. Pick the design in
  the list; department, number, name and the next revision are filled in and locked.

See [01-design-numbering](01-design-numbering.md#new-number-or-revision).

Keywords: new design, existing design, new revision, new number, which one, choose, diseño nuevo, diseño existente, revisión nueva, número nuevo, cuál elijo

## The Start panel
<a id="start-panel"></a>

For a **New design**, fill in Department, Design name (in English) and Designer
(`C. Velazquez`), then click **Get SAP number**. SAP gives the number, the material and the
project, and department and name are then locked to what SAP recorded (**Undo** frees them).
The description is optional.

For a new revision, pick the design in the SAP list. You only add the designer and, if you
want, a description. Then click **Create design** and confirm the card.

Keywords: start, begin, first steps, what do I need, fields, get sap number, reserve, empezar, inicio, primeros pasos, qué necesito, campos, obtener número sap, reservar, arrancar, llenar

## The assistant fills the form
<a id="assistant-fills-form"></a>

Describe the design in one sentence, for example "revision C of the bead sorter vision
board" or "new controller board for the drilling machine, Hardware". The assistant looks
the design up in SAP and proposes the values for the form. Review them; nothing is created
until you confirm a card. **Try an example** sends such a sentence.

Keywords: assistant, ai, fill, fill in, autofill, propose values, describe, sentence, asistente, ia, rellenar, llenar, formulario, proponer, describir, frase, probar un ejemplo

## Step by step
<a id="step-by-step"></a>

Click **Guide me step by step**. The assistant asks one short question per reply, one field
at a time, and checks each answer before the next question.

Keywords: guide, guided, wizard, step by step, one field at a time, one by one, questions, guíame, guiado, paso a paso, campo por campo, uno por uno, preguntas

## Confirmation cards
<a id="confirmation-cards"></a>

A card in the chat shows what is about to happen: reserving a number or creating a design.
Nothing happens until you click **Confirm**. **Cancel** leaves everything unchanged. The
assistant can open a card, but only your click runs it.

Keywords: card, confirm, cancel, button, click, nothing happens, tarjeta, confirmar, cancelar, botón, clic, chat

## A card expired
<a id="card-expired"></a>

A card is valid for 30 minutes. After that it says it expired and can't be confirmed. Ask
the assistant again, or use the button on the form to get a new card.

Keywords: expired, expiry, too late, 30 minutes, timeout, how long, caducó, caducada, vencida, expiró, 30 minutos, cuánto dura

## Undo after reserving
<a id="undo-number"></a>

**Undo** only clears the number from the form. The reservation stays in SAP and the number
is not released: a reserved number is never issued again. If you reserved it by mistake,
tell your lead (see [07-faq](07-faq.md#wrong-reservation)).

Keywords: undo, release, release number, free, give back, cancel reservation, deshacer, liberar, liberar número, devolver, cancelar reserva

## The next free revision
<a id="next-free-revision"></a>

The SAP list shows the latest revision and the next free one, for example "latest D → rev
E". Create Design records every new revision in SAP when you confirm it, before it writes the
folder, so a revision counts even if its folder is deleted later. The next free letter also
skips revision folders that exist without a SAP record. A letter is never reused (see
[02-revisions](02-revisions.md#never-reuse)).

Keywords: latest, next revision, skipped C, skips, rev E, why not, letter, list, última, siguiente revisión, se salta, por qué no, letra, lista

## The example circuit in the template
<a id="template-circuit"></a>

Every new project starts from the company template, which has an example circuit: a 24 V
to 5 V, 3 A supply. It shows that the sheet and the title block work. Delete it and draw
your own circuit. For a new revision, open the previous revision in KiCad and copy its
circuit.

Keywords: example circuit, template circuit, 24 V, 24V, 5 V, supply, sample, delete, schematic, circuito de ejemplo, plantilla, fuente, borrar, esquemático, trae

## Open in KiCad
<a id="open-in-kicad"></a>

**Open in KiCad** starts KiCad 9 on the computer that runs Create Design. If it doesn't
start, open the project file shown under the preview in KiCad 9 (*File › Open Project…*),
or download the project as a zip.

Keywords: open in kicad, didn't work, does not open, failed, button, zip, download, abrir en kicad, no funcionó, no abre, falla, botón, descargar

## No PDF or preview
<a id="no-pdf"></a>

The PDF and the preview are made by `kicad-cli` (KiCad 9). If it is missing or fails, the
design is still created: the KiCad project is in its folder and the card says why there is no
PDF. Open the project in KiCad 9 as usual. For PDFs, ask your administrator to install KiCad
9, or to set `KICAD_CLI` if KiCad isn't on the PATH.

Keywords: pdf, preview, export failed, kicad-cli, not found, missing, svg, exportación, vista previa, falló, no encuentra, falta

## Agent steps
<a id="agent-steps"></a>

**Agent steps** shows what the assistant did for each answer: the model calls, the tools it
used and the results it saw. Use it to see why it answered the way it did.

Keywords: agent steps, steps, trace, log, tool calls, what did the assistant do, pasos del agente, pasos, registro, herramientas, qué hizo

## Demo mode
<a id="demo-mode"></a>

Without an AI model, the demo assistant answers ("(Demo assistant)", and the header says
"Assistant: demo (no AI)"). It follows simple rules: it answers questions with the first lines
of the best manual section and its reference, fills the form from a sentence that names the
values (a name in quotes), and opens the confirmation card when the checks pass. For anything
else, fill in the form yourself: the checks, SAP and the cards work as usual.

Keywords: demo mode, demo, no language model, no ai, not configured, fake, modo demo, demostración, sin ia, sin modelo, no configurado

## The assistant is slow
<a id="slow-assistant"></a>

A local model (Ollama) can be slow on a computer without a graphics card. Wait, press
**Stop**, or fill in the form directly: the form works without the assistant. If the model
doesn't answer in time, the answer stops and the app may offer another model.

Keywords: slow, timed out, timeout, no answer, waiting, stop, ollama, lento, tarda, se agotó el tiempo, no responde, esperar, parar
