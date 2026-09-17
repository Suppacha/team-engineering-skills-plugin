"""Lifecycle CLI for the Team Engineering Skills personal updater."""

from __future__ import annotations

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile

from team_updater.client import CodexClient
from team_updater.engine import Updater
from team_updater.release import PublicReleaseClient
from team_updater.scheduler import Scheduler
from team_updater.store import Store


SOURCE_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_FILES = (
    "scripts/team-update.py",
    "scripts/release_files.py",
    "scripts/release_policy.py",
    "scripts/sync-skills.py",
    "plugins/team-engineering-skills/scripts/framework.py",
    "scripts/team_updater/__init__.py",
    "scripts/team_updater/client.py",
    "scripts/team_updater/engine.py",
    "scripts/team_updater/release.py",
    "scripts/team_updater/scheduler.py",
    "scripts/team_updater/store.py",
    "scripts/team_updater/cli.py",
)
CONFIG = "updater-config.json"


def default_state_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/TeamEngineeringSkillsUpdater"
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            raise RuntimeError("app-data-unavailable")
        return Path(base) / "TeamEngineeringSkillsUpdater"
    raise RuntimeError("unsupported-platform")


def runtime_files() -> tuple[str, ...]:
    """The deliberate trusted runtime allowlist, shared with packaging."""
    return RUNTIME_FILES


