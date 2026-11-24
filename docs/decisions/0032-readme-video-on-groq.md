# 0032: The README video runs on Groq; one video is published

**Status:** accepted (2026-11-24). Amends 0028 and 0029.

## Context

Decision 0028 planned two explainer videos: one with the demo assistant and one with Ollama.
Decision 0029 then picked Dahl (GLM-5.3 Flash) for the short README video. On 2026-11-24 two
Dahl takes failed because the free model was at capacity. A third take, which fell back to
another model (decision 0031), timed out after the reservation. Groq's `gpt-oss-120b`
recorded the same storyboard on the first take after one app fix: a reservation now fills
the form's name.

The takes also showed that recording against the everyday `data/` makes a video look buggy.
Earlier takes had left designs in the mock SAP with the same name as the ones in the video,
so the cards showed `name_exists_in_sap` warnings that were correct but confusing.

## Decision

1. **One published video:** the short one, about 2 minutes, with a real model on **Groq**
   (`npm run video:groq`). It plays inline in the README. The long demo video
   (`npm run video:demo`, 6 minutes) is still recorded and checked by the same tooling. It is
   not published.
2. **No Ollama video.** On this machine (7 GB RAM) a local model is too slow for a clean take.
   The tooling still supports Dahl (`npm run video:dahl`); the storyboard's `providers` entry
   sets the banner and the models for each provider.
3. **Fresh data for every take:** `start.cmd video` deletes and re-seeds `data-video/` and
   points both services at it, through `DATA_DIR` and `DESIGNS_ROOT`. The everyday `data/` is
   not touched.
4. Fixes found in the takes and kept in the product:
   - a card that the model opens fills the form with its values, as the assistant's;
   - a confirmed reservation fills the name and an empty designer;
   - the chat renders `**bold**` and `` `code` ``;
   - placeholders read "e.g. …";
   - `<think>` blocks are removed from replies.

## Consequences

- The video's model (Groq `gpt-oss-120b`) is not the one in the Phase 9 eval table (Dahl,
  GLM-5.3 Flash). The banner in the video names the model, and `docs/video.md` says so.
- A take reserves numbers from the seed. Both recorded takes reserved HL-HW-26-0042, the
  number the README and the manual use as their example.
