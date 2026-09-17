# Personal Desktop Auto-update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a fail-closed per-user updater for Codex Desktop personal accounts, without claiming activation or Desktop certification from CI.

**Architecture:** An immutable installed updater reads public promotion evidence, fetches an immutable Git snapshot, validates it using trusted bundled code, then installs through Codex commands. A journaled local store and per-user OS scheduler handle repeat execution; Claude Code retains its native updater.

**Tech Stack:** Python 3.11+ standard library, Git, Codex plugin commands, launchd / Windows Task Scheduler, unittest and existing three-OS CI.

**Spec:** `docs/superpowers/specs/2026-09-17-personal-desktop-auto-update-design.md` (user approved).

## Global Constraints

- Repository `Suppacha/team-engineering-skills-plugin`; channel `stable`; plugin `team-engineering-skills`; marketplace `team-engineering-skills-marketplace`.
- Codex Desktop personal on macOS/Windows only; company Workspace paused; no CLI/IDE certification. CLI is an internal installer interface, not the user's work surface.
- Python 3.11+, stdlib only; no candidate code execution, self-updater, credentials, telemetry, root/admin elevation, project-instruction edits, or mutation of other marketplaces.
- Logon + every 4 hours; Windows InteractiveToken/LeastPrivilege; macOS user LaunchAgent. One OS-released lock per installation.
- 5 local log files maximum, each 1 MiB; metadata only. Installed version is not loaded-session proof.
- Retain previous verified package; uncertain mutations require readback or repair-required, never blind retry. No stable fallback to main/feature branches.
- No live scheduler/account changes or public release while implementing. CI and isolated CLI tests do not replace four-pair Desktop/native-client pilot.

## File responsibilities and execution

Use existing linked worktree/branch; preserve prior candidate and spec commits. All shell commands use `/opt/homebrew/bin/rtk proxy` on this machine. Use apply_patch for edits. One implementer at a time. Independent task review after each commit range. User already selected subagent execution; do not ask again.

New `scripts/team_updater/` package: `release.py` public evidence; `store.py` Git staging/trusted validation/locking/journal; `client.py` Codex adapter; `engine.py` update transaction; `scheduler.py` OS definitions/control; `cli.py` lifecycle/status. Entry point `scripts/team-update.py`. Distribution helper `scripts/build-updater.py`; installers `scripts/install-updater.command` and `scripts/install-updater.ps1`.

Test command on this host (substitute portable `python3`/`python` elsewhere):
```sh
/opt/homebrew/bin/rtk proxy env PYTHONPATH=/Users/suppacha_suklom/Documents/Codex/2026-07-21/new-chat/work/team-ai-next/pyyaml-temp /Users/suppacha_suklom/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/verify-portable.py
```
Focused tests use `python -m unittest discover -s tests -p 'test_personal_release.py' -v`. Record RED/GREEN evidence in each task report; full suite once before commit. Commit only task-owned files.

### Task 1: Public release eligibility reader

**Files:** Create `scripts/team_updater/__init__.py`, `scripts/team_updater/release.py`, `tests/test_personal_release.py`.

**Interfaces:** `Candidate(version: str, sha: str, record: dict)` frozen dataclass; `PublicReleaseClient(request=None).read_stable() -> str`; `.candidate() -> Candidate`; `check_upgrade(candidate, installed: dict | None) -> bool` (True newer, False identical version+SHA, ValueError otherwise). Injected request `(path: str) -> decoded JSON` is GET-only; production fixed api.github.com without credentials. Installed selector contains `version`, `sha`.

