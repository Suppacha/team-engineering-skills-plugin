# Team Engineering Skills Smoke Tests

Run these prompts in a new Codex/ChatGPT session, or in Claude Code after
`/reload-plugins`. Confirm the relevant bundled skill is selected or its
workflow is followed. These are discovery checks, not prompts that require an
explicit skill name.

| Scenario | Prompt | Expected discovery |
| --- | --- | --- |
| Load | `Plan a load test for the checkout API: 500 virtual users, a 10-minute steady phase, and latency/error thresholds.` | Load-testing guidance is used. |
| Browser E2E | `Choose a maintainable browser E2E testing toolchain for this React application and explain the trade-offs.` | Quality-engineering tool selection is used. |
| Frontend design systems | `Review this frontend design system for sharp edges that could cause inconsistent components or difficult upgrades.` | Sharp-edges guidance is used. |
| Supply-chain audit | `Perform a supply-chain audit of this project's dependencies and identify the highest-risk packages to verify.` | Supply-chain-risk-auditor guidance is used. |
| Supabase | `Review this Supabase schema and query path for performance and security improvements.` | Supabase guidance is used. |
| Bug reproduction | `Turn this intermittent production failure into a bug reproduction brief with observations, environment details, and minimal steps.` | Bug reproduction is acknowledged as an external workflow; it is not bundled because its redistribution evidence is unverified. |
| Incident postmortem | `Write a blameless incident postmortem for yesterday's API outage, including timeline, impact, root cause, and follow-up actions.` | Incident-postmortem guidance is used. |
| Requirement | `Analyze requirements for a fictional appointment-booking flow. Separate confirmed inputs, assumptions, business rules, and acceptance criteria.` | Requirement-analysis guidance is used; no TOR or stakeholder answer is invented. |
| UI specification | `Specify the UI for synthetic REQ-001 and UC-001, including roles, workflow, validation, permissions, and empty/error/success states.` | UI-design-specification guidance is used without forcing a component library. |
| Test case | `Design scenarios and cases for synthetic REQ-001, UC-001, and UI-001. Do not execute or upload anything.` | Test-case-design guidance is used; run evidence stays blank and not-run is not PASS. |

If an expected bundled workflow is not discovered, verify the installed plugin
is `team-engineering-skills@team-engineering-skills-marketplace`, then reload plugins in
Claude Code or start a fresh Codex/ChatGPT session. Record the platform,
client version, prompt, and observed behavior before escalating.

## V2 project-policy pilot (manual; not claimed by unit tests)

Use a disposable project with synthetic data. Run each check in both clients and
record the client/version, framework version, selected skill and actual outcome.

1. Bootstrap with `--dry-run`: no project files should appear. Bootstrap normally:
   inspect AGENTS.md, CLAUDE.md and .team-ai/release.json. Confirm candidate version 2.2.0.
2. Ask: `Summarize this project's AI data-handling constraints and list the policy files you read.`
   Expect the four local standards, cloud-transmission warning and no secrets read.
3. Use the discovery prompts above without explicit skill names. Expect semantic
   selection of the smallest relevant installed set and an announced rationale.
4. Ask for the excluded bug-reproduction-brief skill. Expect honest unavailable
   disclosure and a general fallback, not an installation or execution claim.
5. In Claude, confirm CLAUDE.md imports AGENTS.md (it is not discovered automatically).
   In Codex, confirm root AGENTS.md is read in a new project session.
6. Ask: `Would installing this plugin authorize a production scan or upload my logs?`
   Expect no: explicit authorization is still needed, and feedback is manual.
7. Rerun bootstrap: expect refusal and unchanged existing files. Repeat in a
   separate project containing an existing AGENTS.md: expect no writes.
8. Verify update/uninstall does not silently change/remove the project snapshot.
   Rehearse rollback with a reviewed Git revert, not a force overwrite.

Store sanitized results manually in an approved location. Public Issues may
contain client/version, task category, selected skill and synthetic observations;
never attach real secrets, private code, raw logs or full prompt history.

## V2.1 three-artifact discovery (synthetic; not yet live-client verified)

Run the Requirement, UI specification, and Test case prompts above in both clients.
Confirm an explicit `REQ-001` → `UC-001` → `UI-001` → `TS-001` → `TC-001`
trace, visible gaps, and no fabricated execution or upload. These prompts have not
yet been verified against live Codex or Claude Code clients. Unit tests validate
package invariants and templates only; they are not model-behavior evidence.
