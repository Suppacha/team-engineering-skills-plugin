#!/usr/bin/env python3
"""Create an offline, review-only proposal for a V2 project snapshot update."""

import argparse
import difflib
import json
from pathlib import Path
import re
import sys


sys.dont_write_bytecode = True
from framework import STANDARD_FILES, SEMVER, digest, safe_directory, validate_release
from project_snapshot import (
    CLAUDE_ADAPTER,
    release_evidence,
    render_agents,
    snapshot_payload,
    write_snapshot,
)


MAX_MANAGED_FILE_BYTES = 2 * 1024 * 1024


def paths_overlap(first, second):
    return first == second or first.is_relative_to(second) or second.is_relative_to(first)


def safe_new_directory(value):
    path = Path(value).absolute()
    if path.exists() or path.is_symlink():
        raise ValueError("proposal output already exists")
    parent = path.parent
    for component in (parent, *parent.parents):
        if component.is_symlink():
            raise ValueError("refusing symlinked proposal output ancestor")
    if not parent.is_dir():
        raise ValueError("proposal output parent directory must already exist")
    return path


def read_managed(path):
    if path.is_symlink():
        raise ValueError("refusing symlinked framework-managed file: " + path.name)
    if not path.is_file():
        raise ValueError("inconsistent prior snapshot; missing managed file: " + path.name)
    if path.stat().st_size > MAX_MANAGED_FILE_BYTES:
        raise ValueError("inconsistent prior snapshot; managed file is too large: " + path.name)
    return path.read_bytes()


def parse_json(data, label):
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("inconsistent prior snapshot; invalid " + label) from error
    if not isinstance(value, dict):
        raise ValueError("inconsistent prior snapshot; " + label + " must be an object")
    return value


def version_tuple(value):
    if not isinstance(value, str) or not SEMVER.fullmatch(value):
        raise ValueError("inconsistent prior snapshot version")
    return tuple(int(part) for part in value.split("."))


def validate_prior_snapshot(project):
    managed_roots = [project / "AGENTS.md", project / "CLAUDE.md", project / ".team-ai"]
    if any(path.is_symlink() for path in managed_roots):
        raise ValueError("refusing symlinked framework-managed path")
    snapshot = project / ".team-ai"
    if not snapshot.is_dir():
        raise ValueError("inconsistent prior snapshot; .team-ai is missing")
    for path in snapshot.rglob("*"):
        if path.is_symlink():
            raise ValueError("refusing symlink in framework-managed snapshot")

    agents = read_managed(project / "AGENTS.md").decode("utf-8")
    claude = read_managed(project / "CLAUDE.md").decode("utf-8")
    registry_data = read_managed(snapshot / "registry.json")
    evidence_data = read_managed(snapshot / "release.json")
    registry = parse_json(registry_data, "registry.json")
    evidence = parse_json(evidence_data, "release.json")
    try:
        if type(registry["schema_version"]) is not int or registry["schema_version"] != 1:
            raise ValueError("unsupported prior registry contract")
        if type(evidence["schema_version"]) is not int or evidence["schema_version"] != 1:
            raise ValueError("unsupported prior release evidence contract")
        prior_version = registry["version"]
        if evidence["version"] != prior_version or evidence["owner"] != registry["owner"]:
            raise ValueError("inconsistent prior snapshot version or owner evidence")
        if version_tuple(prior_version)[0] != 2:
            raise ValueError("unsupported prior framework version contract: " + prior_version)
        if set(registry["standards"]) != STANDARD_FILES:
            raise ValueError("inconsistent prior snapshot standards")
        expected_names = {"registry.json"} | {"standards/" + name for name in STANDARD_FILES}
        if set(evidence["sha256"]) != expected_names:
            raise ValueError("inconsistent prior snapshot hash evidence")
        if evidence["sha256"]["registry.json"] != digest(registry_data):
            raise ValueError("prior snapshot drift: registry.json hash mismatch")
        for name in STANDARD_FILES:
            data = read_managed(snapshot / "standards" / name)
            expected = registry["standards"][name]
            if evidence["sha256"]["standards/" + name] != expected or digest(data) != expected:
                raise ValueError("prior snapshot drift: standards/" + name + " hash mismatch")
        if not isinstance(registry["skills"], list) or not registry["skills"]:
            raise ValueError("inconsistent prior snapshot skills")
        for skill in registry["skills"]:
            if not isinstance(skill["name"], str) or not isinstance(skill["routes"], list):
                raise ValueError("inconsistent prior snapshot skill route")
            if any(not isinstance(route, str) for route in skill["routes"]):
                raise ValueError("inconsistent prior snapshot skill route")
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("inconsistent prior snapshot metadata") from error
    return registry, agents, claude


