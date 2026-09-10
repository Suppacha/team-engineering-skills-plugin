"""Portable source-distribution allowlist (does not depend on .git).

This is accidental-file exclusion, not a secret-content scanner. Review every
release diff: a credential embedded in an ordinary source file is not detected.
"""
from pathlib import Path
import fnmatch

ROOT_FILES = {"README.md", "CHANGELOG.md", "LICENSE", ".gitignore"}
ROOT_DIRS = {"plugins", "config", "scripts", "tests", "docs", ".github"}
CATALOGS = {".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"}
DENIED_PARTS = {".git", ".system", ".idea", ".pytest_cache", ".superpowers", ".sdd",
                ".vscode", "__pycache__", "dist", "reverse-skill-router", ".DS_Store"}
DENIED_NAMES = (".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*",
                "id_ed25519*", "*.pyc", "*.pyo", "*.swp", "*~")


def release_files(root):
    root = Path(root)
    files = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        name = relative.as_posix()
        if not (name in ROOT_FILES or name in CATALOGS or relative.parts[0] in ROOT_DIRS):
            continue
        if any(part in DENIED_PARTS for part in relative.parts):
            continue
        if any(fnmatch.fnmatch(part.lower(), pattern) for part in relative.parts for pattern in DENIED_NAMES):
            continue
        if any(relative.parts[i:i+2] == ("plugins", "cache") for i in range(len(relative.parts)-1)):
            continue
        if path.is_symlink():
            raise ValueError("refusing release symlink: " + name)
        if path.is_file():
            files.append((name, path))
    return sorted(files)