def _absolute_executable(value: str, label: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        resolved = shutil.which(value)
        if not resolved:
            raise ValueError("missing-" + label)
        candidate = Path(resolved)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        raise ValueError("missing-" + label) from None
    if not resolved.is_file():
        raise ValueError("missing-" + label)
    return resolved


def _validate_install(args):
    if sys.platform not in ("darwin", "win32"):
        raise RuntimeError("unsupported-platform")
    if sys.version_info < (3, 11):
        raise RuntimeError("unsupported-python")
    state_dir = Path(args.state_dir).expanduser().absolute()
    if state_dir.exists() and not state_dir.is_dir():
        raise ValueError("invalid-state-dir")
    codex = _absolute_executable(args.codex, "codex")
    git = _absolute_executable(args.git, "git")
    python = _absolute_executable(sys.executable, "python")
    # Probe against a fresh, credential-free profile before the requested
    # installation directory or its configuration is created.
    with tempfile.TemporaryDirectory(prefix="team-updater-probe-") as directory:
        probe = CodexClient(codex, codex_home=Path(directory) / "codex-profile")
        try:
            probe.probe()
        finally:
            probe._cleanup_working()
    return state_dir, codex, git, python


def _freeze_runtime(root: Path) -> Path:
    runtime = root / "runtime"
    temporary = Path(tempfile.mkdtemp(prefix=".runtime-", dir=root))
    try:
        for relative in RUNTIME_FILES:
            source = SOURCE_ROOT / relative
            if not source.is_file() or source.is_symlink():
                raise RuntimeError("trusted-runtime-unavailable")
            destination = temporary / relative
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            destination.chmod(0o600)
        old = root / ".runtime-old"
        if old.exists():
            shutil.rmtree(old)
        if runtime.exists():
            os.replace(runtime, old)
        os.replace(temporary, runtime)
        if old.exists():
            shutil.rmtree(old)
        return runtime
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _write_config(root: Path, values: dict) -> None:
    raw = (json.dumps(values, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(prefix=".config-", dir=root)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(raw)
        os.replace(temporary, root / CONFIG)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try: os.unlink(temporary)
        except FileNotFoundError: pass


def _read_config(root: Path) -> dict:
    path = root / CONFIG
    try:
        value = json.loads(path.read_bytes())
        if (not isinstance(value, dict) or set(value) != {"codex", "git", "python", "entry"}
                or not all(isinstance(item, str) and Path(item).is_absolute()
                           for item in value.values())):
            raise ValueError
        return value
    except (OSError, ValueError, json.JSONDecodeError):
        raise RuntimeError("invalid-updater-config") from None


def _logger(root: Path):
    logs = root / "logs"
    logs.mkdir(mode=0o700, exist_ok=True)
    logger = logging.getLogger("team_updater")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(logs / "updater.log", maxBytes=1048576,
                                  backupCount=4, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)
    return logger


def _status(state, scheduler):
    installed = state.get("installed") if isinstance(state.get("installed"), dict) else {}
    available = state.get("available") if isinstance(state.get("available"), dict) else {}
    return {
        "scheduler_enabled": scheduler.status(),
        "configured_enabled": state.get("enabled") is True,
        "installed_version": installed.get("version", "unknown"),
        "installed_sha": installed.get("sha", "unknown"),
        "available_version": available.get("version", "unknown"),
        "last_check": state.get("last_check", "unknown"),
        "last_result": state.get("last_result", "unknown"),
        "reload_required": state.get("reload_required") is True,
        "loaded_session": "unknown",
    }


def _rollback_proven_scheduler(scheduler) -> None:
    """Remove only a definition whose adapter can prove it owns and sees active."""
    try:
        if scheduler.status():
            scheduler.disable()
            if scheduler.status():
                raise RuntimeError("scheduler-readback-failed")
    except (OSError, ValueError, RuntimeError):
        # Unknown ownership is deliberately left untouched.  The persisted
        # repair-required state prevents a blind lifecycle retry.
        return


def run_lifecycle(command, store, engine, scheduler, *, output=sys.stdout, json_output=True):
    if command == "status":
        value = _status(engine.status(), scheduler)
    elif command == "check":
        value = _status(engine.check(), scheduler)
    else:
        with store.lock():
            state = engine.reconcile_completed_locked()
            if command == "resume":
                if state.get("last_result") == "repair-required":
                    raise RuntimeError("repair-required")
                if not isinstance(state.get("installed"), dict):
                    raise RuntimeError("initial-install-required")
                client = getattr(engine, "client", None)
                if client is not None:
                    client.probe()
                    client.validate_source(store.current)
                    if client.inventory() is None:
                        raise RuntimeError("installed-plugin-unavailable")
            elif command not in ("pause", "uninstall-updater"):
                raise ValueError("invalid-command")
            try:
                if command in ("pause", "uninstall-updater"):
                    scheduler.disable()
                    if scheduler.status():
                        raise RuntimeError("scheduler-readback-failed")
                    state["enabled"] = False
                elif command == "resume":
                    scheduler.enable()
                    if not scheduler.status():
                        raise RuntimeError("scheduler-readback-failed")
                    state["enabled"] = True
                store.write_state(state)
            except (OSError, ValueError, RuntimeError):
                if command == "resume":
                    _rollback_proven_scheduler(scheduler)
                state["enabled"] = False
                state["last_result"] = "repair-required"
                store.write_state(state)
                raise
        value = _status(state, scheduler)
    if json_output:
        output.write(json.dumps(value, sort_keys=True) + "\n")
    else:
        output.write("enabled={} installed={} available={} result={} loaded={}\n".format(
            value["scheduler_enabled"], value["installed_version"],
            value["available_version"], value["last_result"], value["loaded_session"]))
    return 0


def _components(root: Path, config: dict):
    store = Store(root)
    client = CodexClient(Path(config["codex"]), codex_home=root / "codex-profile")
    engine = Updater(store, PublicReleaseClient(), client, Path(config["git"]))
    scheduler = Scheduler(root, Path(config["python"]), Path(config["entry"]))
    return store, engine, scheduler


def _install(args, output):
    root, codex, git, python = _validate_install(args)
    store = Store(root)
    runtime = _freeze_runtime(root)
    entry = (runtime / "scripts/team-update.py").resolve(strict=True)
    config = {"codex": str(codex), "git": str(git), "python": str(python), "entry": str(entry)}
    _write_config(root, config)
    client = CodexClient(codex, codex_home=root / "codex-profile")
    engine = Updater(store, PublicReleaseClient(), client, git)
    scheduler = Scheduler(root, python, entry)
    state = engine.install_initial()
    if state.get("last_result") != "installed":
        raise RuntimeError("initial-install-failed")
    with store.lock():
        state = engine.reconcile_completed_locked()
        try:
            scheduler.enable()
            if not scheduler.status():
                raise RuntimeError("scheduler-readback-failed")
            state["enabled"] = True
            store.write_state(state)
        except (OSError, ValueError, RuntimeError):
            _rollback_proven_scheduler(scheduler)
            state["enabled"] = False
            state["last_result"] = "repair-required"
            store.write_state(state)
            raise
    command = [str(python), str(entry), "status", "--state-dir", str(root)]
    rendered = subprocess.list2cmdline(command) if sys.platform == "win32" else shlex.join(command)
    value = _status(state, scheduler)
    if args.json:
        value["management_command"] = rendered
        output.write(json.dumps(value, sort_keys=True) + "\n")
    else:
        output.write("enabled={} installed={} available={} result={} loaded={}\n".format(
            value["scheduler_enabled"], value["installed_version"],
            value["available_version"], value["last_result"], value["loaded_session"]))
        output.write("management-command=" + rendered + "\n")
    return 0


def _parser():
    parser = argparse.ArgumentParser(prog="team-update")
    sub = parser.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install")
    install.add_argument("--state-dir", default=None)
    install.add_argument("--codex", required=True)
    install.add_argument("--git", required=True)
    install.add_argument("--json", action="store_true")
    for name in ("status", "check", "pause", "resume", "uninstall-updater"):
        command = sub.add_parser(name)
        command.add_argument("--state-dir", default=None)
        command.add_argument("--json", action="store_true")
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.state_dir is None:
            args.state_dir = str(default_state_dir())
        if args.command == "install":
            return _install(args, sys.stdout)
        root = Path(args.state_dir).expanduser().absolute()
        config = _read_config(root)
        store, engine, scheduler = _components(root, config)
        logger = _logger(root)
        code = run_lifecycle(args.command, store, engine, scheduler,
                             output=sys.stdout, json_output=args.json)
        state = store.read_state()
        installed = state.get("installed") if isinstance(state.get("installed"), dict) else {}
        logger.info("command=%s result=%s version=%s sha=%s", args.command,
                    state.get("last_result", "unknown"), installed.get("version", "unknown"),
                    installed.get("sha", "unknown"))
        return code
    except (OSError, ValueError, RuntimeError, BlockingIOError) as error:
        code = str(error)
        allowed = {"unsupported-platform", "unsupported-python", "invalid-state-dir",
                   "missing-codex", "missing-git", "missing-python", "invalid-updater-config",
                   "initial-install-failed", "scheduler-readback-failed", "scheduler-collision",
                   "scheduler-command-failed", "repair-required", "updater-busy",
                   "initial-install-required", "installed-plugin-unavailable",
                   "trusted-runtime-unavailable", "app-data-unavailable"}
        print("error=" + (code if code in allowed else "operation-failed"), file=sys.stderr)
        return 2
