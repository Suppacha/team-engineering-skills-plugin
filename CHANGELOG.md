# Changelog

All notable changes to this marketplace are documented here.

## 2.2.0 - 2026-09-17 (candidate; not activated)

- Adds fail-closed candidate, CI, approval, and stable-channel promotion gates with least-privilege release writes.
- Adds a reproducible allowlisted updater runtime ZIP, Personal macOS/Windows installation guide, and team-managed scheduler runbooks while leaving every activation and pilot result explicitly NOT RUN.
- Keeps company Workspace rollout paused and distinguishes installed state from proof that a new Codex Desktop chat loaded the update.
- Preserves all 15 skill payload hashes and skill versions; this candidate adds a local personal updater runtime and its tests, distribution, release controls, and documentation. Runtime implementation is not activation or native Desktop pilot evidence.

## 2.1.0 - 2026-09-15

- Fixes Windows skill-hash validation by using platform-independent, case-sensitive path-component ordering; existing registry hashes and skill payloads remain unchanged.
- Adds repository-owned `requirement-analysis`, `ui-design-specification`, and `test-case-design` skills with implicit invocation for Codex and Claude Code.
- Adds generic Markdown templates, synthetic appointment-booking trace examples, ordered Test Scenario/Test Case CSV schemas, and a new blank two-sheet XLSX template.
- Preserves not-run execution evidence and treats `Upload jira` as data rather than authorization for an external side effect.
- Keeps first-party canonical skills during synchronization without requiring global copies while leaving third-party payloads and license provenance unchanged.
- Adds a Thai three-artifact quickstart and synthetic manual discovery checks explicitly marked as not yet live-client verified.

## 2.0.0 - 2026-09-10

- Adds a Team AI Operating Framework: self-contained security, AI usage, data access and coding/output standards.
- Adds owned/versioned registry routes and drift checks for the unchanged 12 licensed skill payloads.
- Adds offline, no-overwrite project bootstrap with AGENTS.md, Claude @AGENTS.md adapter and policy/hash evidence.
- Adds CODEOWNERS, sanitized manual feedback/change forms, PR checklist, portable CI and a manually dispatched ZIP artifact workflow.
- Adds Thai public-GitHub quickstart, enforcement boundaries, migration/rollback and pilot checks.
- Hardens release file selection with a distribution allowlist and common secret-filename exclusions.

## 1.0.0 - 2026-09-09

- Initial release of `team-engineering-skills` through
  `team-engineering-skills-marketplace`.
- Packages the approved licensed set of 12 engineering skills.
- Adds local ZIP/local-path testing instructions and private-Git marketplace
  distribution guidance for Codex/ChatGPT and Claude Code.
- Adds repeatable skill-discovery smoke tests.
