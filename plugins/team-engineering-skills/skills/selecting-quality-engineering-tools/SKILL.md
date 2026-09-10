---
name: selecting-quality-engineering-tools
description: Use when choosing, adding, or combining Playwright, Robot Framework, Newman/Postman, Testcontainers, WireMock, Allure, k6, Locust, or OWASP ZAP for E2E, acceptance, API regression, integration, service virtualization, reporting, load, or security testing.
---

# Select Quality Engineering Tools

Choose the smallest complementary stack that proves the required risks. A repository link is not a reason to install a tool.

## Route by test boundary

| Need | Default fit | Boundary |
|---|---|---|
| Browser E2E and UI regression | Playwright | Prefer the existing project framework; use the standalone browser workflow below. An installed `playwright` skill is an optional enhancement. |
| Keyword-driven acceptance | Robot Framework | Choose when the project already uses Robot or readable keyword suites are a real team requirement. |
| Existing Postman API collection | Newman | Run the collection in CI; do not rewrite it solely to adopt another runner. |
| Java integration with real infrastructure | Testcontainers Java | Start disposable databases, brokers, or services through the project's test lifecycle. |
| Deterministic external HTTP behavior | WireMock | Stub dependencies, faults, and edge cases; do not mock the system under test. |
| Load, stress, spike, soak, or capacity | k6 or Locust | Preserve the existing tool; prefer k6 for JS/TS-oriented suites and Locust for Python-native suites. **REQUIRED SUB-SKILL:** Use `load-testing`. |
| Authorized web/API security scanning | OWASP ZAP | Separate passive/baseline and active scans; use the scoped workflow below. Installed `api-security` or `pentest-tools` skills are optional enhancements. |
| Cross-run presentation | Allure | Treat it as a reporting layer, never as the authoritative test result or raw evidence store. |
| Frontend component foundation | Project-appropriate design system | Follow the selection guidance below. An installed `choose-frontend-design-system` skill is an optional enhancement. |

## Standalone workflows

These workflows do not require the optional related skills to be installed.

- **Browser E2E:** Identify one critical user journey and its observable success and failure states. Reuse the project's browser runner and isolated test data. Prefer role/label locators, wait for observable application readiness instead of fixed sleeps, and assert user-visible outcomes. Run the focused test, inspect its exit status, and retain a failure trace or screenshot. Expand coverage only for distinct risks.
- **Security testing:** Confirm the authorized target, scope, credentials, and permitted scan mode. Begin with passive analysis of test-environment traffic; redact secrets in artifacts and manually validate findings. An active scan requires explicit approval for its target, rate ceiling, window, stop condition, and cleanup. Record reproducible evidence and limitations; neither scanner output nor a clean scan proves the absence of vulnerabilities.
- **Design-system selection:** Inspect existing components, design tokens, framework constraints, and brand requirements. Reuse a compatible installed system first. Compare candidates on accessibility (keyboard operation, focus, and semantics), theming, component coverage, maintenance, and integration cost. Validate one representative component against those needs before adding dependencies; document the choice and any uncovered requirements.

## Selection workflow

1. Inspect manifests, lockfiles, existing tests, CI, language, target environment, and installed commands.
2. Map each stated risk to one test boundary. Reuse the existing tool for that boundary unless migration has a measured benefit.
3. State the selected tools, why each is needed, which requested tools are skipped, and where results remain authoritative.
4. Install libraries in the target project with its package manager and lockfile. Keep global CLIs isolated; never add every tool to every project.
5. Run fast functional checks before integration/E2E, and functional readiness before load or active security tests. Parallelize only independent, non-competing stages.
6. Verify exit status, assertions, raw artifacts, environment identity, and report ingestion. A generated Allure report does not turn an invalid test into a pass.

## Guardrails

- Do not run load or active security tests against production without explicit target, window, ceiling, monitoring, stop authority, and cleanup approval.
- Do not combine Playwright and Robot, or k6 and Locust, for the same coverage merely to use both.
- Pin project dependencies and container images. Prefer disposable test data and deterministic stubs.
- Consult current official documentation before relying on install commands, versions, adapters, or APIs.
