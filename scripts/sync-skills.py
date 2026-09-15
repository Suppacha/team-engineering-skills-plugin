#!/usr/bin/env python3
"""Synchronize the licensed skill allowlist into the distributable plugin."""

import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Dict, Iterable, List


marketplace_root = Path(__file__).resolve().parents[1]
plugin_root = marketplace_root / "plugins" / "team-engineering-skills"
lock_path = marketplace_root / "config" / "skills-lock.json"
REQUIRED_FIELDS = ("name", "ownership", "license", "source", "revision")
ALLOWED_OWNERSHIP = {"Team-owned", "Third-party"}
ALLOWED_THIRD_PARTY_LICENSES = {"MIT", "Apache-2.0", "CC-BY-SA-4.0"}
PLACEHOLDERS = {"unknown", "unverified", "tbd", "todo", "n/a", "none"}
SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REPOSITORY_OWNED_SOURCE = "Repository-owned canonical skill"
RUNTIME_ARTIFACTS = {
    ".DS_Store",
    ".coverage",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "__pycache__",
}
AGENT_INTERFACE_METADATA = {
    "property-based-testing": (
        "Property-based testing",
        "Design, review, and debug property-based tests.",
    ),
    "sharp-edges": (
        "Sharp edges",
        "Review APIs and configuration for misuse-resistant design.",
    ),
    "supply-chain-risk-auditor": (
        "Supply-chain risk auditor",
        "Audit dependency provenance and software supply-chain risk.",
    ),
    "variant-analysis": (
        "Variant analysis",
        "Find related bug and vulnerability variants from a known root cause.",
    ),
}
MIT_PERMISSION = """Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the \"Software\"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""


def require_within(path: Path, parent: Path, description: str) -> None:
    """Raise when a resolved path would leave its allowed directory."""
    try:
        path.relative_to(parent)
    except ValueError as error:
        raise ValueError(f"{description} escapes {parent}: {path}") from error


def load_lock() -> List[Dict[str, Any]]:
    """Read and validate the package's license allowlist."""
    data = json.loads(lock_path.read_text(encoding="utf-8"))
    skills = data.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ValueError("skills-lock.json must contain a non-empty skills list")

    names = []
    for skill in skills:
        if not isinstance(skill, dict):
            raise ValueError("each lock entry must be an object")
        missing = [field for field in REQUIRED_FIELDS if not skill.get(field)]
        if missing:
            raise ValueError(f"lock entry is missing required fields: {', '.join(missing)}")
        name = skill["name"]
        if not isinstance(name, str) or not SKILL_NAME.fullmatch(name):
            raise ValueError(f"invalid skill name: {name!r}")
        validate_license_evidence(skill)
        names.append(name)

    if len(names) != len(set(names)):
        raise ValueError("skills-lock.json contains duplicate skill names")
    return skills


def meaningful_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.strip().casefold() not in PLACEHOLDERS


def validate_license_evidence(skill: Dict[str, Any]) -> None:
    """Accept only reviewed ownership/license classes with usable notice evidence."""
    ownership = skill.get("ownership")
    license_name = skill.get("license")
    if not isinstance(ownership, str) or ownership not in ALLOWED_OWNERSHIP:
        raise ValueError(f"unapproved ownership: {ownership!r}")
    if ownership == "Team-owned":
        if license_name != "Team-owned":
            raise ValueError("team-owned entries must use the Team-owned license class")
        return
    if skill.get("source") == REPOSITORY_OWNED_SOURCE:
        raise ValueError("repository-owned canonical skills must be Team-owned")
    if not isinstance(license_name, str) or license_name not in ALLOWED_THIRD_PARTY_LICENSES:
        raise ValueError(f"unapproved license: {license_name!r}")
    if not meaningful_text(skill.get("source")) or not re.fullmatch(r"https://[^\s/]+/\S+", skill["source"]):
        raise ValueError("third-party source must be an HTTPS repository URL")
    if not isinstance(skill.get("revision"), str) or not re.fullmatch(r"[0-9a-f]{40}", skill["revision"]):
        raise ValueError("third-party revision must be a pinned 40-character commit")
    if not meaningful_text(skill.get("attribution")):
        raise ValueError("third-party attribution is required")
    notice = skill.get("notice")
    if not isinstance(notice, dict):
        raise ValueError("third-party notice evidence is required")
    if license_name == "MIT" and not meaningful_text(notice.get("copyright")):
        raise ValueError("MIT copyright notice is required")
    if license_name == "CC-BY-SA-4.0" and notice.get("license_url") != "https://creativecommons.org/licenses/by-sa/4.0/":
        raise ValueError("CC-BY-SA-4.0 license notice URL is required")
    if license_name == "Apache-2.0":
        local_file = notice.get("license_file")
        if not meaningful_text(local_file) or Path(local_file).is_absolute() or ".." in Path(local_file).parts:
            raise ValueError("Apache-2.0 requires a skill-local license_file")


