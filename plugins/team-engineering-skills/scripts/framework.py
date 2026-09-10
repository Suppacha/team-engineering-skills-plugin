"""Offline release metadata checks. Hashes detect drift, not publisher identity."""
from pathlib import Path
import hashlib
import json
import re

STANDARD_FILES = {"security.md", "ai-usage.md", "data-access.md", "coding-output.md"}
SEMVER = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def safe_directory(value):
    path = Path(value).absolute()
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError("refusing symlinked directory or ancestor")
    if not path.is_dir():
        raise ValueError("directory must already exist")
    return path.resolve()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def tree_digest(root):
    """Hash ordered relative filenames and bytes with unambiguous separators."""
    result = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("refusing symlink in skill payload")
        if path.is_file():
            result.update(path.relative_to(root).as_posix().encode("utf-8"))
            result.update(b"\0")
            result.update(hashlib.sha256(path.read_bytes()).digest())
    return result.hexdigest()


def validate_release(plugin):
    plugin = safe_directory(plugin)
    # Reject links before reading metadata or policy, including dangling links.
    for path in plugin.rglob("*"):
        if path.is_symlink():
            raise ValueError("refusing symlink in release")
    try:
        registry = json.loads((plugin / "registry.json").read_text(encoding="utf-8"))
        version = (plugin / "VERSION").read_text().strip()
        if not SEMVER.fullmatch(version) or registry["version"] != version:
            raise ValueError("release/registry version mismatch")
        if registry["schema_version"] != 1 or not registry["owner"].strip():
            raise ValueError("missing governance owner or unsupported registry schema")
        for client in (".codex-plugin", ".claude-plugin"):
            manifest = json.loads((plugin / client / "plugin.json").read_text())
            if manifest["version"] != version or manifest["name"] != "team-engineering-skills":
                raise ValueError("plugin identity/version mismatch")
        if set(registry["standards"]) != STANDARD_FILES:
            raise ValueError("required standards are missing or unexpected")
        for name, expected in registry["standards"].items():
            if digest((plugin / "standards" / name).read_bytes()) != expected:
                raise ValueError("standard hash mismatch: " + name)
        names = []
        for skill in registry["skills"]:
            name = skill["name"]
            if not NAME.fullmatch(name) or name in names:
                raise ValueError("unsafe or duplicate skill name")
            names.append(name)
            if not SEMVER.fullmatch(skill["version"]) or not skill["owner"].strip():
                raise ValueError("skill requires version and owner")
            routes = skill["routes"]
            if not isinstance(routes, list) or not routes or any(not isinstance(r, str) or not r.strip() for r in routes):
                raise ValueError("skill requires task routes")
            root = plugin / "skills" / name
            if not (root / "SKILL.md").is_file() or tree_digest(root) != skill["tree_sha256"]:
                raise ValueError("skill payload missing or hash mismatch: " + name)
        actual = {p.name for p in (plugin / "skills").iterdir() if p.is_dir()}
        if set(names) != actual or not names:
            raise ValueError("registry does not cover packaged skills")
        return registry
    except (KeyError, TypeError, AttributeError, OSError, json.JSONDecodeError) as error:
        raise ValueError("invalid or incomplete release metadata") from error