def unified(old_text, new_text, name):
    return "".join(difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile="project/" + name,
        tofile="proposal/" + name,
    ))


def proposal_diff(project, payload, evidence, agents):
    pieces = [
        unified((project / "AGENTS.md").read_text(encoding="utf-8"), agents, "AGENTS.md"),
        unified((project / "CLAUDE.md").read_text(encoding="utf-8"), CLAUDE_ADAPTER, "CLAUDE.md"),
    ]
    proposed = dict(payload)
    proposed["release.json"] = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode()
    for name in sorted(proposed):
        old_path = project / ".team-ai" / name
        old_text = old_path.read_text(encoding="utf-8") if old_path.is_file() else ""
        pieces.append(unified(old_text, proposed[name].decode("utf-8"), ".team-ai/" + name))
    return "".join(pieces)


def create_proposal(release, project, output, dry_run=False):
    release = safe_directory(release)
    project = safe_directory(project)
    output = safe_new_directory(output)
    if paths_overlap(release, project) or paths_overlap(release, output) or paths_overlap(project, output):
        raise ValueError("refusing overlapping release, project or proposal output paths")

    plugin = release / "plugins/team-engineering-skills"
    registry = validate_release(plugin)
    if version_tuple(registry["version"])[0] != 2:
        raise ValueError("unsupported target framework version contract")
    prior, current_agents, current_claude = validate_prior_snapshot(project)
    if version_tuple(registry["version"]) <= version_tuple(prior["version"]):
        raise ValueError("target release must be newer than the prior snapshot")

    payload = snapshot_payload(plugin, registry)
    evidence = release_evidence(registry, payload)
    agents = render_agents(registry)
    clean_prior_agents = render_agents(prior)
    conflicts = []
    if current_agents != clean_prior_agents:
        conflicts.append(unified(clean_prior_agents, current_agents, "AGENTS.md custom instructions"))
    if current_claude != CLAUDE_ADAPTER:
        conflicts.append(unified(CLAUDE_ADAPTER, current_claude, "CLAUDE.md custom instructions"))
    diff_text = proposal_diff(project, payload, evidence, agents)
    if dry_run:
        print(
            "Validated project snapshot %s and release %s; would create a review proposal. No writes."
            % (prior["version"], registry["version"])
        )
        return

    output.mkdir(mode=0o700)
    write_snapshot(output, payload, evidence, agents)
    migration = """# Manual Team AI framework migration

Current snapshot: {old}
Proposed snapshot: {new}

This directory is a proposal only. It did not modify the source project, run Git,
open a pull request, or merge anything. Review `project-to-proposal.diff`, preserve
project-specific instructions, and manually merge the approved result in a reviewed
branch/PR. Hashes detect drift, not publisher authenticity.

Custom instruction conflicts detected: {conflict_count}. See `CONFLICTS.md` when present.
""".format(old=prior["version"], new=registry["version"], conflict_count=len(conflicts))
    (output / "MIGRATION.md").write_text(migration, encoding="utf-8")
    (output / "project-to-proposal.diff").write_text(diff_text, encoding="utf-8")
    if conflicts:
        conflict_text = (
            "# Manual merge conflicts\n\nThe existing project instructions differ from the frozen "
            "bootstrap baseline. Preserve and manually merge these project-owned changes; "
            "the proposal did not overwrite them.\n\n```diff\n" + "\n".join(conflicts) + "```\n"
        )
        (output / "CONFLICTS.md").write_text(conflict_text, encoding="utf-8")
    print("Created review-only proposal for %s -> %s. Source project unchanged." % (prior["version"], registry["version"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True, type=Path, help="trusted extracted marketplace root")
    parser.add_argument("--project", required=True, type=Path, help="existing project with a V2 snapshot")
    parser.add_argument("--output", required=True, type=Path, help="new proposal directory")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        create_proposal(args.release, args.project, args.output, args.dry_run)
    except (ValueError, OSError, UnicodeError) as error:
        print("Project update stopped: " + str(error) + ". Source project was not changed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
