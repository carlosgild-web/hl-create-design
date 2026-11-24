# 0015: "How this demo works" guide (Phase 8)

**Status:** accepted (2026-11-20)

## Context

Phase 5 left only a one-line banner. A reviewer opening the project needs to know in
seconds that it is a fictional demo, what to click, and what the guardrails are. The
`portfolio-demo-guide` pattern from the earlier portfolio projects does that.

## Decision

1. **Same pattern, adapted to this app**: a banner (replaces the old one), a right-side
   panel ("What this is", "The path", "Things to try", GitHub link) and a "Demo guide" pill
   when hidden, remembered in `localStorage`. The text is one config object in ES and EN
   (`frontend/src/demo-guide/guide.config.ts`).
2. **Neutral on purpose**: zinc, dashed border, monospace tag "Portfolio demo · not part of
   the company design". It is about the project, so it never wears the Hilda & Luna colors.
3. **Nothing new installed**: the panel uses the existing shadcn `Sheet`, icons come from
   `lucide-react`, language from the app's own i18n. There is no router, so no per-page
   "you are here" marker and no entry strip, only the in-app banner.
4. Honest content: the model line says "Ollama, Groq, or a scripted model with no key",
   and the things to try include a refusal and a prompt-injection name.

## Consequences

The old `demo.banner` / `demo.dismiss` i18n keys are gone. 4 unit tests cover open, Escape,
hide/remember/restore and Spanish.
