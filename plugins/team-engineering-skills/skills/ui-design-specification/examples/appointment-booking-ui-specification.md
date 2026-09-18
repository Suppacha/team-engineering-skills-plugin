# Synthetic example: appointment booking UI

This fictional example demonstrates structure only. It is not a tested or approved design.

## Trace and roles

- `REQ-001`: A customer can book a displayed available time.
- `UC-001`: Book an available appointment.
- `UI-001`: Appointment time selection, available to the synthetic `Customer` role.
- Downstream references: `TS-001` and `TC-001`.

## Workflow

1. `UI-001` displays available dates and times.
2. The customer selects one time and enters the required contact name.
3. The customer confirms. Success shows a synthetic confirmation identifier; a conflict returns to refreshed availability.

## Text wireframe

```text
Appointment booking
[Date selector]
[Available time options]
[Contact name                 ]
[Confirm appointment]
[Status or validation message]
```

The wireframe does not define behavior by itself.

## Selected behavior

| Element | Validation or action | Outcome |
| --- | --- | --- |
| Date selector | A date must be selected before times are requested. | Loading, empty, or available-time state appears. |
| Available time | Exactly one displayed time can be selected. | Confirm becomes available when other required input is valid. |
| Contact name | Required; formatting rules remain an open decision. | Missing input shows a field-linked error and moves focus to the field. |
| Confirm | References `REQ-001`, `UC-001`. | Success identifies the booking; a conflict refreshes availability without claiming success. |

## States

- Loading: time options are unavailable and a named loading status is announced.
- Empty: no options appear; the customer can select another date.
- Error: the cause and recovery action are shown without exposing internal details.
- Success: the booking identifier is shown once the system confirms the booking.
- Access denied: not applicable to the public synthetic customer flow; privileged management UI is out of scope.

No component library is selected in this example.
