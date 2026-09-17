# Team AI Operating Framework — V2

`team-engineering-skills-marketplace` distributes the `team-engineering-skills`
plugin candidate version `2.2.0` for Codex/ChatGPT plugin-capable clients and Claude Code.
It combines 15 licensed skills with shared policies, task routes, project bootstrap
and a reviewed change process. Individual developers use their own approved accounts.

เริ่มใช้งานภาษาไทย: [Quick User Manual — เลือกอ่านเฉพาะ Tool ที่ใช้](docs/QUICKSTART_TH.md).
ผู้ดูแล: [Native auto-update / Migration](docs/AUTO_UPDATE_ADMIN_TH.md) · [แบบบันทึก pilot](docs/AUTO_UPDATE_PILOT_TH.md) · [หลักฐานและข้อจำกัดคู่มือ](docs/MANUAL_SOURCES_TH.md).
Public source: [Suppacha/team-engineering-skills-plugin](https://github.com/Suppacha/team-engineering-skills-plugin).
Do not commit company secrets or private project information here.

## What V2 provides

- Central standards and owned/versioned skill registry shipped inside the plugin.
- Decentralized execution in the client the developer selects; no automatic provider switching or shared accounts.
- Advisory skill selection from task intent, with an explicit unavailable-skill fallback.
- Traceable requirement analysis, UI specification, and test-case design with reusable synthetic templates.
- Offline project policy snapshots and version/hash evidence.
- Manual sanitized Issues → owner review → PR checks → deliberate release artifact builds.

Policies are guidance, not access controls. Cloud model calls can send code off the
computer even when tools execute locally. Client permissions, human review and
configured CI checks are the actual controls. Read [Governance](docs/GOVERNANCE.md).

## Local ZIP/local-path testing

Requires Python 3.10+ and Bash for verification/build. Bootstrap itself is Python
standard-library only. Build and extract a trusted release:

```sh
./scripts/build-release.sh
unzip dist/team-engineering-skills-marketplace-2.2.0.zip -d /path/to/team-engineering-skills-marketplace-2.2.0
```

The extracted directory is the marketplace root, containing both
`.agents/plugins/marketplace.json` and `.claude-plugin/marketplace.json`.

## Codex/ChatGPT

### Install

For Codex clients with the plugin CLI:

```sh
codex plugin marketplace add /path/to/team-engineering-skills-marketplace-2.2.0
codex plugin add team-engineering-skills@team-engineering-skills-marketplace
```

For the public GitHub marketplace only after Admin activation and a passing pilot:

```sh
codex plugin marketplace add Suppacha/team-engineering-skills-plugin --ref stable
codex plugin add team-engineering-skills@team-engineering-skills-marketplace
```

Alternatively use the supported Codex Plugins UI or `/plugins`. Availability
depends on the client/account; this is not a universal installation path for
every ChatGPT surface. Start a **new session** after installation.

### Update

```sh
codex plugin marketplace upgrade team-engineering-skills-marketplace
codex plugin add team-engineering-skills@team-engineering-skills-marketplace
```

For local releases, register the newly extracted root if the path changed.
Start a new session and separately review any project policy snapshot migration.

### Uninstall

Use Plugins / `/plugins` → select the plugin → Uninstall. This does not remove
project snapshots or local release files.

## Claude Code

### Install

```sh
claude plugin marketplace add Suppacha/team-engineering-skills-plugin@stable --scope user
claude plugin install team-engineering-skills@team-engineering-skills-marketplace
```

For a local test, replace the GitHub repository with the extracted marketplace
directory. Run `/reload-plugins` in Claude Code after installation.

### Update

```sh
claude plugin marketplace update team-engineering-skills-marketplace
claude plugin update team-engineering-skills
```

Run `/reload-plugins` after updating.

### Uninstall

```sh
claude plugin uninstall team-engineering-skills@team-engineering-skills-marketplace
```

## Project bootstrap (both clients)

Installing the plugin alone does not activate shared project policies.
Run this explicit, offline bootstrap from a trusted extracted marketplace:

```sh
python3 /path/to/release/plugins/team-engineering-skills/scripts/bootstrap-project.py \
  --release /path/to/release --project /path/to/existing-project --dry-run
python3 /path/to/release/plugins/team-engineering-skills/scripts/bootstrap-project.py \
  --release /path/to/release --project /path/to/existing-project
```

Review and commit the new `AGENTS.md`, `CLAUDE.md` and `.team-ai/` in the
project's own repository. Claude's adapter imports `@AGENTS.md`; Codex uses
`AGENTS.md`. Existing targets are refused without overwriting. For existing
projects, bootstrap a disposable empty directory and manually merge the reviewed
instructions/snapshot through a PR. No automatic migration or force option exists.

## Automatic invocation and discovery

The clients can select skills from their descriptions; the bootstrapped routing
table adds intent guidance. This is model-driven, not a deterministic keyword
router, and discovery is not guaranteed. It does not automatically launch or
switch between Codex and Claude. A missing skill must be disclosed.
See [Smoke tests](docs/SMOKE_TESTS.md); interactive client pilots remain required.

## Private-Git team distribution

This repository is public. A team needing nonpublic policy can maintain its own
authorized private marketplace and substitute that repository URL during
installation. Repository authentication is managed by each user's client;
never put credentials into URLs or this package.

## Maintainer checks

Python standard library ยังเพียงพอสำหรับ plugin runtime แต่ test suite ปกติ import
PyYAML โดยตรง จึงใช้ `PyYAML==6.0.2` เป็น **mandatory development/test dependency**
แยกจาก optional client validator. ติดตั้งใน virtual environment ของ repository
ด้วย interpreter เดียวกับ `PYTHON_BIN`; ไม่ต้องติดตั้ง global

macOS/Linux:

```sh
python3 -m venv .test-venv
./.test-venv/bin/python -m pip install 'PyYAML==6.0.2'
export PYTHON_BIN="$PWD/.test-venv/bin/python"
./scripts/verify-package.sh
./scripts/build-release.sh
```

Windows PowerShell สำหรับ portable test (การ build ZIP ใช้ Bash/CI):

```powershell
py -3 -m venv .test-venv
& .\.test-venv\Scripts\python.exe -m pip install 'PyYAML==6.0.2'
$env:PYTHON_BIN = (Resolve-Path .\.test-venv\Scripts\python.exe).Path
& $env:PYTHON_BIN scripts\verify-portable.py
```

Portable tests and metadata/payload gates always run. Installed Codex and Claude
validators also run; rejection fails verification. A missing optional client validator
is explicitly **SKIPPED**, not counted as platform runtime validation. The pinned
PyYAML dependency above is not optional for development test discovery and is not a
plugin runtime dependency. The manually dispatched workflow builds a ZIP
artifact only; it does not automatically publish a release.

[Third-party notices](plugins/team-engineering-skills/THIRD_PARTY_NOTICES.md)
retain the original licensing. [Governance](docs/GOVERNANCE.md) describes versioning,
review, rollback and enforcement limits.

Command references: [OpenAI plugins](https://developers.openai.com/plugins/build/plugins),
[Claude plugins](https://code.claude.com/docs/en/discover-plugins),
[Claude AGENTS.md adapter](https://code.claude.com/docs/en/memory#agentsmd).
