# Team Engineering Skills

`team-engineering-skills` version `2.0.0` is the plugin delivered by the
`team-engineering-skills-marketplace` marketplace. It bundles 12 approved,
licensed engineering workflows for quality, security, platform, frontend, and
incident work.

## Install

Install this plugin from the marketplace as
`team-engineering-skills@team-engineering-skills-marketplace`. For Claude Code, reload the
current client with `/reload-plugins`. For Codex/ChatGPT, start a new session
after installing so the bundled skills are available.

Use the local ZIP/local-path flow only for testing an extracted release archive.
For team rollout, use the public marketplace at
https://github.com/Suppacha/team-engineering-skills-plugin or an approved private fork.

## Update

Refresh the source marketplace and update this plugin through the platform's
plugin UI. Re-run `/reload-plugins` in Claude Code, or start a new
Codex/ChatGPT session, after updating.

## Uninstall

Remove `team-engineering-skills@team-engineering-skills-marketplace` from the platform's
plugin UI. In Claude Code, the equivalent command is:

```sh
claude plugin uninstall team-engineering-skills@team-engineering-skills-marketplace
```

## Automatic invocation

The bundled skills are available for automatic invocation when a request fits a
skill's documented workflow. Use the repository-level `docs/SMOKE_TESTS.md`
prompts to confirm discovery after installation.

See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for upstream attribution
and license information.

## V2 framework

`standards/` ships security, AI usage, data access and coding/output policy.
`registry.json` records owner, skill versions, task routes and payload hashes.
`scripts/bootstrap-project.py` creates advisory project instructions and a local
policy snapshot from an explicitly supplied extracted marketplace root.
It refuses existing AGENTS.md, CLAUDE.md and .team-ai targets; it never installs
clients, changes accounts, runs scans or uploads telemetry.

Plugin installation does not itself activate project policy. Bootstrap and review
the project files separately; full instructions are in the marketplace README.
AGENTS.md/CLAUDE.md are advisory. Cloud model calls may transmit code despite
local tool execution. Hashes detect drift, not publisher authenticity.
