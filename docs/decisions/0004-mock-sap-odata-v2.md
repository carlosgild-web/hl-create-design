# 0004: Mock SAP as a separate service shaped like OData v2

**Status:** accepted (2026-11-17)

## Context

Design numbers, SAP material numbers and design statuses come from SAP in the story.
There is no real SAP to call. The mock should make the integration code look like code
that would work against a real SAP Gateway, because that is what a reviewer from an SAP
shop will check.

## Decision

- **A separate FastAPI service** in `sap-mock/`, with its own SQLite file, its own tests
  and its own container. The backend reaches it only over HTTP through `SapClient`
  (invariant 4). No shared code or database.
- **SAP Gateway conventions:** service path `/sap/opu/odata/sap/ZHL_PLM_DESIGN_SRV/`,
  entity sets `DesignSet` and `DepartmentSet`, `$metadata`, `$filter`/`$top`/`$format`,
  payloads wrapped in `{"d": ...}`, dates as `/Date(ms)/`, and SAP-style error bodies
  (`{"error": {"code": ..., "message": {"lang": ..., "value": ...}}}`).
- **Basic auth plus the CSRF handshake:** a `GET` with `x-csrf-token: Fetch` returns a
  token, and a `POST` without a valid token is rejected with 403, like a real Gateway.
- **Chaos switches** (`SAP_LATENCY_MS`, `SAP_FAIL_RATE`, a maintenance flag that returns
  503), so retries, timeouts and the assistant's error explanations can be demonstrated.

Only the subset the tool needs is implemented. It is not a general OData server.

## Consequences

- `SapClient` handles the token fetch, retries and error mapping that a real
  integration needs. Pointing `SAP_BASE_URL` at a real system would, in principle, need
  only a matching service.
- The service is labelled as a mock everywhere: in its README, API title and responses.
- An extra process to run locally. `compose.yaml` and the start scripts (Phase 7) start
  it with the app.
