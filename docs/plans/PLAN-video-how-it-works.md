# PLAN — Explainer videos "From a question to an answer" (Demo + Ollama)

For Claude Code, running on the Windows PC. Read `CLAUDE.md` first. One extra phase (Phase 10, tooling only):
no product behavior changes. Storyboard: `create-design-video-storyboard.md`.

## Two videos, same four sentences

| | `video-demo` | `video-ollama` |
|---|---|---|
| Started by | `start.cmd` → Groq `n` → `d` | `start.cmd` → Groq `n` → `o` (qwen3:4b-instruct-2507-q4_K_M) |
| Health check before recording | `/api/health` → `"llm_provider":"demo"` | `"llm_provider":"ollama"` |
| Banner on every frame | "Scripted model (rules) — DemoClient" | "Real model: qwen3:4b, local (Ollama)" |
| Subtitles | Fixed text from the storyboard | Generated from the real SSE/trace of that take |
| Errors | Should not happen (deterministic) | **Shown as they are** (wrong tool, missing field, timeout): the subtitle explains that validators/gate caught it |
| Model waits | ~instant | Shown with a timer "Model thinking… 42 s", then cut to 1 s with ffmpeg |
| Extra scene | — | Raw Ollama request (`temperature 0`, `num_ctx 8192`, `tools`) and its `tool_calls`; `_calls_from_text` if it happens |

Sentences (verified live against demo on 2026-11-21, runs 37-42):
1. `Why was revision I rejected?` → pre-retrieval, top passage `07-faq#revision-i`, answer with citation.
2. `Revision C of HL-HW-26-0003, Bead Sorter Vision Board, designer C. Velazquez` → 5 fields, valid, `create_design` card.
   Variant: `Revision I of …` → `rev_skipped_letter`, "next free revision is C".
3. `Reserve a Hardware number for Bead Polisher Controller, designer C. Velazquez.` → `reserve_number` card.
4. Click **Confirm** on the reserve card (SAP number, audit), then Confirm the create card (files + PDF).

The user accepted that recording writes to the real `data/` (SAP numbers and designs). Do not reset or delete it.

## Rules for this phase

- Do not touch `backend/app`, `frontend/src`, `sap-mock/app`. New files only under `video/` and `docs/decisions/0027-explainer-videos.md`. **Ask before creating `video/`.**
- ffmpeg is already installed (user confirmed); check `ffmpeg -version`, do not install anything else without asking. Playwright comes from `e2e/node_modules`.
- Recording targets the running app: `BASE_URL=http://localhost:8000`. The user starts `start.cmd` (set `NO_BROWSER=1` optional); the script never starts or stops the app.
- `video/out/` is gitignored (videos, frames, traces). Commit scripts, subtitle templates, README.
- Conventional commits.

## Approach

1. **Playwright drives the real UI** at 1280x1080 (`recordVideo`), typing at 40-60 ms/char, waiting on UI states (not fixed sleeps). Ollama timeouts: `AGENT_TURN_TIMEOUT_S` (120 s) and `OLLAMA_TIMEOUT_S` (180 s); Playwright waits up to 200 s per turn.
2. **Capture the truth** per turn: SSE events (wrap `fetch` in `addInitScript` and copy the stream) and `GET /api/runs/{id}` → `video/out/<video>/trace-turn-N.json`. Log the time of each event (`t_ms`).
3. **Overlay** injected with `addInitScript`: right panel "Under the hood" (file:function:line, excerpt, payload), pipeline strip, bottom subtitles, provider banner. Payloads come from the captured events only.
4. **Cue builder** `video/cues.mjs`: maps each event type to a storyboard row (`tool_call:search_design_manual` + `auto` → rows 1.6-1.9, `form_proposal` → 2.8, `pending_action` → 3.4, `error` → "the code stopped it" row…). Demo: must match the storyboard exactly, otherwise fail. Ollama: build the cue list from whatever events came, including unexpected ones.
5. **Line resolver** `video/lines.mjs`: `file:symbol` → current line by regex; fail if not found. No hardcoded line numbers.
6. **Post-processing** `video/compose.mjs` (ffmpeg): cut model-wait gaps > 3 s down to 1 s (from `t_ms`), add the left 1280 + right 640 layout if the panel is rendered separately, export `.mp4`, write `subtitles.en.srt`.
7. **Ollama raw request scene**: optional dev proxy is NOT added to the app. Instead, show the request built by `OllamaClient` by calling the same function in a small script `video/ollama_payload.py` that imports `app.llm.ollama` and prints the payload for the captured messages (read-only, no network). Ask before adding it if it needs anything new.

## Steps

