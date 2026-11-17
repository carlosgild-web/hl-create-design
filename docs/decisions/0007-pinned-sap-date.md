# 0007: Pin the mock SAP's date with `SAP_TODAY`

**Status:** accepted (2026-11-17)

## Context

A design number carries the year it was reserved (`HL-HW-26-0042`), and a reservation
books to the department's default project (WBS) for that year. The seed data has
default projects for 2023 to 2026 only, and the whole demo story (manual, README, tests,
the "next number is 0042" scenario) is set in November 2026.

From 1 January 2027 a mock that used the real date would issue `HL-HW-27-0001` and find
no default project for 2027. The online demo would break, or tell a different story
from its own documentation.

## Decision

- New setting `SAP_TODAY` (a date, empty by default). When set, the mock uses it as
  "today" for the reservation year, the creation date and each department's default
  project. When empty, it uses the real date.
- When a year has no default project, a reservation fails with an SAP error
  (`ZHL_PLM/011`, "contact Product Engineering"), as the manual describes for missing
  master data. The mock does not invent projects.
- `compose.yaml` and the online demo (Phase 7) set `SAP_TODAY=2026-11-17`. Tests set it
  through their own settings.

## Consequences

- The demo story stays the same over time, and the tests don't depend on the calendar.
- With `SAP_TODAY` set, the dates SAP returns can differ from the backend's issue date on
  the title block. That is acceptable for a mock; the backend never reads the mock's clock.
- Running the mock without `SAP_TODAY` after 2026 shows the `ZHL_PLM/011` error path,
  which is also worth demonstrating.