- [ ] Write failing tests with real publisher-shaped JSON fixtures; no network in tests. Decode VERSION via GitHub contents endpoint at immutable SHA (base64, bounded size). Compare canonical release-record JSON asset digest; validate `promoted`, draft/prerelease false, fixed repository/tag/target SHA, schema_version, positive run IDs, repository-local GitHub evidence URLs and approval structure matching existing `collect_approval` output. Inspect existing publisher/collector once for actual fields, do not invent approval identities.
```python
def test_same_version_changed_sha_is_refused(self):
    candidate = Candidate('2.2.0', 'b' * 40, {})
    with self.assertRaises(ValueError):
        check_upgrade(candidate, {'version': '2.2.0', 'sha': 'a' * 40})
```
- [ ] Run focused test RED before production implementation.
- [ ] Implement fixed-host GET transport with 20s timeout, 1MiB response cap, at most 3 transient attempts, bounded delay, no redirects, bounded pagination (10 pages), redacted errors. Rate limit is an error for the engine's persisted cooldown, not a spin loop. Stable absence is explicit unavailable, never fallback. Pure upgrade uses strict stable SemVer/full lowercase 40-char SHA; ensure bool is not accepted as positive integer.
```python
def check_upgrade(candidate, installed):
    if installed is None:
        return True
    old = version_tuple(installed['version'])
    new = version_tuple(candidate.version)
    if new < old or (new == old and candidate.sha != installed['sha']):
        raise ValueError('release-regression')
    return new > old
```
- [ ] Cover valid, identical, lower/same version changed SHA, wrong stable/tag/asset digest, prepared/draft/prerelease, malformed contents/JSON, missing approval, foreign evidence URLs, page/response caps and transport failures. GREEN/full suite; commit.

### Task 2: Trusted snapshot staging and safe state primitives

**Files:** Create `scripts/team_updater/store.py`, `tests/test_personal_store.py`. May reuse trusted `release_policy.py`, `release_files.py` and framework validator read-only; never load modules from staged candidate.

**Interfaces:** `Store(root: Path)` owns `staging`, `current`, `previous`, `state.json`, `journal.json`, `.lock`; `.lock()` context manager raises `BlockingIOError` for busy; `.read_state() -> dict`; `.write_state(dict)` and `.read_journal() -> dict | None` / `.write_journal(dict | None)` atomic bounded JSON; `.stage(candidate: Candidate, git_executable: Path) -> Path`; `.activate(staged: Path)`, `.restore_previous()`; `validate_snapshot(path: Path, candidate: Candidate) -> dict` returns registry. Constructor must not accept root/home/project/broad unsafe directories and must reject symlink/reparse ancestors.

- [ ] RED tests: lock conflict/release, tampered snapshot, symlink/reparse/reserved/case-colliding Git paths, outside staging activation, old current preserved on rename failure, atomic state and malformed journal.
```python
def test_two_holders_cannot_write(self):
    with Store(self.root).lock():
        with self.assertRaises(BlockingIOError):
            with Store(self.root).lock():
                self.fail('second writer entered')
```
- [ ] Implement clean Git environment (no inherited GIT_* overrides, config system/global disabled, empty templates/hooks, no credential helpers/filters/SSH/submodules, HTTPS fixed remote). Fetch SHA with bounded timeout into fresh staging Git database; inspect tree via `ls-tree -rz` and export raw blobs, not checkout/filter execution. Limit 5000 files, 16 MiB/file, 128 MiB total. Reject dangerous entries before any extraction; release allowlist controls export. Check Git object SHA and candidate HEAD/FETCH_HEAD.
- [ ] Validate with installed trusted framework validator plus marketplace/plugin identity/version and actual Apache license-file existence/containment. Staging content is data only. Do not copy remote updater code into running updater installation. OS lock uses flock/msvcrt with lock-file handle held, not stale PID files. JSON errors sanitized; modes user-private where supported.
```python
registry = trusted_framework.validate_release(snapshot / 'plugins' / 'team-engineering-skills')
if registry['version'] != candidate.version:
    raise ValueError('package-version-mismatch')
```
- [ ] GREEN targeted tests with real temp files and local Git fixture objects through injected subprocess transport (fixed production remote unchanged); full suite; commit.

### Task 3: Codex adapter and journaled update engine

**Files:** Create `scripts/team_updater/client.py`, `scripts/team_updater/engine.py`, `tests/test_personal_client.py`, `tests/test_personal_engine.py`. Consume isolated probe report `.superpowers/personal-client-probe.md` for exact observed client JSON; never guess installed-path fields.

