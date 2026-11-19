# 0013: Packaging (Phase 7)

**Status:** accepted (2026-11-19)

## Decision

1. **One app image** based on `kicad/kicad:9.0` (Debian 12, Python 3.11, `kicad-cli`), built
   in two stages: Node builds the React app, then the KiCad image gets a venv with the
   backend. The image installs `python3-venv`/`pip` because the KiCad image has neither.
2. **The backend serves the built UI** at `/` (`FRONTEND_DIR`, default `frontend/dist`;
   `mount_frontend` in `app/main.py`, registered last so `/api/*` always wins, unknown paths
   fall back to `index.html`, nothing outside the folder is readable). One container
   means one URL for the public demo; the Vite dev proxy is unchanged.
3. **`sap-mock` has its own small image** (`python:3.11-slim`), so the app and the mock stay
   separate services, as in invariant 4.
4. **`compose.yaml`** wires app + sap-mock (+ an `ollama` profile). Settings are explicit
   `environment:` entries with defaults (`LLM_PROVIDER=fake`, `SAP_TODAY=2026-11-17`, decision
   0007), so a developer's local `.env` (Windows `KICAD_CLI`, `localhost` URLs) never leaks
   into the containers. Data lives in named volumes.
5. **CI job `kicad-image`** builds the image, runs the `kicad`-marked tests inside it
   (they were skipped everywhere before), generates a design and uploads `after.pdf`.

## No hosted demo

The owner decided (2026-11-19) not to host a public demo. Phase 8 publishes a demo video
and the repo; anyone who wants to try it clones and runs `start.cmd` / `start.sh`. The
per-IP rate limit, daily token cap and cleanup job from decision 0011 stay (off by default)
for anyone who hosts it themselves; the image honours `PORT`.
