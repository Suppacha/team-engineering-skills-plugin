# Team Plugin Auto-update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** สมาชิก Codex ใน Workspace บริษัทและ Claude Code รับเฉพาะรุ่นที่อนุมัติผ่าน native auto-update โดยไม่ต้องติดตั้งซ้ำทุก release

**Architecture:** Git branch `stable` คือช่องทางเผยแพร่ ใช้ gate แบบอ่านหลักฐานจาก GitHub และ protected environment ก่อน promotion ของ immutable SHA เดิม แยก pure validation, GitHub transport และการเขียน ref; ไม่รันโค้ดจาก candidate ขณะถือ credential เผยแพร่ การตั้งค่า Admin และ live pilot เป็นขั้นเปิดใช้งาน ไม่ใช่ผลลัพธ์อัตโนมัติของ CI

**Tech Stack:** Python 3.10+ standard library, unittest, Git, GitHub Actions/REST, native Workspace sync และ Claude Code marketplace; ไม่เพิ่ม updater runtime

**Spec:** [Approved design](../specs/2026-09-17-team-plugin-auto-update-design.md)

## Global Constraints

- Codex: เฉพาะการใช้งานใน Workspace บริษัท บน client/version ที่ผ่าน pilot บน macOS และ Windows ไม่รับรองบัญชีส่วนตัวหรือ CLI ทุกแบบเพียงเพราะล็อกอินบัญชีเดียวกัน
- Claude Code: Git marketplace ของทีม ตั้งค่าต่อเครื่อง/ผู้ใช้ OS และเปิด auto-update ของ marketplace
- รับเฉพาะรุ่นที่ผ่าน CI และผู้มีอำนาจอนุมัติแล้ว ไม่มี auto-publish ทุก commit
- ไม่สร้าง daemon, scheduled task, cron, launch agent, MCP service หรือ updater ใหม่บนเครื่องสมาชิก
- ไม่แก้ `AGENTS.md`, `CLAUDE.md`, `.team-ai` ของโปรเจกต์อัตโนมัติ การอัปเดต snapshot ยังต้อง review แยก
- ไม่เปิด telemetry หรือเปลี่ยนเงื่อนไข retention; หลักฐาน pilot เก็บโดยผู้ทดสอบ ไม่ส่งข้อมูลออกอัตโนมัติ
- repository `Suppacha/team-engineering-skills-plugin` เป็น public; plugin `team-engineering-skills`, marketplace `team-engineering-skills-marketplace`
- ทำงานบน feature branch/worktree แยก; ห้าม merge main, สร้าง/ขยับ stable, ออก release, เพิ่ม secrets/rulesets หรือแก้ Workspace จนกว่าจะได้อนุมัติ action นั้น
- ใช้เวอร์ชันเป้าหมาย 2.2.0 สำหรับ implementation; เป็น candidate ไม่ใช่การประกาศ release แล้ว อย่าแก้ skill version ถ้า payload ไม่เปลี่ยน
- รันคำสั่งจาก repository root; macOS ใช้ `python3`, Windows ใช้ `py -3` แทน ส่วน CI ใช้ `python` ตาม setup-python
- ตัวอย่าง Python tests ด้านล่างใช้ imports จาก `scripts` โดยเพิ่ม root/scripts เข้า sys.path ตาม pattern ที่ repository ใช้อยู่

## Dependency and file map

Task 1 → Task 2 → Task 3 → Task 5 → Task 6; Task 4 ทำแยกขนานกับ Tasks 1–3 ได้เมื่อ interfaces คงที่

| File | Responsibility |
| --- | --- |
| `scripts/release_policy.py` | Pure SHA/version/CI/evidence validation ไม่มี network หรือ write |
| `scripts/release_github.py` | GitHub API transport, pagination, timeout, fresh read และ redaction |
| `scripts/promote_release.py` | CLI orchestration, validation-before-write, promotion state machine |
| `config/release-policy.json` | Public policy ของ repo, workflow, environment, owner และ channel |
| `.github/workflows/promote.yml` | Read-only preflight → human gate → isolated writer |
| `tests/test_release_policy.py` | Pure contract rejection/acceptance tests |
| `tests/test_release_github.py` | Fake HTTP transport: real API shapes, pagination/failures |
| `tests/test_release_promotion.py` | Fake ref store: no-write-before-validation, concurrency/recovery |
| `tests/test_release_workflow.py` | Workflow safety/config regression tests |
| `config/claude-code-stable.example.json` | Example entry เท่านั้น ไม่ติดตั้งหรือ overwrite config |
| `docs/AUTO_UPDATE_ADMIN_TH.md` | Admin preconditions, permissions, migration/recovery |
| `docs/AUTO_UPDATE_PILOT_TH.md` | Manual four-pair test cases และหลักฐานที่ต้องบันทึก |
| `docs/QUICKSTART_TH.md`, `docs/MANUAL_SOURCES_TH.md`, `README.md` | End-user source of truth และข้อจำกัด |

