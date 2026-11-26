# The video

A 2½-minute recording of the real app with a real model: Groq, `openai/gpt-oss-120b`
(decision 0032). On the left is the app. On the right, an "Under the hood" panel shows the
code behind each step and the data that passed through it. KiCad's schematic and PCB editors
are recorded at the end.

## What it shows

| Time | Step | What to notice |
|---|---|---|
| 0:00 | Title | |
| 0:07 | "Why was revision I rejected?" | The backend searches the Design Manual (SQLite FTS5) **before** the model is called; the passages go to the model as a tool result. |
| 0:22 | The answer | Written by the model from those passages, with a clickable citation `[07-faq#revision-i]`. |
| 0:32 | "Reserve a Hardware number for Bead Grader Controller, designer C. Velazquez." | The model proposes form values, then calls `validate_design_request`. The validators decide; the model only explains. |
| 0:55 | The reservation card | The model can only open a card. Nothing reaches SAP until the engineer clicks Confirm. |
| 1:11 | Confirm | `POST /api/actions/{id}/confirm` → `SapClient` → the mock SAP issues HL-HW-26-0042, the material and the project. The fields SAP owns lock. |
| 1:39 | Create | A second card and a second click. The files are written inside the designs folder only. `kicad-cli` exports the PDF. |
| 1:51 | Open in KiCad | KiCad's schematic editor, recorded on the desktop, then a cut to the title block filled from the project's text variables. |
| 2:16 | Open PCB | The board was created too. KiCad's PCB editor shows the same title block, with the same values, from the same text variables (decision 0036). |
| 2:37 | End | |

## Is it real?

- **The app and the model are real.** It is the app as `start.cmd video` runs it, and every
  answer comes from the model. Rows that the model's steps did not match are left out.
  Model waits longer than 3 s are cut to 1 s, with a label on screen. This take had none.
- **The panel shows captured data.** Each payload is the event, request or response the app
  received during the take. `cues.mjs` compares each one with the capture again, and checks
  that no local path appears. The code excerpts are found by file and symbol (`lines.mjs`),
  so their line numbers are the current ones.
- **KiCad's output is real:** the PDF comes from `kicad-cli`, and the editor is KiCad 9.

## Record it again

See [video/README.md](../video/README.md). In short:

```bash
start.cmd video                  # fresh seed data; answer n to Dahl, Y to Groq
cd video && npm ci
VIDEO_DESIGN_NAME="Bead Grader Controller" npm run video:groq
```

The output in `video/out/groq/` is `video.mp4`, `video-readme.mp4` (1280x720, under 10 MB,
for the README) and `poster.png`. The tooling is described in decision 0028.
