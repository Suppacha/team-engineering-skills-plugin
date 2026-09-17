"""Fail-closed adapter for the bundled Codex plugin CLI."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import weakref

from team_updater.release import Candidate


MARKETPLACE = "team-engineering-skills-marketplace"
PLUGIN = "team-engineering-skills"
SELECTOR = PLUGIN + "@" + MARKETPLACE
TIMEOUT = 30
MAX_OUTPUT = 1024 * 1024


def _require(value, code):
    if not value:
        raise ValueError(code)


def _same_path(left, right):
    try:
        return Path(left).resolve(strict=False) == Path(right).resolve(strict=False)
    except (OSError, TypeError, ValueError):
        return False


def _tree(path: Path) -> dict:
    _require(path.is_dir() and not path.is_symlink(), "invalid-plugin-cache")
    result = {}
    for item in sorted(path.rglob("*")):
        _require(not item.is_symlink(), "invalid-plugin-cache")
        if item.is_file():
            relative = item.relative_to(path).as_posix()
            result[relative] = hashlib.sha256(item.read_bytes()).hexdigest()
        else:
            _require(item.is_dir(), "invalid-plugin-cache")
    return result


def _bounded_run(command, *, input, capture_output, shell, check, timeout, cwd, env):
    """Run without ever retaining more than MAX_OUTPUT from either pipe."""
    _require(input is None and capture_output and shell is False, "invalid-client-command")
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, shell=False, cwd=cwd, env=env)
    exceeded = threading.Event()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}

    def read_stream(name, stream):
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk:
                return
            buffer = buffers[name]
            remaining = MAX_OUTPUT + 1 - len(buffer)
            if remaining > 0:
                buffer.extend(chunk[:remaining])
            if len(buffer) > MAX_OUTPUT:
                exceeded.set()
                return

    readers = [threading.Thread(target=read_stream, args=(name, stream), daemon=True)
               for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))]
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            if exceeded.wait(0.01):
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise RuntimeError("client-output-limit")
            if time.monotonic() >= deadline:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise subprocess.TimeoutExpired(command, timeout)
        for reader in readers:
            reader.join(timeout=1)
        if exceeded.is_set():
            raise RuntimeError("client-output-limit")
        stdout, stderr = bytes(buffers["stdout"]), bytes(buffers["stderr"])
        if check and process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command,
                                                output=stdout, stderr=b"")
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    finally:
        if process.poll() is None:
            process.kill()
        process.stdout.close()
        process.stderr.close()


class CodexClient:
    def __init__(self, executable: Path, run=None, codex_home: Path | None = None):
        _require(isinstance(executable, Path) and executable.is_absolute(), "invalid-codex-executable")
        _require(executable.is_file() and not executable.is_symlink(), "invalid-codex-executable")
        home = codex_home if codex_home is not None else Path(os.environ.get("CODEX_HOME", ""))
        _require(isinstance(home, Path) and home.is_absolute(), "invalid-codex-home")
        home.mkdir(mode=0o700, parents=True, exist_ok=True)
        _require(home.is_dir() and not home.is_symlink(), "invalid-codex-home")
        self.executable = executable.resolve(strict=True)
        self.codex_home = home.resolve(strict=True)
        self._run = _bounded_run if run is None else run
        self._working_directory = Path(tempfile.mkdtemp(prefix="team-updater-client-")).resolve()
        self._cleanup_working = weakref.finalize(
            self, shutil.rmtree, self._working_directory, True)
        self._source = None
        self._evidence = None

    def _command(self, arguments, *, json_result=False, cwd=None):
        environment = dict(os.environ)
        environment["CODEX_HOME"] = str(self.codex_home)
        try:
            completed = self._run([str(self.executable), *arguments], input=None,
                                  capture_output=True, shell=False, check=True,
                                  timeout=TIMEOUT, cwd=cwd or self._working_directory,
                                  env=environment)
        except subprocess.TimeoutExpired:
            raise RuntimeError("client-status-unknown") from None
        except subprocess.SubprocessError:
            raise RuntimeError("client-command-failed") from None
        raw = completed.stdout
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        stderr = completed.stderr
        if isinstance(stderr, str):
            stderr = stderr.encode("utf-8")
        _require(isinstance(raw, bytes) and isinstance(stderr, bytes)
                 and len(raw) <= MAX_OUTPUT and len(stderr) <= MAX_OUTPUT,
                 "unsupported-client-response")
        if not json_result:
            try:
                return raw.decode("utf-8").strip()
            except UnicodeError:
                raise ValueError("unsupported-client-response") from None
        try:
            value = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError):
            raise ValueError("unsupported-client-response") from None
        _require(isinstance(value, dict), "unsupported-client-response")
        return value

    def probe(self) -> dict:
        version = self._command(["--version"])
        _require(version.startswith("codex-cli "), "unsupported-client")
        self._command(["plugin", "--help"])
        self._command(["plugin", "marketplace", "--help"])
        return {"version": version, "codex_home": str(self.codex_home)}

    def _marketplaces(self):
        value = self._command(["plugin", "marketplace", "list", "--json"], json_result=True)
        entries = value.get("marketplaces")
        _require(isinstance(entries, list), "unsupported-client-response")
        for entry in entries:
            _require(isinstance(entry, dict), "unsupported-client-response")
        return entries

    def inventory(self) -> dict | None:
        value = self._command(["plugin", "list", "--json"], json_result=True)
        installed, available = value.get("installed"), value.get("available")
        _require(isinstance(installed, list) and isinstance(available, list),
                 "unsupported-client-response")
        matches = [item for item in installed if isinstance(item, dict)
                   and (item.get("pluginId") == SELECTOR or item.get("name") == PLUGIN)]
        _require(len(matches) <= 1, "unsupported-client-response")
        if not matches:
            return None
        item = matches[0]
        _require(item.get("pluginId") == SELECTOR
                 and item.get("marketplaceName") == MARKETPLACE, "source-collision")
        expected = {"name": PLUGIN, "marketplaceName": MARKETPLACE,
                    "installed": True, "installPolicy": "AVAILABLE", "authPolicy": "ON_USE"}
        _require(all(item.get(key) == value for key, value in expected.items())
                 and isinstance(item.get("version"), str), "unsupported-client-response")
        source = item.get("source")
        market = item.get("marketplaceSource")
        _require(isinstance(source, dict) and source.get("source") == "local"
                 and isinstance(source.get("path"), str)
                 and isinstance(market, dict) and market.get("sourceType") == "local"
                 and isinstance(market.get("source"), str), "unsupported-client-response")
        if self._source is not None:
            _require(_same_path(market["source"], self._source)
                     and _same_path(source["path"], self._source / "plugins" / PLUGIN),
                     "source-collision")
        return {"version": item["version"], "enabled": item.get("enabled") is True,
                "source": market["source"]}

    def validate_source(self, source: Path) -> None:
        """Reject a same-name registration owned by anything else, without mutation."""
        _require(isinstance(source, Path) and source.is_absolute(), "invalid-source")
        self._source = source.resolve(strict=False)
        for entry in self._marketplaces():
            if entry.get("name") != MARKETPLACE:
                continue
            market = entry.get("marketplaceSource")
            _require(isinstance(market, dict) and market.get("sourceType") == "local"
                     and _same_path(entry.get("root"), source)
                     and _same_path(market.get("source"), source), "source-collision")
        self.inventory()

    def register(self, source: Path):
        _require(isinstance(source, Path) and source.is_absolute() and source.is_dir()
                 and not source.is_symlink(), "invalid-source")
        source = source.resolve(strict=True)
        self.validate_source(source)
        for entry in self._marketplaces():
            if entry.get("name") == MARKETPLACE:
                market = entry.get("marketplaceSource")
                _require(isinstance(market, dict) and market.get("sourceType") == "local"
                         and _same_path(entry.get("root"), source)
                         and _same_path(market.get("source"), source), "source-collision")
                self._source = source
                return {"already_added": True}
        value = self._command(["plugin", "marketplace", "add", "--json", str(source)],
                              json_result=True, cwd=source)
        _require(set(value) == {"marketplaceName", "installedRoot", "alreadyAdded"}
                 and value["marketplaceName"] == MARKETPLACE
                 and _same_path(value["installedRoot"], source)
                 and type(value["alreadyAdded"]) is bool, "unsupported-client-response")
        self._source = source
        return {"already_added": value["alreadyAdded"]}

    def bind_evidence(self, evidence):
        if evidence is None:
            self._evidence = None
            return
        _require(isinstance(evidence, dict) and set(evidence) == {"installed_path", "tree"}
                 and isinstance(evidence["installed_path"], str)
                 and isinstance(evidence["tree"], dict), "invalid-install-evidence")
        self._evidence = evidence

    def install(self, source: Path, candidate: Candidate) -> dict:
        _require(self._source is not None and _same_path(source, self._source), "source-not-registered")
        current = self.inventory()
        if current is not None and not current["enabled"]:
            raise ValueError("plugin-disabled")
        try:
            value = self._command(["plugin", "add", "--json", SELECTOR],
                                  json_result=True, cwd=source)
        except RuntimeError as error:
            if str(error) not in {"client-status-unknown", "client-command-failed"}:
                raise
            current = self.inventory()
            if current is None or current["version"] != candidate.version or not current["enabled"]:
                raise RuntimeError(str(error)) from None
            expected_path = self.codex_home / "plugins/cache" / MARKETPLACE / PLUGIN / candidate.version
            value = {"pluginId": SELECTOR, "name": PLUGIN, "marketplaceName": MARKETPLACE,
                     "version": candidate.version, "installedPath": str(expected_path),
                     "authPolicy": "ON_USE"}
        expected_path = (self.codex_home / "plugins/cache" / MARKETPLACE / PLUGIN
                         / candidate.version).resolve(strict=False)
        _require(set(value) == {"pluginId", "name", "marketplaceName", "version",
                               "installedPath", "authPolicy"}
                 and value["pluginId"] == SELECTOR and value["name"] == PLUGIN
                 and value["marketplaceName"] == MARKETPLACE
                 and value["version"] == candidate.version and value["authPolicy"] == "ON_USE"
                 and _same_path(value["installedPath"], expected_path),
                 "unsupported-client-response")
        source_tree = _tree(source / "plugins" / PLUGIN)
        cache_tree = _tree(expected_path)
        _require(cache_tree == source_tree, "installed-cache-mismatch")
        self._evidence = {"installed_path": str(expected_path), "tree": source_tree}
        return {"version": candidate.version, **self._evidence}

    def verify(self, source: Path, candidate: Candidate) -> bool:
        try:
            self._source = source.resolve(strict=True)
            current = self.inventory()
            expected_path = (self.codex_home / "plugins/cache" / MARKETPLACE / PLUGIN
                             / candidate.version).resolve(strict=False)
            if (current is None or not current["enabled"] or current["version"] != candidate.version
                    or self._evidence is None
                    or not _same_path(self._evidence.get("installed_path"), expected_path)):
                return False
            source_tree = _tree(source / "plugins" / PLUGIN)
            return self._evidence.get("tree") == source_tree == _tree(expected_path)
        except (OSError, ValueError, RuntimeError):
            return False