---

### Task 1: Pure release policy and package comparison

**Files:** Create `scripts/release_policy.py`, `config/release-policy.json`, `tests/test_release_policy.py`.
**Consumes:** existing `framework.validate_release(Path)` จาก `plugins/team-engineering-skills/scripts/framework.py`; normalized GitHub evidence supplied by Task 2.
**Produces:** `validate_sha(value: str) -> str`, `version_tuple(value: str) -> tuple[int,int,int]`, `check_candidate(candidate: dict, baseline: dict, ci: dict) -> list[str]`, `check_approval(evidence: dict, policy: dict, run_id: int, candidate_sha: str) -> list[str]`. Empty errors means accepted; any missing field yields an explicit error, never default approval.

- [ ] Write failing tests using this minimal fixture contract:

```python
SHA = "a" * 40
CANDIDATE = {"sha": SHA, "on_main": True, "version": "2.2.0",
             "valid_package": True, "skills": {"test-case-design": {"version": "1.0.0", "hash": "1" * 64}}}
BASELINE = {"sha": "b" * 40, "version": "2.1.0", "skills": CANDIDATE["skills"]}
CI = {"sha": SHA, "event": "push", "branch": "main", "workflow": ".github/workflows/verify.yml",
      "status": "completed", "conclusion": "success", "attempt": 1,
      "jobs": {f"package ({os})": "success" for os in ("windows-latest", "macos-latest", "ubuntu-latest")}}

def test_reject_pending_windows(self):
    ci = {**CI, "jobs": {**CI["jobs"], "package (windows-latest)": "pending"}}
    self.assertTrue(check_candidate(CANDIDATE, BASELINE, ci))

def test_accept_exact_evidence(self):
    self.assertEqual(check_candidate(CANDIDATE, BASELINE, CI), [])
```

- [ ] Run `python3 -m unittest discover -s tests -p test_release_policy.py -v`; require RED for missing implementation.
- [ ] Implement narrow validators. SHA regex `^[0-9a-f]{40}$`; stable versions exactly three non-negative integer components without leading zeros/pre-release suffix. Numeric comparison, not string order. First promotion baseline comes from the reviewed 2.1.0 contract in history, not an implicit 0.0.0; missing valid baseline rejects. Compare changed payload hashes against increasing skill versions; added Skills need valid version/provenance; removed Skills require release notes and explicit release review.

```python
REQUIRED_JOBS = {"package (windows-latest)", "package (macos-latest)", "package (ubuntu-latest)"}
def jobs_pass(jobs):
    return isinstance(jobs, dict) and set(jobs) == REQUIRED_JOBS and all(v == "success" for v in jobs.values())
```

- [ ] Add table-driven negatives for malformed SHA, non-main, another SHA, event/workflow mismatch, missing/duplicate jobs, rerun not finished, cancelled/skipped/failure, version equal/lower, changed Skill hash without bump, invalid package. Model approval with run ID, candidate SHA, environment ID/name, approved reviewer GitHub ID and state; tests reject mismatches and arbitrary `approved: true`.
- [ ] Define policy JSON: schema_version 1; exact repository/name constants above; source_branch `main`; channel `stable`; environment `team-plugin-stable`; initial reviewer login `Suppacha` resolved to GitHub ID at activation. No credential fields.
- [ ] GREEN targeted tests and full `python3 scripts/verify-portable.py`; commit `feat: add fail-closed release policy checks`.

### Task 2: Evidence collection without publication authority

**Files:** Create `scripts/release_github.py`, `tests/test_release_github.py`.
**Consumes:** Task 1 policy; authenticated GitHub read access supplied by caller, never a token in input JSON.
**Produces:** `GitHubClient(request)` with `get_json(path)`, `get_pages(path)`, `collect_candidate(sha, baseline_sha) -> dict`, `collect_approval(run_id, candidate_sha) -> dict`, `read_stable() -> str | None`. Injectable `request(method, path, body=None) -> (status, headers, data)`; production host fixed to `api.github.com`.

