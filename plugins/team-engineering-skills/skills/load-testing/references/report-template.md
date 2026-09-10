# Load-Test Decision Report

Use this template only after determining the authoritative artifacts for the current run. Remove sections that do not apply; never fill missing evidence with guesses.

## 1. Executive decision

- Decision: `GO | CONDITIONAL GO | NO-GO | NO VERDICT`
- Run classification: `PASS | FAIL | INVALID | INCONCLUSIVE`
- Tested capacity/workload:
- Primary reason:
- Conditions, remediation owners, and due dates:

## 2. Test contract

| Item | Approved value | Actual value | Deviation/impact |
|---|---|---|---|
| Environment and target | | | |
| Business journeys and mix | | | |
| Arrival rate/concurrency | | | |
| Ramp, hold, and total duration | | | |
| Dataset/accounts | | | |
| Monitoring and stop authority | | | |

List authorization reference and execution window without exposing credentials or private infrastructure details.

## 3. Acceptance results

| Criterion | Threshold | Result | Status | Evidence |
|---|---:|---:|---|---|
| Journey success | | | | |
| Error rate | | | | |
| Throughput | | | | |
| p50 / p95 / p99 | | | | |
| Resource/headroom guardrail | | | | |
| Business/data integrity | | | | |

Do not silently substitute a measured metric for a differently defined threshold.

## 4. Traffic reconciliation

- Intended/started/completed/dropped journeys:
- Business requests, retries, authentication, and setup traffic:
- Count mismatches and explanation:
- Load-generator CPU, memory, network, and saturation assessment:

## 5. Timeline and evidence

Correlate workload stages with application, gateway, host, database, cache, queue, and downstream telemetry. List incidents, abort signals, collector gaps, network interruptions, and recovery events with timezone-aware timestamps.

## 6. Findings

For each finding:

- Observation:
- Supporting evidence:
- Likely cause and confidence:
- Alternative explanations:
- User/business impact:
- Recommended action, owner, and priority:

## 7. Validity and limitations

State missing telemetry, environment differences, warmed caches, shared test data, rate limiting, coordinated-omission risk, generator constraints, and any deviation from the approved contract. If any item prevents a capacity judgment, classify the run `INVALID` or `INCONCLUSIVE` and issue no readiness verdict.

## 8. Reproduction and artifact manifest

- Tool/runtime version and source commit:
- Sanitized configuration and exact command/CI job:
- Run ID, start/end time, and timezone:
- Raw result, log, dashboard snapshot, and report paths:
- Checksums or immutable artifact references:
- Secret/PII scan result:
