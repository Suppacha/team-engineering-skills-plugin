# Governance and enforcement boundaries

Repository: https://github.com/Suppacha/team-engineering-skills-plugin (public).
Framework and each skill's initial maintainer: **Suppacha** (`@Suppacha`).
Ownership here means stewardship, not a claim of copyright over third-party skills.

## Change and release workflow

1. Submit a sanitized manual Issue (feedback or proposed change).
2. Suppacha triages scope, authorization, license evidence and acceptance criteria.
3. Implement in a branch; include tests, docs, registry and changelog changes in a PR.
4. Request owner review and run `scripts/verify-package.sh`. Record optional-validator skips honestly. Pilot both supported clients before team-wide rollout.
5. A maintainer deliberately dispatches **Build reviewed release artifact** on the reviewed ref. It runs verification and uploads a ZIP artifact, not a GitHub Release, tag, marketplace publish, deployment or package-registry push.
6. Review the artifact and publish an approved version through the chosen release process. Consumers explicitly update the plugin and review project snapshot changes; no silent policy updates.
7. Roll back by reinstalling an approved previous release and reverting the project snapshot commit after review. Uninstalling a plugin does not remove `.team-ai`, `AGENTS.md` or `CLAUDE.md`.

Use semantic versions for the framework: major for incompatible policy/bootstrap contracts, minor for compatible capabilities, patch for compatible fixes. Individual skill `version` values are team-packaged versions, not upstream versions: V2 retains the V1 payloads at `1.0.0`. Update an affected skill's version and `tree_sha256` when its content changes. Keep immutable upstream revisions and licenses in `config/skills-lock.json`.

Registry hash algorithm: SHA-256 over each sorted skill-relative UTF-8 filename, a NUL byte, and the binary SHA-256 of that file's bytes. Policy hashes are plain file SHA-256. Use `scripts/framework.py`'s `tree_digest` function when updating metadata. Hash changes must be reviewed, never blindly refreshed to silence a failure. Hashes detect content drift, not identity or trust: obtain releases from a trusted, reviewed source.

## What is and is not enforced

| Layer | Actual behavior |
| --- | --- |
| AGENTS.md / CLAUDE.md / SKILL.md | Advisory instructions and semantic routing; client/model behavior is not guaranteed. |
| Bootstrap | Explicit existing local project/release; refuses all existing targets and symlinks; validates registry/payload hashes; no network, scans, telemetry or account configuration. |
| Package CI | Runs Python tests, metadata consistency, payload hashes and available client validators. It is not a semantic AI-policy engine or a repository-wide secret scanner. |
| CODEOWNERS | Routes review to @Suppacha; does not require approval by itself. |
| Branch protection / rulesets | Not configured by this repository. An administrator must separately require passing checks and appropriate reviews; a sole owner needs an additional reviewer for independent approval. |
| Client/OS permissions | Configured by each developer/organization, not installed or weakened by the plugin. |
| Usage evidence | Manual sanitized pilot notes and GitHub PR/Issue history; no centralized prompt/usage dashboard or automated monitoring. |

Bootstrap should run while no other process is modifying the project directory. Exclusive file creation prevents overwrite, but this is not a hardened boundary against a hostile local process swapping directories concurrently. I/O failure can leave newly created partial files; inspect them manually, do not rerun with a force flag (none exists).

The ZIP builder uses an explicit distribution allowlist and excludes common secret filenames and internal caches. This is not content scanning: a secret embedded in a normal source/doc file still requires human review or a separately configured scanner. Never put secrets in this public repository.

Build from a clean, reviewed checkout or extracted approved release. The allowlist
includes distributable directories such as docs/ and scripts/; an untracked note
inside those directories can still be included. Review the final ZIP inventory,
not just the Git diff. Do not export old local Git history containing internal work.