- [ ] Write RED tests for two-page job listing and HTTP403/404/429/5xx; no unknown status is treated as a missing stable branch. Use fake transport:

```python
def test_auth_failure_is_not_first_release(self):
    def forbidden(method, path, body=None):
        return 403, {}, {"message": "Forbidden"}
    with self.assertRaises(RuntimeError):
        GitHubClient(forbidden).read_stable()
```

- [ ] Run `python3 -m unittest discover -s tests -p test_release_github.py -v`, confirm RED.
- [ ] Implement stdlib urllib transport with timeout, bounded body size, no credential-bearing cross-host redirect, bounded pagination, bounded retries only for safe GET; error text excludes Authorization/secrets.
- [ ] Fetch exact verify workflow runs for candidate SHA, event push/main; select latest run and latest attempt even if older run passed. Fetch all jobs for that attempt and validate repository/workflow identity before normalizing to Task 1 shape. Use real commit ancestry check for main/stable, not caller booleans. Extract manifests/registry as data at exact SHAs; verify allowlisted file payloads without executing scripts from candidates. An archive reader must reject traversal, links and unbounded contents.
- [ ] Read environment protection, effective rulesets and run review history from GitHub APIs; resolve reviewer IDs from actual settings and compare to approved activation policy. Unknown rule types/evidence shapes fail closed. Bind approval to the current promotion run's immutable input SHA, not review of a different run or commit. Missing API permissions are actionable failures, not bypasses.
- [ ] Test wrong repo, malicious pagination URL, old successful rerun, symlink archive, main movement and unreadable approval history. GREEN target/full tests; commit `feat: collect immutable GitHub release evidence`.

