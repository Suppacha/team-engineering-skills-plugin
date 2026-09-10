---
name: load-testing
description: Use when planning, scripting, running, troubleshooting, reviewing, or reporting load, performance, stress, spike, soak, endurance, capacity, scalability, concurrency, throughput, or latency tests (including โหลดเทสต์ and ทดสอบโหลด) with k6, JMeter, Locust, Gatling, Artillery, or an existing project tool.
---

# Load Testing

Treat a load-test result as an auditable decision, not merely a traffic-generator output. Prefer the project's existing tool and conventions. Do not migrate tools without a concrete benefit.

## Non-negotiable gates

- Run against production only with explicit authorization naming the target, window, traffic ceiling, monitoring owner, and stop authority. Otherwise prepare artifacts or use an approved non-production environment.
- Keep passwords, tokens, cookies, API keys, personal data, and private payloads in environment variables or an approved secret store. Never print or publish them. Redact shared artifacts.
- Never start a meaningful load until a one-user/one-iteration functional check passes. Separate script defects from system performance.
- For mutating flows, establish test-data ownership, idempotency, expected side effects, cooldowns, cleanup/rollback, and downstream impact before execution.
- Refuse to publish a pass/fail capacity verdict when the run is invalid, incomplete, unreconciled, or missing required telemetry.

## Establish the test contract

Inspect the repository, runbook, existing scripts, and monitoring first. Record:

1. Business question and critical user journeys.
2. Approved target environment and authorization boundary.
3. Workload model: arrival rate or concurrent users, journey mix, think time, ramp, steady duration, and test-data cardinality. Do not treat VUs, concurrency, RPS, and completed journeys as interchangeable.
4. Acceptance thresholds for journey success, error rate, throughput, and p50/p95/p99 latency. If thresholds are absent, label proposed values as assumptions; do not invent an SLA.
5. Required client, service, host, database, cache, queue, and dependency telemetry.
6. Safety ceilings, abort signals, monitoring owner, and recovery plan.

Ask only for missing facts that block safe execution or materially change the design. Continue with clearly labeled assumptions when safe.

Use terms precisely: VUs are tool workers, concurrency is simultaneous in-flight work/users, arrival rate is new iterations per time unit, RPS is measured requests per second, and journeys are business-flow executions. Derive relationships from measured journey duration and mix; do not convert them with an unexplained rule of thumb.

## Build the scenario faithfully

- Model complete business journeys, not isolated requests, unless endpoint isolation is the stated goal.
- Add assertions for status, schema, and business outcome. A fast incorrect response is a failure.
- Correlate dynamic tokens and identifiers; parameterize accounts and data; preserve realistic caching and session behavior.
- Prevent accidental amplification from retries, login-per-request, shared credentials, zero think time, or unbounded data reuse.
- Tag journey, request, operation, and outcome so failures and latency can be attributed.
- Pin tool/runtime versions and make configuration reproducible without embedding environment-specific secrets.
- Add static checks or dry runs that cannot generate real load. Do not use a live readiness, pilot, or full run merely to verify implementation.

## Execute in controlled stages

Proceed only while the prior gate is valid:

1. **Static validation** — syntax, configuration, secret scan, target allowlist, and destructive-operation review.
2. **Preflight** — network, test data, disk, clocks, credentials, telemetry, collectors, and load-generator capacity.
3. **Smoke** — 1 VU and 1–5 iterations; validate every journey and evidence path.
4. **Baseline** — low rate; capture normal latency, error distribution, and resource behavior.
5. **Load** — ramp gradually to the approved target and hold long enough for steady-state evidence.
6. **Stress/spike/soak/capacity** — run only when it answers the test contract; isolate from the standard load verdict.
7. **Repeat** — rerun important findings to distinguish reproducible behavior from noise.

Use fail-closed stop rules. Abort or invalidate on critical alarms, data corruption, uncontrolled error growth, generator saturation, collector loss, target mismatch, broad network/VPN loss, or loss of operator control. Preserve partial evidence, but do not call an invalid run a system failure.

## Analyze evidence

Reconcile intended traffic, started journeys, completed journeys, dropped work, retries, and request counts. Distinguish:

- `PASS`: valid run and every approved threshold passes.
- `FAIL`: valid run and at least one approved threshold fails.
- `INVALID`: conditions cannot support a capacity judgment.
- `INCONCLUSIVE`: valid evidence exists but the contract or attribution is insufficient.

Report throughput, journey success, p50/p95/p99, errors by type and time, saturation, resource headroom, and dependency behavior. Correlate client and server timelines. Do not claim root cause from client-only symptoms; state observation, evidence, inference, and confidence separately. Check for coordinated omission or insufficient load-generator capacity when results look unexpectedly good.

## Deliver a decision-ready package

Use [references/report-template.md](references/report-template.md) when producing a report. Include exact commands or CI job, sanitized configuration, version/commit, timestamps and timezone, workload stages, thresholds, raw artifact locations/checksums, deviations, incident timeline, bottlenecks, recommendations, owners, and a reproducible rerun path.

Recommend `GO`, `CONDITIONAL GO`, or `NO-GO` only from a valid run and explicit criteria. Otherwise report `NO VERDICT — INVALID/INCONCLUSIVE`. Never equate “the tool exited zero” with production readiness.

Keep the decisions separate: `EXECUTION BLOCKED` means the requested test is not authorized or safe to start; it does not mean the system failed capacity. Emergency or time pressure never waives the authorization, telemetry, data-safety, and stop-control gates. Record authorization using the organization's accepted change/ticket/approval mechanism.

Before declaring completion, run the project's tests/static checks, validate the skill or script syntax, scan deliverables for secrets, and verify that the report's numbers reconcile with the authoritative raw results.
