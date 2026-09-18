---
name: ui-design-specification
description: Use when specifying screens, user flows, interaction states, validation, permissions, or responsive and accessible behavior from approved requirements.
---

# UI Design Specification

## Overview

Turn confirmed requirements and use cases into an implementable, reviewable interface specification. A wireframe supports the specification; it does not replace written behavior, states, or trace references.

## Workflow

1. Read the approved requirements first. Identify user roles, `REQ-*` and `UC-*` references, business rules, constraints, and open questions.
2. List screens or views and assign stable `UI-*` identifiers. Do not create a screen for a requirement that has no user-interface behavior.
3. Specify navigation and the task workflow, including entry, exit, cancellation, recovery, and permission boundaries.
4. For each screen, describe fields, data meaning, actions, validation, permissions, and the outcome after each action.
5. Cover applicable loading, empty, error, success, disabled, and access-denied states. Distinguish system behavior from unresolved design choices.
6. Add responsive and accessibility behavior required by the project, including keyboard order, focus, labels, announcements, contrast, and target sizes where relevant.
7. Link UI acceptance criteria and downstream test scenarios explicitly. Report missing or conflicting references.

## Design choices

Use the project's existing design system and components when available. If none is specified, describe interaction and visual intent without forcing Ant Design, MUI, or another library. Add sequence or data-flow diagrams only when asynchronous coordination, integration, or ordering is material to the behavior.

Never infer roles, permissions, validation rules, or success messages from a screenshot alone. Label proposals and assumptions for human review. Do not claim a prototype was tested, approved, or implemented unless evidence is supplied.

## Deliverables

- Start from the [UI specification template](assets/templates/ui-design-specification-template.md).
- Use the [synthetic appointment example](examples/appointment-booking-ui-specification.md) only to check document shape and traceability.
- Include a wireframe or prototype reference plus written behavior when the requested deliverable needs visual layout.

## Quality check

Confirm every screen names its roles and upstream references; workflows include alternate paths; fields, validation, actions, permissions, outcomes, and applicable states are specified; responsive/accessibility choices match project needs; open decisions are visible; and no component library or execution status was invented.