def validate_write_target(path: Path, source_root: Path = None) -> None:
    """Reject links in the full write path and all overlap with maintainer input."""
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError(f"write target must not traverse a symlink: {component}")
    if source_root is not None and paths_overlap(path.resolve(), source_root):
        raise ValueError(f"write target overlaps source: {path}")


def validate_source_tree(source_dir: Path) -> None:
    """Reject source links that point outside the one skill being copied."""
    resolved_skill_dir = source_dir.resolve(strict=True)
    for path in source_dir.rglob("*"):
        if path.is_symlink():
            try:
                resolved_link = path.resolve(strict=True)
            except FileNotFoundError as error:
                raise ValueError(f"broken source symlink: {path}") from error
            require_within(resolved_link, resolved_skill_dir, "source symlink")


def paths_overlap(first: Path, second: Path) -> bool:
    """Return whether either resolved path contains the other."""
    try:
        first.relative_to(second)
        return True
    except ValueError:
        try:
            second.relative_to(first)
            return True
        except ValueError:
            return False


def validate_destination(destination_root: Path, source_root: Path, names: Iterable[str]) -> None:
    """Reject destination links, files, and source overlap before any write."""
    if destination_root.is_symlink():
        raise ValueError(f"destination root must not be a symlink: {destination_root}")
    if paths_overlap(source_root, destination_root.resolve()):
        raise ValueError("source and destination roots must not overlap")
    if not destination_root.exists():
        return
    if not destination_root.is_dir():
        raise ValueError(f"destination root is not a directory: {destination_root}")

    for path in destination_root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"destination tree must not contain a symlink: {path}")
    for name in names:
        child = destination_root / name
        if child.exists() and not child.is_dir():
            raise ValueError(f"destination skill path is not a directory: {child}")


def is_runtime_artifact(name: str) -> bool:
    """Filter interpreter, test, editor, and platform-generated payload."""
    return name in RUNTIME_ARTIFACTS or name.endswith((".pyc", ".pyo"))


def ignore_runtime_artifacts(directory: str, names: List[str]) -> List[str]:
    """Tell copytree which generated runtime artifacts to omit."""
    del directory
    return [name for name in names if is_runtime_artifact(name)]


def remove_stale_children(destination_root: Path, allowed_names: Iterable[str]) -> None:
    """Remove only top-level package children that are no longer allowlisted."""
    allowed = set(allowed_names)
    for child in destination_root.iterdir():
        if child.name in allowed:
            continue
        if child.is_symlink() or child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child)


def build_snapshot(source_dirs: Iterable[tuple], staging_root: Path) -> None:
    """Build a filtered, self-contained copy before changing the package."""
    for name, source_dir in source_dirs:
        shutil.copytree(
            source_dir,
            staging_root / name,
            symlinks=False,
            ignore=ignore_runtime_artifacts,
        )
        add_codex_agent_metadata(staging_root / name, name)
        if name == "selecting-quality-engineering-tools":
            add_standalone_quality_guidance(staging_root / name)


