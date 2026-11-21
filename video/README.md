# Explainer videos

Records "From a question to an answer" from the running app (decision 0028). The full docs
come with the Ollama video (Phase 10, V6).

```bash
cd video && npm ci          # @playwright/test only; uses the installed Edge
npm run video:check         # every [file, symbol] in storyboard.json still resolves
npm run video:smoke         # 10 s: the 1920x1080 stage -> out/smoke/
```

The Demo video:

1. Start the app: `start.cmd`, answer `n` (no Groq), then `d` (demo).
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
| `cues.mjs`, `compose.mjs` | Cues, checks, `.mp4` and `.srt` (ffmpeg) |

Recording writes to the real `data/`: every take reserves a new SAP number and creates a
design. With `VIDEO_OPEN_KICAD=0` the take does not click **Open in KiCad**.
