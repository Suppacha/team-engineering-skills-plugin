"""Trusted snapshot storage for the personal Desktop updater.

Candidate Git content is treated only as bytes.  This module never checks it
out and never imports code from a staged snapshot.
"""

from __future__ import annotations

from contextlib import contextmanager
import fnmatch
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile

from release_files import CATALOGS, DENIED_NAMES, DENIED_PARTS
from release_policy import validate_sha
from team_updater.release import Candidate


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = "plugins/team-engineering-skills"
REMOTE = "https://github.com/Suppacha/team-engineering-skills-plugin.git"
MARKER = ".team-updater-store"
MARKER_CONTENT = "team-plugin-personal-updater\n"
MAX_JSON = 64 * 1024
MAX_FILES = 5000
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
GIT_TIMEOUT = 30


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _has_reparse(path: Path) -> bool:
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, FileNotFoundError):
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _safe_root(value: Path) -> Path:
    _require(isinstance(value, Path) and value.is_absolute(), "unsafe-store-root")
    lexical = Path(os.path.abspath(value))
    # macOS exposes /var as a platform-owned compatibility link.  Canonicalize
    # that exact prefix, but never silently canonicalize a user-selected link.
    allowed_system_links = {Path("/var"), Path("/tmp")}
    for component in reversed((lexical, *lexical.parents)):
        if component in allowed_system_links:
            continue
        if component.is_symlink() or _has_reparse(component):
            raise ValueError("unsafe-store-root")
    root = lexical.resolve(strict=False)
    home = Path.home().resolve()
    project = ROOT.resolve()
    broad = {Path(root.anchor), home, project, Path.cwd().resolve(),
             Path(tempfile.gettempdir()).resolve(), Path("/private/tmp")}
    _require(root not in broad, "unsafe-store-root")
    for protected in (home, project, Path.cwd().resolve()):
        _require(root != protected and not protected.is_relative_to(root), "unsafe-store-root")
    existed = root.exists()
    if existed:
        _require(root.is_dir() and not root.is_symlink(), "unsafe-store-root")
        marker = root / MARKER
        _require(marker.is_file() and not marker.is_symlink()
                 and not _has_reparse(marker)
                 and marker.read_text(encoding="ascii") == MARKER_CONTENT,
                 "unowned-store-root")
    else:
        root.mkdir(mode=0o700, parents=False)
    marker = root / MARKER
    if not existed:
        marker.write_text(MARKER_CONTENT, encoding="ascii")
        try:
            marker.chmod(0o600)
        except OSError:
            pass
    return root


def _trusted_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    _require(spec is not None and spec.loader is not None, "trusted-validator-unavailable")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _safe_path(name: str) -> PurePosixPath:
    _require(isinstance(name, str) and bool(name) and not name.startswith("/")
             and "\\" not in name and ":" not in name
             and not any(ord(character) < 32 for character in name), "unsafe-tree-path")
    parts = name.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    _require(all(part not in ("", ".", "..") and not part.endswith((" ", "."))
                 and part.split(".")[0].upper() not in reserved for part in parts),
             "unsafe-portable-tree-path")
    return PurePosixPath(name)


def _selected(path: PurePosixPath) -> bool:
    name = path.as_posix()
    return (name.startswith(PLUGIN + "/") or name in CATALOGS
            or name in {"config/skills-lock.json", "LICENSE", "CHANGELOG.md"})


def _validate_tree(entries):
    """Validate all Git entries before returning the release allowlist."""
    _require(isinstance(entries, list) and len(entries) <= MAX_FILES, "oversized-git-tree")
    seen = set()
    selected = []
    total = 0
    for entry in entries:
        _require(isinstance(entry, tuple) and len(entry) == 5, "invalid-git-tree")
        mode, kind, object_sha, size, name = entry
        path = _safe_path(name)
        folded = name.casefold()
        _require(folded not in seen, "case-colliding-git-path")
        seen.add(folded)
        if kind == "tree" and mode == "040000":
            _require(size is None, "invalid-git-tree")
            continue
        _require(kind == "blob" and mode in ("100644", "100755"),
                 "links-submodules-and-reparse-entries-forbidden")
        validate_sha(object_sha)
        _require(type(size) is int and 0 <= size <= MAX_FILE, "oversized-git-blob")
        total += size
        _require(total <= MAX_TOTAL, "oversized-git-tree")
        if not _selected(path):
            continue
        _require(not any(part in DENIED_PARTS
                         or any(fnmatch.fnmatch(part.lower(), pattern) for pattern in DENIED_NAMES)
                         for part in path.parts), "denied-packaged-file")
        selected.append(entry)
    return selected