Official API sources to open during execution: [workflow runs/reviews](https://docs.github.com/en/rest/actions/workflow-runs), [environments](https://docs.github.com/en/rest/deployments/environments), [Git refs](https://docs.github.com/en/rest/git/refs), [rulesets](https://docs.github.com/en/rest/repos/rules). Test against current returned schemas; do not invent fields when a pilot API response differs.

### Task 3: Isolated promotion and approval-gated workflow

**Files:** Create `scripts/promote_release.py`, `.github/workflows/promote.yml`, `tests/test_release_promotion.py`, `tests/test_release_workflow.py`.
**Consumes:** Tasks 1–2; baseline/candidate versions, prior stable SHA, run approval evidence.
**Produces:** CLI `promote_release.py preflight --candidate SHA --output FILE` (no remote writes), `promote_release.py publish --candidate SHA --expected-stable SHA_OR_ABSENT --run-id ID`; `publish_release(client, record) -> dict` state result with `prepared`, `promoted`, `recorded` or explicit partial failure. Requires live revalidation regardless of input record.

- [ ] Write RED state tests using an in-memory fake client implementing read/create/update refs and release-record methods. `force=False` must be the only update mode:

```python
def test_stable_moved_aborts(self):
    client = FakePromotionClient(stable="c" * 40)
    with self.assertRaises(ValueError):
        publish_release(client, {"candidate_sha": "a" * 40, "previous_stable_sha": "b" * 40})
    self.assertEqual(client.writes, [])
```

- [ ] Run target discovery and confirm RED. Implement states: validate fresh evidence → persist prepared record → re-read stable → create first ref or PATCH `force:false` → verify exact remote SHA → mark release record promoted → report success. Record contains schema/version/candidate/previous SHA/run and CI URLs/approval identity/time, no worktree data. Persist as GitHub release metadata with tag fixed to candidate plus JSON asset; same version conflicting SHA rejects. A draft prepared record is not a published release. New immutable record finalizes only after promotion.
- [ ] Recovery tests: API timeout after write requires readback (never blindly retry), partial record failure after ref move reports partial state and repair instructions; retry same candidate can finalize matching record without re-promoting; new candidate cannot reuse prior approval. GitHub ref write is not claimed as CAS: concurrency + restricted sole writer + immediate pre-write check are prerequisites; recheck/refuse if protections absent. Ancestry check plus `force:false` rejects rewind/divergence.
- [ ] Workflow skeleton must include:

```yaml
on:
  workflow_dispatch:
    inputs:
      candidate_sha:
        required: true
        type: string
permissions:
  contents: read
  actions: read
concurrency:
  group: team-plugin-stable-promotion
  cancel-in-progress: false
```

- [ ] Implement read-only `preflight` job and dependent `publish` job with `environment: team-plugin-stable`, `if: github.ref == 'refs/heads/main'`, same immutable SHA input. Checkout trusted workflow revision (`github.sha`) with credentials not persisted; never checkout/run arbitrary candidate with writer credentials. Pass user input through environment/argv, not interpolated shell source. Repeat preflight after human approval. Pin third-party Actions to reviewed immutable SHAs obtained from upstream, not guessed values.
- [ ] Writer identity is an Admin-provisioned dedicated GitHub App restricted to this repo. Its environment-only key is unavailable before approval; scoped permission/ruleset design must pass Task 6 before activation. PR workflows receive no writer key/token. Never set broad repository bypass for ordinary Actions. If owner cannot provision a least-privilege protected writer, stop activation; do not silently use owner's PAT.
- [ ] Workflow tests parse YAML with a CI test-only parser and validate job dependencies, environment, permissions, default branch condition, no pull_request_target trigger, no force push, no candidate execution in privileged job. Add parser only to test dependencies and explicit CI install if needed; do not add runtime dependency to plugin. Test environment missing/unprotected rejects even though GitHub can auto-create named environments.
- [ ] GREEN pure/state/workflow tests and full suite; commit `feat: gate stable promotion on verified CI and release approval`.

### Task 4: Client configuration, migration and end-user instructions

**Files:** Create `config/claude-code-stable.example.json`, `docs/AUTO_UPDATE_ADMIN_TH.md`, `docs/AUTO_UPDATE_PILOT_TH.md`, `tests/test_auto_update_docs.py`; modify `docs/QUICKSTART_TH.md`, `docs/MANUAL_SOURCES_TH.md`, `README.md`.
**Consumes:** Stable channel/policy from Tasks 1–3, approved spec; may begin before coding finishes.
**Produces:** Non-executing config example + Thai user/admin documentation + blank pilot checklist, all marked not activated until evidence exists.

- [ ] Write failing config test: expected repository, `ref == "stable"`, `autoUpdate is True`, no `permissions`/`env` overrides and only team's marketplace entry. Confirm RED with `python3 -m unittest discover -s tests -p test_auto_update_docs.py -v`.
- [ ] Verify current official Claude settings schema before writing this example; if schema changed stop and revise this task explicitly:

```json
{
  "extraKnownMarketplaces": {
    "team-engineering-skills-marketplace": {
      "source": {"source": "github", "repo": "Suppacha/team-engineering-skills-plugin", "ref": "stable"},
      "autoUpdate": true
    }
  }
}
```

- [ ] Document initial install separately from auto-update; config entry alone does not install plugin. JSON is merge-only example; never replace user settings file. Explain one-time migration from ZIP source, same-name collision, supported uninstall/disable without deleting backup/project instructions. No account sync assumptions for Claude local installation.
- [ ] Codex Admin guide: company Workspace only, import repo root/ref stable, roles/access, read sync report, then member install/new session; daily sync is not immediate Push delivery. Do not promise CLI/IDE support without pilot. Existing private accounts remain outside assurance.
- [ ] User guide retains Quick Start + four Tool structure but marks new path “หลังผู้ดูแลเปิดใช้งานและผ่าน pilot”; keep working ZIP path available until activation. Distinguish installed/loaded/package/skill/project snapshot version. Keep Claude chat/ChatGPT cloud paths conditional and outside this auto-update release scope.
- [ ] Add manual pilot rows for all four OS/client pairs with fields version A/B, SHA/source, account-scope, automatic-check observation, installed evidence, loaded evidence, session/reload time, result and limitation. All results start NOT RUN, no telemetry uploader.
- [ ] Test links/config scope/NOT RUN labels; GREEN full suite; commit `docs: guide native stable-channel updates and migration`.

### Task 5: Versioned candidate and repository readiness

**Files:** Modify `plugins/team-engineering-skills/VERSION`, both plugin manifests, `registry.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, version assertions in `tests/test_package.py`, `tests/test_team_workflows.py` and any exact-version fixtures found by `rg`; update README/manual release labels to candidate 2.2.0.
**Consumes:** passing Tasks 1–4; no live stable publication.
**Produces:** coherent 2.2.0 candidate tested on CI, with old baseline fixtures preserved.

- [ ] Add failing test asserting all candidate package identity/version surfaces agree on 2.2.0. Retain frozen 2.0.0 migration fixture and original expected hashes; do not globally replace historical versions.

```python
self.assertEqual(candidate_versions, {"2.2.0"})
self.assertEqual(previous_contract["version"], "2.0.0")
```

- [ ] Run targeted tests RED; update exact candidate surfaces. Recompute hashes only for intentionally changed payloads; root docs/CI changes do not require changing skill payload hashes. Fail if a changed skill payload kept old version.
- [ ] Run `python3 scripts/verify-portable.py`, `bash scripts/verify-package.sh`, `bash scripts/build-release.sh`, `git diff --check`. Report optional validator skips accurately; inspect ZIP allowlist and no credentials/private artifacts.
- [ ] Independent spec/security-quality review of gate and privilege separation, then re-run all affected tests. Commit `chore: prepare 2.2.0 auto-update candidate`.
- [ ] Push development branch only when authorized; inspect exact head CI Windows/macOS/Ubuntu. Report Repository-ready only after verified results. Do not merge/open stable automatically. Existing PR1 still contains V2.1 work: choose a separate dependent PR for these changes and disclose its base rather than merging earlier work implicitly.

### Task 6: Admin activation and live certification (external gate)

**Files:** Update only sanitized results in `docs/AUTO_UPDATE_PILOT_TH.md` and setup instructions when observed behavior differs; private operational evidence stays outside public repo.
**Consumes:** repository-ready reviewed commit on main after user-approved merge; admin permission and consent for each access/config change.
**Produces:** Admin-configured → Pilot-verified → Team-enabled evidence, or explicit blocker without claiming auto-update complete.

- [ ] Read actual GitHub environment/rulesets before changes. Present exact requested permissions and reviewer/writer identities to Admin. Owner is initial release approver, not invented independent reviewer. Self-review prevention requires a separate available approver/dispatcher; never silently deadlock or weaken rules. Require audit-able owner approval even if owner dispatches.
- [ ] Admin configures environment `team-plugin-stable` with required reviewer and default-branch-only deployment; no bypass. Configure stable write/delete/force protection with dedicated writer permitted only for gated promotion. Read back effective settings. Negative integration test proves ordinary user/PR token cannot write stable; test in explicitly approved test scope, not by temporarily weakening production rules.
- [ ] Validate first promotion against baseline 2.1.0 from verified repository history; full main SHA and CI/approval evidence required. Ask user to approve concrete release action before publishing A. Do not create an empty/unvalidated stable branch as setup convenience.
- [ ] Set up only an approved pilot group on company Workspace and test Claude machines. Obtain authorization before import/grants/config edits. Capture source/conflicts and preserve old install backup. No member credentials requested or copied.
- [ ] Publish approved B with a higher version through the same gate. Observe automatic sync/update without manual update command. Permit session/reload only. Codex manual Sync now can diagnose but cannot count as automatic-update proof. If daily sync needs later follow-up, use product monitoring only after user requests/approves that follow-up; don't leave an untracked background loop.
- [ ] Run every pilot scenario: A→B automatic, offline/reconnect, failed sync, stale session, wrong Workspace/personal-account exclusion, duplicate source migration, project instruction byte equality, forward-recovery release. Record exact results; cannot certify missing Windows/client pair from macOS unit tests.
- [ ] Human owner reviews matrix and separately approves wider rollout; update guide to active only for proven pairs. On blocker leave stage unchanged and report required human/external action.

## Self-review and execution handoff

Spec coverage: §1–3/global limits → all tasks; §4 gates/records → Tasks 1–3/6; §5–7 clients/migration → Task 4/6; §8 recovery → Tasks 3/4/6; §9 tests → Tasks 1–6; §10 delivery → Tasks 4–6.
No task is authorization to create credentials, change access, enable company-wide plugins or publish a release. Successful mocked gates do not prove GitHub enforcement; YAML naming alone does not protect an environment.
Use fresh implementing subagent per task and separate spec/quality review, or execute inline with the same gates. Independent Task 4 can run alongside core gate development; never parallelize competing writes to workflow/version files.
Plan preparation itself writes documentation only. Next action is execution-mode selection; live settings and promotion remain separate approvals.
