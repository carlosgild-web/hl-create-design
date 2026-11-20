# 0014: Hilda & Luna palette for the UI (Phase 8)

**Status:** accepted (2026-11-20)

## Context

Phase 5 shipped the default shadcn neutral theme and left the brand palette open. This tool
belongs to the same fictional company as `luna-hybrid-agent` (decision 0006 reuses its logo),
so the UI should look like part of the same portfolio.

## Decision

1. **Same tokens as `luna-hybrid-agent`'s employee portal** (`--color-hl-*`): night `#121735`,
   cobalt `#2f45b5`, amber `#e39a2d`, opal `#e7a3a6`, sea `#5fae9c`, moon `#eef0f8`, on a
   moonstone background `#f3f5f8` with ink text `#18204a`.
2. **shadcn tokens are mapped, not replaced**: cobalt is `primary` and `ring`, moonstone is
   `background`, white is `card`. A dark theme (night background) is defined too, although
   the UI has no switch yet. Components keep using semantic tokens (`bg-primary`, `bg-muted`).
3. **Brand tokens only where semantics do not reach:** the demo banner (night), the
   assistant-suggestion highlight and the confirmation card (amber), the SAP status badges
   (sea / cobalt / destructive / muted). Two derived "ink" colors (`hl-amber-ink` `#8a5208`,
   `hl-sea-ink` `#2b6b5b`) keep small text readable on white.
4. **Fonts unchanged** (Geist, already bundled). Luna's Fraunces/Figtree would add two
   font packages for little gain.

## Consequences

No new dependency. Lint, unit tests, build and the Playwright e2e pass unchanged, because no
test depends on colors.
