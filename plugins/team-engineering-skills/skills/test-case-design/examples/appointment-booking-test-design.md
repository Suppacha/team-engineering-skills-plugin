# Synthetic example: appointment booking test design

This fictional example is design evidence only. No case was executed or uploaded.

## Trace mapping

| Requirement | Use case | UI | Test scenario | Test case |
| --- | --- | --- | --- | --- |
| REQ-001 | UC-001 | UI-001 | TS-001 | TC-001 |

## Scenario TS-001

- Name: Confirm an available appointment.
- Preconditions: Synthetic appointment availability exists and `UI-001` is reachable.
- Expected result: Supported booking outcomes follow `REQ-001` and `UC-001` without double-booking a selected time.
- Coverage: `TC-001` is the positive path. Conflict, missing-input, boundary, and permission cases should be added only when the approved artifacts define those rules.

## Case TC-001

| Field | Synthetic value |
| --- | --- |
| Test Case Type | Positive |
| Preconditions | An available synthetic time `09:30` is displayed. |
| Test Data | Contact name `Sample Customer`; time `09:30`. |
| Test Steps | 1. Select `09:30`. 2. Enter `Sample Customer`. 3. Confirm the appointment. |
| Expected Result | A confirmation identifier is shown and `09:30` is no longer displayed as available. |
| Actual Result | |
| Tested By | |
| Test Date | |
| Scenario Status | Not Run (individual case result) |
| Upload jira | |

`Not Run` records the absence of execution; it is not a pass result.
