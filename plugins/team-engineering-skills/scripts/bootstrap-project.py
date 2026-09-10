#!/usr/bin/env python3
"""Create an explicitly selected project's advisory policy snapshot, offline.

No project contents are read, no clients installed, no commands executed, no
network calls made. Run only from a trusted release on a quiescent local folder.
"""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from framework import digest, safe_directory, validate_release


def bootstrap(release, project, dry_run=False):
    release = safe_directory(release)
    project = safe_directory(project)
    if project == release or project.is_relative_to(release) or release.is_relative_to(project):
        raise ValueError("refusing overlapping release and project directories")
    targets = [project / name for name in ("AGENTS.md", "CLAUDE.md", ".team-ai")]
    if any(path.exists() or path.is_symlink() for path in targets):
        raise ValueError("refusing existing AGENTS.md, CLAUDE.md or .team-ai; merge manually in a reviewed PR")
    plugin = release / "plugins/team-engineering-skills"
    registry = validate_release(plugin)
    payload = {"registry.json": (plugin / "registry.json").read_bytes()}
    for name in sorted(registry["standards"]):
        payload["standards/" + name] = (plugin / "standards" / name).read_bytes()
    evidence = {
        "schema_version": 1, "version": registry["version"],
        "owner": registry["owner"], "sha256": {name: digest(data) for name, data in payload.items()},
        "provenance": "Explicit local release; hashes detect drift, not publisher authenticity.",
    }
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
    lines.extend(["", "Registry and version evidence: .team-ai/registry.json and .team-ai/release.json.",
                  "Feedback is manual and sanitized via GitHub Issues; never upload prompts or code automatically.", ""])
    agents = "\n".join(lines).encode("utf-8")
    if dry_run:
        print("Validated release " + registry["version"] + "; would create AGENTS.md, CLAUDE.md and .team-ai. No writes.")
        return
    # Exclusive creation refuses files introduced after preflight. There is no
    # overwrite/force path. On I/O failure retain partial outputs for inspection;
    # never recursively delete a directory that another process may have changed.
    snapshot = project / ".team-ai"
    snapshot.mkdir(mode=0o700)
    (snapshot / "standards").mkdir(mode=0o700)
    for name, data in payload.items():
        with (snapshot / name).open("xb") as stream:
            stream.write(data)
    with (snapshot / "release.json").open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, indent=2, sort_keys=True)
        stream.write("\n")
    with (project / "AGENTS.md").open("xb") as stream:
        stream.write(agents)
    with (project / "CLAUDE.md").open("x", encoding="utf-8") as stream:
        stream.write("# Team AI adapter\n\n@AGENTS.md\n")
    print("Created advisory project snapshot for " + registry["version"] + ". Review and commit it; restart your AI client session.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True, type=Path, help="trusted extracted marketplace root (not ZIP or URL)")
    parser.add_argument("--project", required=True, type=Path, help="existing local project directory")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        bootstrap(args.release, args.project, args.dry_run)
    except (ValueError, OSError) as error:
        print("Bootstrap stopped: " + str(error) + ". Existing files were not overwritten; inspect any partial new files.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
