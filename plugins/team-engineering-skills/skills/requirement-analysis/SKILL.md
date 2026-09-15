---
name: requirement-analysis
description: Use when analyzing product or business needs, clarifying scope, or turning authorized discovery evidence into traceable requirements.
---

# Requirement Analysis

## Overview

Produce reviewable requirements whose evidence, assumptions, and open questions are visibly distinct. Preserve known identifiers and make gaps explicit instead of inventing stakeholder decisions or TOR references.

## Workflow

1. Confirm the requested product area, audience, scope, out-of-scope items, and authorized evidence. Record how each source was gathered.
2. Separate confirmed source statements from analyst interpretation, assumptions, missing information, and questions for the BA or stakeholder.
3. Describe problems, impacts, and constraints before proposing requirements. Assign stable `REQ-*` and `UC-*` identifiers where the project has none.
4. State each business or functional requirement as a testable outcome. Add only relevant non-functional requirements.
5. Express business rules as condition and outcome pairs. Write measurable acceptance criteria linked to a requirement or use case.
6. Trace many-to-many references explicitly. Report missing or duplicate references and requirements that do not need a UI.
7. Record only reviews, versions, and approvals that actually occurred.

## Evidence contract

| Classification | Required handling |
| --- | --- |
| Confirmed source | Identify the authorized source and retain its meaning. |
| Analyst interpretation | Label it as analysis, not a stakeholder statement. |
| Assumption | State what must be validated and who can answer. |
| Missing information | Leave the requirement incomplete and ask a focused question. |
| TOR reference | Include only a TOR identifier or section present in the supplied evidence; otherwise write `Not provided`. |

Do not read unrelated files, infer business rules from UI appearance, or claim approval. Do not upload source material or create tickets unless the user separately authorizes that action.

## Deliverables

- Start from the [requirements template](assets/templates/requirements-template.md) when a reusable document is requested.
- Use the [synthetic appointment example](examples/appointment-booking-requirements.md) to check identifier and evidence shape, never as project evidence.
- Hand unresolved questions and explicit references to downstream UI and test-design work.

## Quality check

Confirm that scope is bounded; sources and assumptions are distinguishable; rules and acceptance criteria are testable; every TOR citation exists; trace links are explicit; and no review, execution, or approval status was fabricated.