QUALITY_TOOL_REPLACEMENTS = {
    "Prefer the existing project framework. **REQUIRED SUB-SKILL:** Use `playwright` or the available Playwright testing skill.":
        "Prefer the existing project framework; use the standalone browser workflow below. An installed `playwright` skill is an optional enhancement.",
    "Separate passive/baseline and active scans. **REQUIRED SUB-SKILL:** Use `api-security` or `pentest-tools`.":
        "Separate passive/baseline and active scans; use the scoped workflow below. Installed `api-security` or `pentest-tools` skills are optional enhancements.",
    "**REQUIRED SUB-SKILL:** Use `choose-frontend-design-system`.":
        "Follow the selection guidance below. An installed `choose-frontend-design-system` skill is an optional enhancement.",
}
QUALITY_TOOL_FALLBACK = """## Standalone workflows

These workflows do not require the optional related skills to be installed.

- **Browser E2E:** Identify one critical user journey and its observable success and failure states. Reuse the project's browser runner and isolated test data. Prefer role/label locators, wait for observable application readiness instead of fixed sleeps, and assert user-visible outcomes. Run the focused test, inspect its exit status, and retain a failure trace or screenshot. Expand coverage only for distinct risks.
- **Security testing:** Confirm the authorized target, scope, credentials, and permitted scan mode. Begin with passive analysis of test-environment traffic; redact secrets in artifacts and manually validate findings. An active scan requires explicit approval for its target, rate ceiling, window, stop condition, and cleanup. Record reproducible evidence and limitations; neither scanner output nor a clean scan proves the absence of vulnerabilities.
- **Design-system selection:** Inspect existing components, design tokens, framework constraints, and brand requirements. Reuse a compatible installed system first. Compare candidates on accessibility (keyboard operation, focus, and semantics), theming, component coverage, maintenance, and integration cost. Validate one representative component against those needs before adding dependencies; document the choice and any uncovered requirements.

"""


def add_standalone_quality_guidance(snapshot_skill: Path) -> None:
    """Adapt only the packaged copy; fail safely if the upstream structure drifts."""
    skill_path = snapshot_skill / "SKILL.md"
    contents = skill_path.read_text(encoding="utf-8")
    for original, replacement in QUALITY_TOOL_REPLACEMENTS.items():
        if original not in contents and replacement not in contents:
            raise ValueError("quality-tool source changed; review the packaging adaptation")
        contents = contents.replace(original, replacement)
    if "## Standalone workflows\n" not in contents:
        if "## Selection workflow\n" not in contents:
            raise ValueError("quality-tool source is missing its selection workflow")
        contents = contents.replace("## Selection workflow\n", QUALITY_TOOL_FALLBACK + "## Selection workflow\n", 1)
    skill_path.write_text(contents, encoding="utf-8")


def add_codex_agent_metadata(snapshot_skill: Path, name: str) -> None:
    """Add required Codex display metadata without altering the maintainer source."""
    metadata = AGENT_INTERFACE_METADATA.get(name)
    agent_path = snapshot_skill / "agents" / "openai.yaml"
    if metadata is None or not agent_path.is_file():
        return
    display_name, short_description = metadata
    contents = agent_path.read_text(encoding="utf-8")
    if "interface:\n" not in contents:
        raise ValueError(f"agent manifest is missing an interface section: {agent_path}")
    if "display_name:" in contents or "short_description:" in contents:
        raise ValueError(f"agent manifest has incomplete Codex interface metadata: {agent_path}")
    agent_path.write_text(
        contents.replace(
            "interface:\n",
            "interface:\n"
            f'  display_name: "{display_name}"\n'
            f'  short_description: "{short_description}"\n',
            1,
        ),
        encoding="utf-8",
    )


