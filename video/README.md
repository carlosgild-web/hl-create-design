# Explainer videos

Records "From a question to an answer" from the running app (decision 0028). The published
video is the short one on Groq (decision 0032); [docs/video.md](../docs/video.md) says what
it shows. Recording needs Windows (Edge, and ffmpeg `gdigrab` for the KiCad window) and
ffmpeg on the `PATH`.

```bash
cd video && npm ci          # @playwright/test only; uses the installed Edge
npm run video:check         # every [file, symbol] in storyboard.json still resolves
npm run video:smoke         # 10 s: the 1920x1080 stage -> out/smoke/
```

The short video for the README (a real model, ~2 min, decisions 0030 and 0032):

1. Start the app on fresh seed data: `start.cmd video` (it deletes and re-seeds `data-video/`;
   your `data/` is not touched). Answer `n` to "Use Dahl?" and `Y` to "Use Groq?".
2. `VIDEO_DESIGN_NAME="Bead Grader Controller" npm run video:groq`. Use a name that is not in
   the seed. It writes to `out/groq/` (`npm run video:dahl` records the same rows on Dahl,
   into `out/dahl/`):
   - `video.mp4`, with the model waits over 3 s shortened to 1 s and labelled;
   - `video-readme.mp4` (1280x720, under 10 MB) and `poster.png`;
   - `take.json`, which lists the storyboard rows the model's turn never matched.

Both videos end in KiCad. "Open in KiCad" starts the schematic editor, and `kicad.mjs`
records its window on the desktop (ffmpeg `gdigrab`, Windows). The short video then clicks
"Open PCB" and records the PCB editor the same way (decision 0036). `compose.mjs` puts each
clip in where its click happened, with a cut to its title block. Leave the screen alone
for those ~40 s. `npm run video:test` checks how `compose.mjs` cuts a take.

The long demo video (the demo assistant, ~6 min; recorded and checked, not published):

1. Start the app on fresh seed data: `start.cmd video`, answer `n` to Dahl and to Groq, then
   `d` (demo).
2. `npm run video:demo` writes these files to `out/demo/`:
   - `take.webm` and `video.mp4`;
   - `subtitles.en.srt`;
   - `events.json`, `trace-turn-N.json` and `shown.json` (what the panel showed, with its
     source);
   - `cues.json`.
3. `npm run video:verify` re-checks the rows' order, compares every payload with the
   capture, and checks that no local path appears.

| File | Role |
|---|---|
| `storyboard.json` | The rows: trigger, subtitle, callouts, payload source |
| `record.spec.ts` | The take: guard, capture, conductor, scenes |
| `stage.html`, `stage.js` | App iframe, "Under the hood" panel, subtitles, slides |
| `lines.mjs` | `file:symbol` → current line and excerpt |
| `introspect.py` | FTS terms and BM25 ranking, intent label (read only, backend venv) |
| `storyboard-dahl.json` | The short video's rows, for Groq and Dahl (flexible: a real model's steps vary) |
| `kicad.mjs`, `cues-kicad.json` | The KiCad ending: window capture of each editor, its zoom and subtitles |
| `cues.mjs`, `compose.mjs` | Cues, checks, gap cuts, `.mp4`, `.srt`, the README copy (ffmpeg) |

Every take reserves a new SAP number and creates a design. In `start.cmd video` mode that
happens in `data-video/`, which the next start deletes, so a take never shows the leftovers
of an earlier one (duplicate names, high numbers). With `VIDEO_OPEN_KICAD=0` the take does
not click **Open in KiCad**. The end card shows the repo, `VIDEO_AUTHOR` and
`VIDEO_LINKEDIN`.