def _open_lock_file(path: Path):
    """Open the lock itself without following a final Windows reparse point."""
    if os.name != "nt":
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        return os.fdopen(descriptor, "r+b")

    import ctypes
    from ctypes import wintypes
    import msvcrt

    class FileAttributeTagInfo(ctypes.Structure):
        _fields_ = [("file_attributes", wintypes.DWORD),
                    ("reparse_tag", wintypes.DWORD)]

    create_file = ctypes.windll.kernel32.CreateFileW
    create_file.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                            wintypes.HANDLE]
    create_file.restype = wintypes.HANDLE
    get_info = ctypes.windll.kernel32.GetFileInformationByHandleEx
    get_info.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                         wintypes.DWORD]
    get_info.restype = wintypes.BOOL
    close_handle = ctypes.windll.kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    generic_read_write = 0x80000000 | 0x40000000
    # Other contenders may inspect/open the lock, but cannot unlink or replace
    # the directory entry while this instance holds the native handle.
    share_read_write = 0x1 | 0x2
    open_always = 4
    file_attribute_normal = 0x80
    file_flag_open_reparse_point = 0x00200000
    handle = create_file(str(path), generic_read_write, share_read_write,
                         None, open_always,
                         file_attribute_normal | file_flag_open_reparse_point,
                         None)
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        raise ctypes.WinError()
    try:
        info = FileAttributeTagInfo()
        # FileAttributeTagInfo is FILE_INFO_BY_HANDLE_CLASS value 9.
        if not get_info(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError()
        file_attribute_directory = 0x10
        file_attribute_reparse_point = 0x400
        if info.file_attributes & (file_attribute_directory | file_attribute_reparse_point):
            raise ValueError("unsafe-lock-file")
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDWR)
        handle = None  # descriptor owns the native handle now
        return os.fdopen(descriptor, "r+b")
    finally:
        if handle is not None:
            close_handle(handle)


def _parse_tree(raw: bytes):
    entries = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_name = record.split(b"\t", 1)
            mode, kind, object_sha, raw_size = metadata.split()
            name = raw_name.decode("utf-8", "strict")
            size = None if raw_size == b"-" else int(raw_size)
            entries.append((mode.decode("ascii"), kind.decode("ascii"),
                            object_sha.decode("ascii"), size, name))
        except (ValueError, UnicodeError):
            raise ValueError("invalid-git-tree") from None
    return entries


def _read_json(path: Path, *, missing, label: str):
    if not path.exists():
        if path.is_symlink():
            raise ValueError("invalid-" + label)
        return missing
    if path.is_symlink() or _has_reparse(path) or not path.is_file():
        raise ValueError("invalid-" + label)
    try:
        raw = path.read_bytes()
        _require(len(raw) <= MAX_JSON, "invalid-" + label)
        value = json.loads(raw)
        _require(isinstance(value, dict), "invalid-" + label)
        return value
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        raise ValueError("invalid-" + label) from None