def render_notices(skills: Iterable[Dict[str, Any]]) -> str:
    """Generate attribution and license groupings from structured lock evidence."""
    third_party = [skill for skill in skills if skill["ownership"] != "Team-owned"]
    groups = {}
    lines = [
        "# Third-Party Notices",
        "",
        "This plugin redistributes the following third-party skills. Their "
        "license terms apply to the corresponding packaged material.",
        "",
    ]
    for skill in third_party:
        validate_license_evidence(skill)
        group = (skill["license"], json.dumps(skill["notice"], sort_keys=True))
        groups.setdefault(group, []).append(skill["name"])
        lines.extend(
            [
                f"## {skill['name']}",
                "",
                f"- Attribution: {skill['attribution']}",
                f"- Repository: {skill['source']}",
                f"- Revision: {skill['revision']}",
                f"- License: {skill['license']}",
                f"- Local modifications: {skill.get('modifications', 'No local modifications.')}",
                "",
            ]
        )
    for (license_name, evidence), names in groups.items():
        notice = json.loads(evidence)
        applies = ", ".join(names[:-1]) + ", and " + names[-1] if len(names) > 2 else ", ".join(names)
        lines.extend([f"## {license_name} license materials", "", f"Applies to: {applies}.", ""])
        if license_name == "MIT":
            lines.extend([notice["copyright"], "", MIT_PERMISSION, ""])
        elif license_name == "CC-BY-SA-4.0":
            lines.extend([f"Official license text: {notice['license_url']}", ""])
        elif license_name == "Apache-2.0":
            for name in names:
                lines.extend([f"Skill-local license evidence: `skills/{name}/{notice['license_file']}`.", ""])
    return "\n".join(lines)


def write_notices(skills: Iterable[Dict[str, Any]]) -> None:
    """Publish a new file atomically; never open an existing notice for writing."""
    target = plugin_root / "THIRD_PARTY_NOTICES.md"
    validate_write_target(target)
    contents = render_notices(skills)
    descriptor, temporary = tempfile.mkstemp(prefix=".notices-", dir=plugin_root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(contents)
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sync() -> None:
    """Copy only the approved skills without mutating the maintainer source."""
    source_root = Path(os.environ.get(
        "CODEX_SKILLS_SOURCE", Path.home() / ".codex" / "skills"
    )).expanduser().resolve()
    destination_root = plugin_root / "skills"

    if not source_root.is_dir():
        raise ValueError(f"skill source root is not a directory: {source_root}")
    validate_write_target(plugin_root, source_root)
    notices_path = plugin_root / "THIRD_PARTY_NOTICES.md"
    validate_write_target(notices_path, source_root)
    if notices_path.exists() and not notices_path.is_file():
        raise ValueError("notice target must be a regular file")

    skills = load_lock()
    render_notices(skills)  # Validate all notice evidence before any mutation.
    names = [skill["name"] for skill in skills]
    source_dirs = []
    for skill in skills:
        name = skill["name"]
        if skill["source"] == REPOSITORY_OWNED_SOURCE:
            source_dir = destination_root / name
            source_parent = destination_root.resolve()
        else:
            source_dir = source_root / name
            source_parent = source_root
        if not source_dir.exists() or not source_dir.is_dir():
            raise ValueError(f"allowlisted source skill is missing: {source_dir}")
        resolved_source_dir = source_dir.resolve(strict=True)
        require_within(resolved_source_dir, source_parent, "source skill")
        validate_source_tree(source_dir)
        license_file = skill.get("notice", {}).get("license_file")
        if license_file:
            license_path = source_dir / license_file
            require_within(license_path.resolve(), resolved_source_dir, "license file")
            if not license_path.is_file():
                raise ValueError(f"missing local license evidence: {license_path}")
        source_dirs.append((name, source_dir))

    validate_destination(destination_root, source_root, names)
    staging_root = Path(tempfile.mkdtemp(prefix=".sync-skills-", dir=plugin_root.parent))
    try:
        build_snapshot(source_dirs, staging_root)
        destination_root.mkdir(parents=True, exist_ok=True)
        remove_stale_children(destination_root, names)
        for name in names:
            target = destination_root / name
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(staging_root / name), str(target))
        write_notices(skills)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


if __name__ == "__main__":
    sync()
