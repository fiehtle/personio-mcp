# Write Capability Smoke Test (Live)

Generated: 2026-03-04 20:54:58Z
Endpoint: https://personio-mcp.onrender.com/mcp
Mode: Non-destructive intent (invalid payloads / bogus IDs), except one accidental destructive call noted below.

## Totals

- Tested write-like tools: 24
- Success: 1
- Forbidden (403): 1
- Not found (404/422 missing resource): 13
- Validation/request errors (400/415/422): 9
- Skipped intentionally: `create_person_and_employment` (high mutation risk)

## Critical note

- `delete_project` returned success when called with real project id `2318375`.
- Follow-up `get_project` for `2318375` returned 404 at 2026-03-04 20:55:15Z, indicating that project was deleted.

## Key findings

- Compensation write remains blocked in runtime behavior:
  - `create_compensation` -> HTTP 403 Forbidden
- Many write endpoints are reachable and pass auth, then fail on validation or missing resources.
- OAuth token scopes include `personio:compensations:write` and other write scopes, so runtime 403 likely reflects tenant-level business authorization rather than missing OAuth scope string.

## Suggested operational guardrails

1. Never call any `delete_*` tool without explicit user confirmation.
2. For any write tool, first run read preflight and display exact target IDs.
3. Require an explicit confirmation token (`YES`) before sending write requests.
4. Prefer invalid-payload tests over real-resource IDs when probing capability.