def _write_json(path: Path, value: dict, *, label: str) -> None:
    _require(isinstance(value, dict), "invalid-" + label)
    try:
        raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    except (TypeError, ValueError):
        raise ValueError("invalid-" + label) from None
    _require(len(raw) <= MAX_JSON, "invalid-" + label)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            pass
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def validate_snapshot(path: Path, candidate: Candidate) -> dict:
    _require(isinstance(candidate, Candidate), "invalid-candidate")
    validate_sha(candidate.sha)
    snapshot = Path(path)
    _require(snapshot.is_dir() and not snapshot.is_symlink(), "invalid-snapshot")
    for item in snapshot.rglob("*"):
        _require(not item.is_symlink() and not _has_reparse(item), "invalid-snapshot-link")
    framework = _trusted_module("updater_trusted_framework", PLUGIN + "/scripts/framework.py")
    registry = framework.validate_release(snapshot / PLUGIN)
    _require(registry.get("version") == candidate.version, "package-version-mismatch")

    for name in CATALOGS:
        try:
            catalog = json.loads((snapshot / name).read_text(encoding="utf-8"))
            _require(catalog.get("name") == "team-engineering-skills-marketplace",
                     "marketplace-identity-mismatch")
            plugins = catalog.get("plugins")
            _require(isinstance(plugins, list) and len(plugins) == 1
                     and plugins[0].get("name") == "team-engineering-skills",
                     "marketplace-plugin-mismatch")
            expected = "./" + PLUGIN
            if name.startswith(".agents/"):
                _require(plugins[0].get("source") == {"source": "local", "path": expected},
                         "marketplace-source-mismatch")
            else:
                _require(plugins[0].get("source") == expected
                         and plugins[0].get("version") == candidate.version,
                         "marketplace-source-mismatch")
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            raise ValueError("invalid-marketplace") from None

    licenses_module = _trusted_module("updater_trusted_licenses", "scripts/sync-skills.py")
    try:
        lock = json.loads((snapshot / "config/skills-lock.json").read_text(encoding="utf-8"))
        entries = lock.get("skills")
        _require(isinstance(entries, list) and bool(entries), "missing-license-allowlist")
        licenses = {}
        registry_names = {skill["name"] for skill in registry["skills"]}
        for entry in entries:
            _require(isinstance(entry, dict)
                     and all(isinstance(entry.get(key), str) and entry[key].strip()
                             for key in licenses_module.REQUIRED_FIELDS), "incomplete-license-evidence")
            licenses_module.validate_license_evidence(entry)
            name = entry["name"]
            _require(name not in licenses and name in registry_names, "invalid-license-entry")
            if entry["license"] == "Apache-2.0":
                relative = _safe_path(entry["notice"]["license_file"])
                skill_root = (snapshot / PLUGIN / "skills" / name).resolve()
                license_path = (skill_root / relative).resolve()
                _require(license_path.is_relative_to(skill_root) and license_path.is_file()
                         and bool(license_path.read_bytes().strip()), "missing-apache-license")
            licenses[name] = entry
        _require(set(licenses) == registry_names, "license-allowlist-mismatch")
        notices = (snapshot / PLUGIN / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        _require(notices == licenses_module.render_notices(entries), "license-notices-mismatch")
        _require(bool((snapshot / "LICENSE").read_bytes().strip()), "missing-distribution-license")
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, AttributeError):
        raise ValueError("invalid-license-evidence") from None
    return registry