**Interfaces:** `CodexClient(executable: Path, run=None, codex_home: Path | None=None).probe() -> dict`, `.inventory() -> dict | None`, `.register(source: Path)`, `.install(source: Path, candidate: Candidate) -> dict`, `.verify(source: Path, candidate: Candidate) -> bool`; `Updater(store, releases, client, git_executable: Path, clock=None).check() -> dict`, `.install_initial() -> dict` and `.status() -> dict`. Clock returns UTC-aware datetime. State schema 1 uses `enabled`, `installed`, `available`, `last_check`, `last_result`, `next_check`, `reload_required`; never says loaded automatically. Persist effective absolute Codex profile path at installation; pass it only as child-process CODEX_HOME so scheduler targets the same profile, never discover/copy auth. `install_initial()` is explicit first-install entry used only by CLI install; applies the same release/source gates while enabled remains false until scheduler readback succeeds. Ordinary check on disabled state does not mutate the plugin.

- [ ] RED tests for owned/unowned source collision, unsupported/malformed client JSON, plugin install subprocess uncertainty/readback, and crash between each journal phase.
```python
def test_changed_stable_cannot_activate(self):
    result = self.engine_with_moving_stable().check()
    self.assertEqual(result['last_result'], 'stable-moved')
    self.assertEqual(self.current_bytes(), self.before)
```
- [ ] Adapter uses exact selectors and absolute executables, `shell=False`, explicit cwd owned by updater, bounded output/timeouts, and no secret/raw stdout logging. Probe help/version and known JSON schema; no policy override. Inventory must reject same name sourced elsewhere before mutation. Install returns manifest/hash-backed evidence, not exit code alone. Preserve other marketplace entries.
- [ ] Constrain returned installedPath to the persisted profile's expected plugin cache/name/version before reading it. `plugin list` lacks installedPath in the observed client; persist validated add-result evidence and revalidate listing plus cache bytes on later checks. If an existing team plugin is user-disabled, stop instead of silently re-enabling it.
- [ ] Engine lock spans read/validate/stage/activate/install/readback/state. Check cooldown and enabled state; verify installed bytes even for no-op. Journal phases `prepared`, `swapped`, `installing`; state writes last; interruption/uncertain cache falls to `repair-required`, suppress future mutation until repaired deliberately. Re-read stable immediately before activation. Preserve snapshot on validated preactivation error. Attempt no blind retry if CLI status unknown; readback can prove success. Never auto-downgrade cache. Handle first install separately and require no duplicate registration.
- [ ] Success gives `updated` + reload_required; identical validated installation `up-to-date`; network failure retains installed evidence with error and bounded next_check (4h). User check follows same safety gate. Redacted structured codes only.
- [ ] GREEN focused/full tests. Repeat harmless isolated real CLI A→B using probe-established isolation and verify snapshot/cache identity. No scheduler or real profile activation; report Desktop pilot separately. Commit.

### Task 4: Per-user schedulers and lifecycle entry points

**Files:** Create `scripts/team_updater/scheduler.py`, `scripts/team_updater/cli.py`, `scripts/team-update.py`, `scripts/install-updater.command`, `scripts/install-updater.ps1`, `tests/test_personal_scheduler.py`, `tests/test_personal_cli.py`.

**Interfaces:** `Scheduler(root: Path, python: Path, entry: Path, run=None).enable()`, `.disable()`, `.status() -> bool`; pure `launch_agent(argv: list[str]) -> bytes`, `windows_task(argv: list[str], user_id: str) -> bytes`; `cli.main(argv=None) -> int`. Lifecycle subcommands `install`, `status`, `check`, `pause`, `resume`, `uninstall-updater`; explicit `--state-dir`, `--codex`, `--git` for install only, persisted absolute paths. Default OS-user app-data path named TeamEngineeringSkillsUpdater, not project cwd. Linux allowed only portable tests, not install.

