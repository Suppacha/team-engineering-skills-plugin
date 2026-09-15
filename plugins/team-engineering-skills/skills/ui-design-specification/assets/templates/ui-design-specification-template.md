# UI design specification

## Document control

| Field | Value |
| --- | --- |
| Product or project | |
| Version | |
| Status | Draft / In review / Approved |
| Requirements baseline | |
| Prepared by | |
| Last updated | |

Record only reviews and approvals that occurred.

## Design context

### Objective

### In-scope user tasks

### Out of scope

### Design system and platform constraints

Name the project-selected design system. If none is selected, record that as an open decision rather than forcing a library.

## Roles and permissions

| Role ID | Role | Allowed actions | Restricted actions | Source references |
| --- | --- | --- | --- | --- |
| ROLE-001 | | | | REQ-001 |

## Screen inventory

| UI ID | Screen or view | Roles | Requirement references | Use case references | Purpose |
| --- | --- | --- | --- | --- | --- |
| UI-001 | | ROLE-001 | REQ-001 | UC-001 | |

## Navigation and workflow

| Step | From | User action or system event | To | Alternate or recovery path | References |
| --- | --- | --- | --- | --- | --- |
| 1 | | | | | UC-001 |

Add a sequence or data-flow diagram only when ordering or integration behavior needs it.

## Screen specification: UI-001

### Purpose and references

- Roles:
- Requirements:
- Use cases:
- Entry conditions:
- Exit outcomes:

### Wireframe or prototype

Add an authorized local artifact or reviewed URL. The written specification below remains authoritative for behavior.

### Fields and content

| Element ID | Label or content | Data meaning | Required | Default | Editable by | Visibility rule |
| --- | --- | --- | --- | --- | --- | --- |
| EL-001 | | | Yes / No | | | |

### Validation

| Rule ID | Element | Trigger | Rule | User feedback | Requirement or business rule |
| --- | --- | --- | --- | --- | --- |
| VAL-001 | EL-001 | | | | REQ-001 |

### Actions and outcomes

| Action ID | Action | Available to | Preconditions | System outcome | User-visible outcome | Failure recovery |
| --- | --- | --- | --- | --- | --- | --- |
| ACT-001 | | ROLE-001 | | | | |

### Interface states

| State | Trigger | Visible content and controls | Allowed next actions | Accessibility behavior |
| --- | --- | --- | --- | --- |
| Loading | | | | |
| Empty | | | | |
| Error | | | | |
| Success | | | | |
| Access denied | | | | |

Remove states that do not apply and explain material omissions.

### Responsive behavior

| Viewport or capability | Layout and priority | Interaction changes | Preserved information |
| --- | --- | --- | --- |
| Small screen | | | |
| Large screen | | | |

### Accessibility

| Topic | Required behavior | Verification note |
| --- | --- | --- |
| Keyboard and focus | | |
| Names and instructions | | |
| Status and error announcements | | |
| Contrast and non-color cues | | |

### Acceptance criteria

| Criterion ID | Given | When | Then | Upstream reference | Downstream test reference |
| --- | --- | --- | --- | --- | --- |
| UI-AC-001 | | | | REQ-001 / UC-001 | TS-001 |

## Open decisions and assumptions

| ID | Type | Question or assumption | Decision owner | Impact | Resolution |
| --- | --- | --- | --- | --- | --- |
| UI-GAP-001 | Open decision / Assumption | | | | |

## Traceability

| Requirement | Use case | UI | Test scenario | Notes |
| --- | --- | --- | --- | --- |
| REQ-001 | UC-001 | UI-001 | TS-001 | |
