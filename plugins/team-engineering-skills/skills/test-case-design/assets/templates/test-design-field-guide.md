# Test design template field guide

The CSV files and workbook preserve compatibility header names and order. They contain headers only and no execution evidence.

## Test Scenario

Use one row per scenario. `Scenario ID` is a stable `TS-*` identifier. Record a TOR value only when the supplied evidence contains that exact reference. `Scenario Status` can describe design readiness or an aggregate execution state only when that state is supported by the visible case results. `Upload jira` records a known upload state; it never initiates an upload.

## Test Case

Use one row per deterministic case. `Scenario ID` links the parent scenario, and `Test Case ID` is a stable `TC-*` identifier. Keep numbered actions in `Test Steps`; put observable outcomes in `Expected Result`.

For compatibility, `Scenario Status` in this sheet means the individual test-case execution result. Use `Not Run` before execution, not `PASS`. Leave `Actual Result`, `Tested By`, and `Test Date` blank until a real run supplies evidence. Keep `Upload jira` blank or use a truthful recorded state; filling it does not authorize any external action.

## Cross-artifact mapping

Do not add trace columns to the 25-column Test Case schema without an approved schema change. Maintain a separate mapping artifact when many-to-many links are needed:

| Requirement | Use case | UI | Test scenario | Test case |
| --- | --- | --- | --- | --- |
| REQ-001 | UC-001 | UI-001 | TS-001 | TC-001 |

Identifiers must be explicit. Matching numeric suffixes alone does not prove a relationship.
