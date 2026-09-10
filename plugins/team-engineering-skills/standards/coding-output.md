# Coding and output standard

Owner: Suppacha. Baseline 2.0.0.

- Inspect relevant project instructions and existing patterns first. Preserve unrelated or uncommitted user changes.
- Keep changes small and scoped. Add regression tests for changed behavior; prefer deterministic tests with synthetic data. Explain any untested path.
- Use existing formatters, linters and dependency controls. Do not silently introduce a new framework, service, package or network permission.
- Review error paths, input validation, authorization, dependency risk and recovery behavior in proportion to the task.
- Before claiming completion, run appropriate checks and inspect their exit codes and results. Report skipped checks, environment limits and remaining risk separately from passes.
- Final output states the outcome, changed files, verification evidence and limitations. Link evidence without secrets; do not dump raw logs or private prompt history.
- For a pilot, manually record client/version, framework version, sanitized task category, selected skill, outcome and checks in the team's approved location. Do not auto-upload usage.
- Submit changes through a reviewed PR with owner sign-off and release notes. Escalate conflicts or unclear authority before expanding scope.
