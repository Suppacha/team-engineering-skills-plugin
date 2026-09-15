#!/usr/bin/env python3
"""Create an explicitly selected project's advisory policy snapshot, offline.

No project contents are read, no clients installed, no commands executed, no
network calls made. Run only from a trusted release on a quiescent local folder.
"""
import argparse
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from framework import safe_directory, validate_release
from project_snapshot import release_evidence, render_agents, snapshot_payload, write_snapshot


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
    payload = snapshot_payload(plugin, registry)
    evidence = release_evidence(registry, payload)
    agents = render_agents(registry)
    if dry_run:
        print("Validated release " + registry["version"] + "; would create AGENTS.md, CLAUDE.md and .team-ai. No writes.")
        return
    # Exclusive creation refuses files introduced after preflight. There is no
    # overwrite/force path. On I/O failure retain partial outputs for inspection;
    # never recursively delete a directory that another process may have changed.
    write_snapshot(project, payload, evidence, agents)
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
