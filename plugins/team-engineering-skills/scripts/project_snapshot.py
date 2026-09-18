"""Shared generation for bootstrap and reviewed project update proposals."""

import json

from framework import digest


CLAUDE_ADAPTER = "# Team AI adapter\n\n@AGENTS.md\n"


def snapshot_payload(plugin, registry):
    payload = {"registry.json": (plugin / "registry.json").read_bytes()}
    for name in sorted(registry["standards"]):
        payload["standards/" + name] = (plugin / "standards" / name).read_bytes()
    return payload


def release_evidence(registry, payload):
    return {
        "schema_version": 1,
        "version": registry["version"],
        "owner": registry["owner"],
        "sha256": {name: digest(data) for name, data in payload.items()},
        "provenance": "Explicit local release; hashes detect drift, not publisher authenticity.",
    }


def render_agents(registry):
    lines = [
        "# Team AI Operating Framework", "", "Release: " + registry["version"], "",
        "Read these local standards before acting:", "",
        *["- .team-ai/standards/" + name for name in sorted(registry["standards"])], "",
        "These instructions are advisory, not a security boundary. Respect higher-priority",
        "client instructions, user authorization and project-specific constraints; stop on conflicts.",
        "Cloud model calls can send code off this computer. Do not read or transmit secrets.", "",
        "## Skill selection", "",
        "Use the smallest relevant set of installed team-engineering-skills skills below.",
        "Read the selected SKILL.md fully and announce the skill and reason before acting.",
        "This table guides the current client; it does not launch or switch AI providers.",
        "If a skill is unavailable, state that clearly and use a safe general fallback.",
        "Never claim a missing skill ran. Match task intent, not only exact keywords.", "",
    ]
    for skill in registry["skills"]:
        lines.append("- " + skill["name"] + ": " + "; ".join(skill["routes"]))
    lines.extend([
        "", "Registry and version evidence: .team-ai/registry.json and .team-ai/release.json.",
        "Feedback is manual and sanitized via GitHub Issues; never upload prompts or code automatically.", "",
    ])
    return "\n".join(lines)


def write_snapshot(root, payload, evidence, agents):
    snapshot = root / ".team-ai"
    snapshot.mkdir(mode=0o700)
    (snapshot / "standards").mkdir(mode=0o700)
    for name, data in payload.items():
        target = snapshot / name
        with target.open("xb") as stream:
            stream.write(data)
    with (snapshot / "release.json").open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, indent=2, sort_keys=True)
        stream.write("\n")
    with (root / "AGENTS.md").open("x", encoding="utf-8") as stream:
        stream.write(agents)
    with (root / "CLAUDE.md").open("x", encoding="utf-8") as stream:
        stream.write(CLAUDE_ADAPTER)
