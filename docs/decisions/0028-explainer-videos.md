# 0028: Explainer videos recorded from the real app

**Status:** accepted (2026-11-21)

## Context

Phase 10 adds two explainer videos, "From a question to an answer": a Demo video
(`DemoClient`) and an Ollama video. Each one shows the real app next to an "Under the hood"
panel: the code behind each step and the data that passed through it. The video is only
worth something if what it shows is what happened. That rules out typed-in payloads,
hand-written line numbers and a mock-up of the UI. The plan
(`Claude outputs/PLAN-video-how-it-works.md`) wanted to change no product code. It also
wanted no new files outside `video/` and this record.

## Decision

1. **A stage page on the app's own origin.** The recorder (Playwright, in `video/`) serves
   `video/stage.html` at `/__video/stage.html` through `page.route`. Nothing is added to
   the app. The stage is 1920x1080:
   - the real app in a same-origin iframe (1280x960);
   - the panel (640x960);
   - a subtitle bar (1920x120);
   - full-size slides for the title, the architecture, the invariants, the trace and the
     comparison.

   This replaces the storyboard's layout, where the app was recorded at 1280x1080 and the
   panel was added in post.
2. **Payloads only from the take's own capture.** An init script wraps the app's `fetch`.
   It captures:
   - the `POST /api/chat` request and every SSE event of its stream;
   - the JSON of `POST /api/actions` and `.../confirm`.

   After each run the recorder saves `GET /api/runs/{id}`. Every panel payload names its
   source (event index, trace turn, or introspect command). `cues.mjs` checks each payload
   against `events.json` / `trace-turn-N.json` after the take, and fails on any difference
   or any local path.
3. **Paced delivery, unchanged content.** Node handles each captured event before the app
   receives it. That is how a subtitle stays on screen while the app shows that step. The
   server runs at full speed, and the events reach the app unchanged and in order. Only
   their delivery to the browser is paced.
4. **No line numbers by hand.** The storyboard names `[file, symbol]`. `lines.mjs` finds
   the current line and excerpt by regex at take time. `npm run video:check` fails when a
   symbol is gone.
5. **`video/introspect.py`, read only.** Two rows show data the stream and the trace don't
   carry:
   - the FTS5 terms and BM25 ranking for the captured query;
   - the intent label.

   The script imports the backend's own `fts_query`, `ManualIndex` and `classify`, and runs
   with the backend's venv. It writes nothing and opens no connection. The take fails if
   its ranking differs from the order the tool returned.
6. **Strict storyboard for the demo.** `video/storyboard.json` holds the rows as data. Each
   row is triggered by a spec step or by a captured event (with a `before`/`after` phase).
   The demo take fails when a row is missing or out of order, or when a run ends early. The
   Ollama video (V4) will build its cues from whatever came.
7. **Guard and privacy.**
   - The take starts only if `/api/health` reports the expected provider.
   - The preview dialog's "Project file" path is blurred.
   - The app's visible text is checked for local paths at the Agent steps drawer and the
     preview dialog.
8. **Its own `package.json`.** `video/` pins `@playwright/test` to the version `e2e/` uses
   and drives the installed Edge (`channel: msedge`), so no browser is downloaded.
   `video/out/` and `video/node_modules/` are gitignored. Recording writes to the real
   `data/` (SAP numbers, designs), which is accepted.

## App fixes found while planning (V0b)

The live check found three small bugs. They were fixed before recording, each with a test:
- **D1:** `DemoClient` took `HW` as the design name in "number for HW, …".
- **D4:** revision `I` read "(I in 'I')". It now uses a `single` variant (the 0022
  mechanism).
- **U1:** the Start panel showed "Fill in first: ." when nothing was missing.

## Consequences

- The scripts in `video/` are tooling. CI does not run them: they need the running app
  and a browser.
- The storyboard's line numbers and the "02-revisions#skipped-letters as #2" ranking were
  out of date. The take now shows the current ones (the FAQ passage first, then the
  designer and title-block passages).
- The Ollama video (V4–V5) and the KiCad desktop ending (V3b) reuse the stage, the capture
  and the checks.