class Store:
    def __init__(self, root: Path, *, run=subprocess.run):
        self.root = _safe_root(root)
        self._run = run
        self.staging = self.root / "staging"
        self.current = self.root / "current"
        self.previous = self.root / "previous"
        self.state = self.root / "state.json"
        self.journal = self.root / "journal.json"
        self.lock_file = self.root / ".lock"
        self.staging.mkdir(mode=0o700, exist_ok=True)
        _require(self.staging.is_dir() and not self.staging.is_symlink()
                 and not _has_reparse(self.staging), "unsafe-store-root")

    @contextmanager
    def lock(self):
        try:
            handle = _open_lock_file(self.lock_file)
        except (OSError, ValueError):
            raise ValueError("unsafe-lock-file") from None
        try:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0, os.SEEK_END)
                    if handle.tell() == 0:
                        handle.write(b"\0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, IOError):
                raise BlockingIOError("updater-busy") from None
            yield
        finally:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            handle.close()

    def read_state(self) -> dict:
        return _read_json(self.state, missing={}, label="state")

    def write_state(self, value: dict) -> None:
        _write_json(self.state, value, label="state")

    def read_journal(self) -> dict | None:
        return _read_json(self.journal, missing=None, label="journal")

    def write_journal(self, value: dict | None) -> None:
        if value is None:
            try:
                self.journal.unlink()
            except FileNotFoundError:
                pass
            return
        _write_json(self.journal, value, label="journal")

    @staticmethod
    def _git_environment() -> dict:
        environment = {key: value for key, value in os.environ.items()
                       if not key.upper().startswith("GIT_") and key not in {"SSH_ASKPASS", "GIT_ASKPASS"}}
        environment.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
                            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
                            "GIT_ASKPASS": "", "SSH_ASKPASS": ""})
        return environment

    def _run_git(self, executable: Path, git_dir: Path, arguments: list[str], *, input_data=None):
        command = [str(executable), "--git-dir=" + str(git_dir),
                   "-c", "credential.helper=", "-c", "core.hooksPath=" + os.devnull,
                   "-c", "filter.lfs.smudge=", "-c", "filter.lfs.required=false",
                   "-c", "protocol.file.allow=never", "-c", "protocol.ext.allow=never",
                   *arguments]
        return self._run(command, input=input_data, capture_output=True, check=True,
                         timeout=GIT_TIMEOUT, env=Store._git_environment())

    def stage(self, candidate: Candidate, git_executable: Path) -> Path:
        _require(isinstance(candidate, Candidate), "invalid-candidate")
        validate_sha(candidate.sha)
        _require(isinstance(git_executable, Path) and git_executable.is_absolute(), "invalid-git-executable")
        git = git_executable.resolve(strict=True)
        _require(git.is_file() and not git_executable.is_symlink(), "invalid-git-executable")
        work = Path(tempfile.mkdtemp(prefix=".incoming-", dir=self.staging))
        database = work / "objects.git"
        snapshot = work / "snapshot"
        templates = work / "empty-templates"
        templates.mkdir()
        try:
            self._run([str(git), "init", "--bare", "--template=" + str(templates), str(database)],
                      capture_output=True, check=True, timeout=GIT_TIMEOUT,
                      env=self._git_environment())
            self._run_git(git, database, ["remote", "add", "origin", REMOTE])
            self._run_git(git, database, ["fetch", "--no-tags", "--depth=1", "origin",
                                                candidate.sha + ":refs/heads/candidate"])
            self._run_git(git, database, ["symbolic-ref", "HEAD", "refs/heads/candidate"])
            fetched = self._run_git(git, database, ["rev-parse", "FETCH_HEAD^{commit}"]).stdout.decode("ascii").strip()
            head = self._run_git(git, database, ["rev-parse", "HEAD^{commit}"]).stdout.decode("ascii").strip()
            _require(fetched == candidate.sha and head == candidate.sha, "git-candidate-mismatch")
            self._run_git(git, database, ["cat-file", "-e", candidate.sha + "^{commit}"])
            raw_tree = self._run_git(git, database, ["ls-tree", "-rz", "-l", candidate.sha]).stdout
            entries = _validate_tree(_parse_tree(raw_tree))
            snapshot.mkdir(mode=0o700)
            for _mode, _kind, object_sha, size, name in entries:
                data = self._run_git(git, database, ["cat-file", "blob", object_sha]).stdout
                digest = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
                _require(len(data) == size and digest == object_sha, "git-blob-mismatch")
                destination = snapshot.joinpath(*PurePosixPath(name).parts)
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with destination.open("xb") as handle:
                    handle.write(data)
                destination.chmod(0o600)
            validate_snapshot(snapshot, candidate)
            destination = self.staging / candidate.sha
            _require(not destination.exists(), "candidate-already-staged")
            os.replace(snapshot, destination)
            return destination
        except subprocess.SubprocessError:
            raise RuntimeError("git-staging-failed") from None
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def _owned_staged(self, staged: Path) -> Path:
        _require(isinstance(staged, Path) and staged.parent == self.staging
                 and staged.name not in ("", ".", "..") and staged.is_dir()
                 and not staged.is_symlink(), "staged-path-outside-store")
        _require(staged.resolve().parent == self.staging.resolve(), "staged-path-outside-store")
        return staged

    def activate(self, staged: Path) -> None:
        staged = self._owned_staged(staged)
        rollback = self.root / ".activation-old"
        _require(not rollback.exists(), "repair-required")
        had_current = self.current.exists()
        if had_current:
            os.replace(self.current, rollback)
        try:
            os.replace(staged, self.current)
        except BaseException:
            if had_current:
                os.replace(rollback, self.current)
            raise
        if self.previous.exists():
            shutil.rmtree(self.previous)
        if had_current:
            os.replace(rollback, self.previous)

    def restore_previous(self) -> None:
        _require(self.previous.is_dir() and not self.previous.is_symlink(), "previous-unavailable")
        temporary = self.root / ".restore-current"
        _require(not temporary.exists(), "repair-required")
        had_current = self.current.exists()
        if had_current:
            os.replace(self.current, temporary)
        try:
            os.replace(self.previous, self.current)
        except BaseException:
            if had_current:
                os.replace(temporary, self.current)
            raise
        if had_current:
            os.replace(temporary, self.previous)