| # | Step | Done when |
|---|---|---|
| V0 | Re-verify every `file:symbol` in the storyboard; propose this plan; ask to create `video/` | Approved |
| V1 | `video/record.spec.ts` + `video/playwright.config.ts` (baseURL 8000, no webServer) + health/provider guard | Fails with a clear message if the wrong provider is running |
| V2 | Overlay + cue builder + line resolver; 10-second smoke clip | Overlay fits 1920x1080 |
| V3 | **Demo video**: user runs `start.cmd` with `d`; `npm run video:demo` | All storyboard rows present; `.mp4` + `.srt` in `video/out/demo/` |
| V3b | **KiCad ending (both videos)**: after the Playwright part clicks *Open in KiCad*, record the desktop with `ffmpeg -f gdigrab -framerate 30 -i desktop` (or `-i title="KiCad…"`), 40-60 s. The KiCad steps (Project Manager → schematic → zoom title block → Schematic Setup › Text Variables → Page Settings) are done **by the user by hand**, following an on-screen checklist that `video/kicad-checklist.md` describes with timings; no KiCad automation tool is added (ask before adding pywinauto or similar). Subtitles for this part come from a fixed cue file `video/cues-kicad.json`, aligned in post. Mask the Windows path, taskbar and user name with an ffmpeg `boxblur`/`drawbox` region. | `kicad.mp4` ends with the filled title block and text variables visible; `compose.mjs` appends it to each video |
| V4 | Tell the user to restart with `o`. **Ollama video**: `npm run video:ollama` | `.mp4` with the real take, errors included, waits cut and labelled |
| V5 | Extra Ollama scene (raw request / `tool_calls`) | Payload matches the run's messages |
| V6 | `video/README.md`, decision 0027, README links | A fresh clone can regenerate both videos |

## Acceptance checks

- No hand-typed payload: every JSON on screen equals the captured trace.
- Provider banner matches `/api/health` and the run's `provider`/`model`.
- Ollama video: if the model did something unexpected, it stays in the video with a subtitle explaining which validator or gate caught it (decision: show errors, do not retake).
- Wait cuts are always labelled ("42 s, sped up"), never hidden.
- No secrets, no `.env`, no Windows paths (`C:\MyData\…`) in frames; check the steps drawer and the preview dialog.

## Findings from the live check (2026-11-21, demo)

| # | Finding | Proposal |
|---|---|---|
| D1 | `DemoClient` bug: `"Reserve a new number for HW, Bead Drill Controller, …"` sets `name="HW"` (regex `_NUMBER_FOR_RE` in `llm/demo.py` takes the department code as the name) → `name_length` error. | Separate fix (not this phase): skip department codes/names in `_NUMBER_FOR_RE`, add a test. The video uses the verified sentence 3. |
| D2 | `"Revision C of the bead sorter vision board"` (e2e/showcase sentence) only fills `revision` with demo. It works in e2e because that uses a scripted `FakeClient`. | Use sentence 2. Optional: teach `DemoClient` "of the <name>" + SAP lookup. |
| D3 | `Bead Drill Controller` already exists in SAP (`HL-HW-23-0004`) → warning `name_exists_in_sap`. | Use `Bead Polisher Controller` in the video. |
| D4 | Demo reply for revision I: "(I in 'I')" reads oddly. | Minor wording fix in `demo.py`, separate commit. |
| D5 | Rule question top passage is `07-faq#revision-i`, not `02-revisions#skipped-letters`. | Storyboard updated. |
| U1 | After a reservation, under "Get SAP number" the hint shows **"Fill in first: ."** (empty list). | Separate UI fix: hide the hint when the number exists. Avoid that area in the video or record after the fix. |
| U2 | Demo is not instant: "Checking the values against the rules…" then "Thinking…" (1-2 s). | Keep: it shows the pipeline. No cut needed in the demo video. |
| U3 | Description placeholder "Six-axis stepper drive for the bead drill" looks like real text. | In scene 4 type a real description: `Polishing station controller, first release`. |
| P1 | Preview dialog shows the full Windows path `C:\MyData\ClaudeProjects\hl-create-design\data\designs\…`. | Overlay mask on the "Project file" box (or crop) in both videos; acceptance check covers it. |

## Verified full flow (demo, 2026-11-21, by UI clicks)

1. Chat: sentence 3 → card "Reserve a new SAP number?" → Confirm → **HL-HW-26-0047** rev A, material 40001242, WBS P-26-0108; form fields locked "From SAP"; folder `HW/HL-HW-26-0047/A`.
2. Form button **Create design** → card "Create this design?" appears **in the chat** (form says "A card for these values is waiting in the chat") → Confirm.
3. Preview dialog opens with the real KiCad PDF (title block filled), buttons Open in KiCad / Download project (.zip) / Open PDF / Download PDF.
4. **Open in KiCad** → status "KiCad is starting with the project. It may take a few seconds."; KiCad 9 opens the `.kicad_pro`. Files in the folder: `.kicad_pro` (with `text_variables` HL_DESIGN_NUMBER, HL_SAP_MATERIAL, HL_PROJECT, HL_DEPARTMENT, HL_DESIGNER), `.kicad_sch`, `hl_title_block.kicad_wks`, `output/*.pdf|svg`. **Both videos end here** (storyboard scene 4b).
Numbers keep increasing in the real `data/`: the Ollama video will reserve a different number (e.g. 0048). That is expected.
