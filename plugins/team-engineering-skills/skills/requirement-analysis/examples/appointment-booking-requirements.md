# Synthetic example: appointment booking

This example is fictional and contains no source project content.

## Evidence

| Source ID | Classification | Statement |
| --- | --- | --- |
| SRC-001 | Synthetic confirmed source | A fictional service owner asks customers to select an available appointment time and receive a confirmation. |
| GAP-001 | Assumption requiring validation | The duration of a reservation hold is unknown. |

## Requirement and rule

| ID | Statement | Evidence | TOR reference |
| --- | --- | --- | --- |
| REQ-001 | A customer can book one displayed available appointment time. | SRC-001 | Not provided |
| BR-001 | When a booking is confirmed, the selected time is no longer displayed as available. | SRC-001 | Not provided |

## Use case and acceptance criterion

- `UC-001`: Book an available appointment; references `REQ-001`.
- `AC-001`: Given an available time, when the customer confirms valid details, then the booking is recorded and a confirmation identifier is shown.

## Proposed downstream trace

`REQ-001` → `UC-001` → `UI-001` → `TS-001` → `TC-001`

The downstream identifiers are explicit planning references, not evidence that UI design, testing, or execution already occurred.
