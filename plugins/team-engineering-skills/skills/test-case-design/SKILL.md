---
name: test-case-design
description: Use when deriving traceable manual test scenarios and deterministic test cases from approved requirements, use cases, workflows, or UI specifications.
---

# Test Case Design

## Overview

Design reproducible tests from supplied evidence without implying execution. Preserve the two-sheet compatibility headers and keep cross-artifact mapping separate from the 25-column Test Case schema.

## Workflow

1. Read confirmed requirements, business rules, acceptance criteria, use cases, workflows, and UI specifications. List gaps instead of inventing missing behavior.
2. Assign stable `TS-*` scenario and `TC-*` case identifiers. Store explicit many-to-many references to `REQ-*`, `UC-*`, and `UI-*` outside the compatibility columns when needed.
3. Select positive, negative, boundary, and permission coverage according to evidence and risk. Do not add a category when no supported behavior exists to test.
4. Align preconditions, fictional test data, deterministic numbered steps, and observable expected results. One action belongs in each step; expected results describe externally verifiable outcomes.
5. Review duplicate IDs, missing references, ambiguous outcomes, destructive setup, credentials, and environment assumptions.
6. Export the requested format without changing execution evidence or contacting an issue tracker.

## Execution-evidence contract

- Leave `Actual Result`, `Tested By`, and `Test Date` blank until a real execution occurs.
- A designed but unexecuted case is `Not Run`, never `PASS`.
- In the Test Case sheet, the compatibility column `Scenario Status` records the individual case execution result. Document this meaning without silently renaming the header.
- Aggregate a scenario only from visible case outcomes. Pending, blocked, failed, and not-run cases cannot be collapsed into pass.
- `Upload jira` is a data field only. It does not authorize login, upload, ticket creation, or any external connection.

## Templates and example

- [Test Scenario header CSV](assets/templates/test-scenario-header.csv)
- [Test Case header CSV](assets/templates/test-case-header.csv)
- [Blank two-sheet workbook](assets/templates/test-design-template.xlsx)
- [Template field guide](assets/templates/test-design-field-guide.md)
- [Synthetic appointment example](examples/appointment-booking-test-design.md)

Copy a template before populating it. Use only fictional data and never include real credentials.

## Quality check

Confirm header order, unique identifiers, upstream references, risk-appropriate coverage, deterministic steps, observable expected results, fictional data, blank execution evidence, honest not-run status, transparent aggregation, and no upload side effect.