- [ ] RED tests for quoted paths, malformed XML control chars, no-admin settings and uninstall isolation.
```python
def test_launch_agent_interval_and_arguments(self):
    data = plistlib.loads(launch_agent(['/path with space/python', '/team/update.py', 'check']))
    self.assertEqual(data['StartInterval'], 14400)
    self.assertTrue(data['RunAtLoad'])
    self.assertEqual(data['ProgramArguments'][0], '/path with space/python')
```
- [ ] Generate plist via plistlib, Windows XML via ElementTree + subprocess.list2cmdline; logon trigger + periodic 4h, IgnoreNew, InteractiveToken/LeastPrivilege, no stored password. Use fixed unique team label/task name; refuse collisions with unowned scheduler definitions. Verify readback before state enabled. Disable/remove only owned scheduler, preserve package/source/backups. Windows identity derived from OS, not user-supplied untrusted task name; never log identity.
- [ ] CLI install validates prerequisites before copy/config writes, freezes trusted updater runtime separately from candidate source, uses engine initial install then scheduler. Failure leaves disabled/repair state, never says enabled. Pause and resume reconcile scheduler readback and capabilities/source. Log allowlisted metadata via RotatingFileHandler maxBytes=1048576, backupCount=4; no raw exception/path/credential output. Status JSON + short human mode, clear unknown vs current and installed vs loaded.
- [ ] Install wrappers forward quoted arguments without changing execution policy/elevating or downloading runtimes; no unconditional uninstall/cache cleanup. GREEN/full tests; no actual scheduler installation during automated tests; commit.

### Task 5: Distribution, manuals, CI evidence and delivery

**Files:** Create `scripts/build-updater.py`, `tests/test_updater_distribution.py`, `docs/PERSONAL_AUTO_UPDATE_TH.md`; modify `README.md`, `docs/QUICKSTART_TH.md`, `docs/AUTO_UPDATE_ADMIN_TH.md`, `docs/AUTO_UPDATE_PILOT_TH.md`, `docs/MANUAL_SOURCES_TH.md`, `docs/MAINTAINER_APPENDIX_TH.md`, `tests/test_auto_update_docs.py`, `.github/workflows/verify.yml`, `CHANGELOG.md` only as needed.

**Interfaces:** `build-updater.py --output PATH` creates a portable allowlisted ZIP containing trusted runtime and validator dependencies, not credentials/pilot data. Existing plugin ZIP format remains compatible. Candidate version remains 2.2.0 only if unpublished; never overwrite published version.

- [ ] RED distribution test asserts source ZIP exclusions and installed runtime dependencies can import from extracted artifact. Review human README/quickstart prose for false company/native promises; do not add string-presence tests for human prose. Retain or adapt existing executable/config/link contract tests where they exercise real behavior.
```python
def test_updater_archive_contains_entry_and_excludes_private_state(self):
    names = self.build_and_list()
    self.assertIn('scripts/team-update.py', names)
    self.assertFalse(any('.superpowers/' in name or name.endswith('.pem') for name in names))
```
- [ ] Implement reproducible bounded allowlist build using trusted release_files, include frozen validator dependencies deliberately; no symlinks/private cache. Amend docs in Thai with installation per OS-user, prerequisites, 4h delay/sleep/offline, new-chat loading, status/pause/resume/uninstall, non-self-updating runtime, account non-isolation, paused company work and release protection bootstrap still needed. Quickstart stays short; technical repair Appendix.
- [ ] Preserve existing release baseline ancestry/protections. Update four-pair pilot rows to Codex personal with explicit scheduler/installed/loaded test columns, all unrun tests NOT RUN. Do not fabricate test results. Document required real Windows Desktop tester and GitHub release Admin actions.
- [ ] CI runs all added portable tests on all3OS, plus native OS scheduler-definition tests without installing production tasks; retain mandatory Windows NTFS test. Record focused/full tests, package validators, clean diff, artifact contents/checksum. Independent whole-branch review, one fix wave, then push to already authorized feature branch and update PR2 evidence if network available. No merge/publish/new credentials automatically.
- [ ] Live activation is a separate gated handoff: human configures release writer/protections and approves exact release, then approved pilot operators run macOS/Windows Desktop A→B. Stop only at external authority/device gates, with precise unfinished list. No claim team-enabled until evidence passes.

## Self-review coverage

Spec1–2 scoped across all tasks; spec3–4 in Tasks2–4; spec5 in Tasks1–2; spec6 in Tasks2–3; spec7 in Task4; spec8–10 in Task5. Candidate modules never replace trusted runtime. Same source directory is owned by Store and passed to CodexClient by engine only. Scheduler calls the installed immutable entry point. Distribution includes its runtime imports; tests exercise extracted artifact. Protocol shape remains a capability gate rather than a promise for unknown clients.
