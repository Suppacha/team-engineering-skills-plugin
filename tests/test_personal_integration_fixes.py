"""Regressions at the updater's real persistence/lifecycle boundaries."""
import json
import io
import os
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from contextlib import redirect_stderr
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from team_updater import cli
from team_updater.store import Store
from team_updater.engine import Updater
from test_personal_cli import Schedule


class PersistenceTests(unittest.TestCase):
    def test_config_state_journal_write_without_unix_fchmod(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "store")
            original = getattr(os, "fchmod", None)
            try:
                if original is not None:
                    del os.fchmod
                with store.lock():
                    cli._write_config(store.root, {"fixture": True})
                    store.write_state({"enabled": False})
                    store.write_journal({"phase": "prepared"})
                self.assertEqual(json.loads((store.root / cli.CONFIG).read_bytes()), {"fixture": True})
                self.assertEqual(store.read_state(), {"enabled": False})
                self.assertEqual(store.read_journal(), {"phase": "prepared"})
            finally:
                if original is not None:
                    os.fchmod = original

    def test_stop_commands_preserve_incomplete_journal_but_stop_owned_scheduler(self):
        for command in ("pause", "uninstall-updater"):
            for phase in ("prepared", "swapped", "installing", "verified", "unknown"):
                with self.subTest(command=command, phase=phase), tempfile.TemporaryDirectory() as directory:
                    store = Store(Path(directory) / "store")
                    store.write_state({"enabled": True, "installed": {"version": "2.2.0"}})
                    journal = {"phase": phase}
                    store.write_journal(journal)
                    engine = Updater(store, None, None, Path(sys.executable))
                    scheduler = Schedule(True)
                    cli.run_lifecycle(command, store, engine, scheduler, output=io.StringIO())
                    self.assertFalse(scheduler.active)
                    self.assertFalse(store.read_state()["enabled"])
                    self.assertTrue(store.read_state()["repair_required"])
                    self.assertEqual(store.read_journal(), journal)

    def test_components_use_frozen_profile_not_private_updater_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            profile = root / "desktop-profile"
            config = {"codex": str(Path(sys.executable).resolve()), "git": sys.executable,
                      "python": sys.executable, "entry": str(ROOT / "scripts/team-update.py"),
                      "codex_home": str(profile)}
            with patch.object(cli, "Scheduler"):
                store, engine, _ = cli._components(root / "store", config)
            self.assertEqual(engine.client.codex_home, profile)
            self.assertFalse((store.root / "codex-profile").exists())

    def test_effective_profile_defaults_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch.dict(os.environ, {"CODEX_HOME": str(root / "effective")}), \
                    patch.object(Path, "home", return_value=root):
                self.assertEqual(cli._profile(None), root / "effective")
                self.assertEqual(cli._profile(str(root / "custom")), root / "custom")
            with patch.dict(os.environ, {}, clear=True), patch.object(Path, "home", return_value=root):
                self.assertEqual(cli._profile(None), root / ".codex")

    def test_busy_install_does_not_touch_frozen_runtime_or_config(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "store")
            exe = Path(sys.executable).resolve()
            args = SimpleNamespace(codex_home=str(Path(directory).resolve() / "fixture-profile"), json=True)
            with store.lock(), patch.object(cli, "_validate_install", return_value=(store.root, exe, exe, exe)), \
                    patch.object(cli, "_freeze_runtime") as freeze, patch.object(cli, "_write_config") as config:
                with self.assertRaisesRegex(BlockingIOError, "updater-busy"):
                    cli._install(args, io.StringIO())
                freeze.assert_not_called()
                config.assert_not_called()

    def test_existing_runtime_is_immutable_on_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "store")
            with store.lock():
                runtime = cli._freeze_runtime(store.root)
                before = (runtime / "scripts/team-update.py").read_bytes()
                with patch.object(cli, "SOURCE_ROOT", Path(directory) / "missing"):
                    with self.assertRaisesRegex(RuntimeError, "updater-runtime-migration-required"):
                        cli._freeze_runtime(store.root)
            self.assertEqual((runtime / "scripts/team-update.py").read_bytes(), before)

    def test_native_shell_management_command_preserves_spaces_and_metacharacters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "space ' dollar$ amp& semi; [bracket]"
            root.mkdir()
            script = root / "argument echo.py"
            script.write_text("import json,sys; print(json.dumps(sys.argv[1:]))", encoding="utf-8")
            binary_dir = root / "python link"
            original = Path(sys.executable).resolve()
            if os.name == "nt":
                subprocess.run(["cmd", "/c", "mklink", "/J", str(binary_dir), str(original.parent)],
                               check=True, capture_output=True)
            else:
                binary_dir.symlink_to(original.parent, target_is_directory=True)
            command = [str(binary_dir / original.name), str(script), "status", "--state-dir", str(root)]
            rendered = cli._management_command(command)
            shell = (["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", rendered]
                     if os.name == "nt" else ["/bin/sh", "-c", rendered])
            result = subprocess.run(shell, check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(result.stdout), command[2:])

    def test_failed_background_check_logs_sanitized_outcome_without_status_call(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "store")
            store.write_state({"enabled": True, "last_result": "up-to-date"})
            class Client:
                def validate_source(self, source): raise ValueError("secret/token sensitive response")
            engine = Updater(store, None, Client(), Path(sys.executable))
            with patch.object(cli, "_read_config", return_value={}), \
                    patch.object(cli, "_components", return_value=(store, engine, Schedule(True))), \
                    redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(["check", "--state-dir", str(store.root)]), 2)
            raw = (store.root / "logs/updater.log").read_text()
            self.assertIn("operation-failed", raw)
            self.assertNotIn("secret", raw)
            self.assertNotEqual(store.read_state()["last_result"], "up-to-date")

    def test_initial_runtime_and_config_rename_interruptions_are_recoverable(self):
        for target in ("runtime", cli.CONFIG):
            for after in (False, True):
                with self.subTest(target=target, after=after), tempfile.TemporaryDirectory() as directory:
                    store = Store(Path(directory) / "store")
                    original = os.replace
                    config = {"fixture": "unchanged"}
                    def interrupted(source, destination):
                        if Path(destination).name == target:
                            if after: original(source, destination)
                            raise OSError("fixture interruption")
                        return original(source, destination)
                    with store.lock():
                        with patch.object(cli.os, "replace", side_effect=interrupted), self.assertRaises(OSError):
                            cli._freeze_runtime(store.root)
                            cli._write_config(store.root, config)
                        runtime = cli._freeze_runtime(store.root)
                        cli._write_config(store.root, config)
                        self.assertEqual((runtime / "scripts/team-update.py").read_bytes(),
                                         (ROOT / "scripts/team-update.py").read_bytes())
                        self.assertEqual(json.loads((store.root / cli.CONFIG).read_bytes()), config)
                        self.assertFalse((store.root / ".runtime-old").exists())

    def test_invalid_initial_profile_does_not_poison_bootstrap_state(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            actual = base / "actual"
            actual.mkdir()
            alias = base / "alias"
            if os.name == "nt":
                subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(actual)],
                               check=True, capture_output=True)
            else:
                alias.symlink_to(actual, target_is_directory=True)
            root = base / "updater"
            exe = Path(sys.executable).resolve()
            args = SimpleNamespace(codex_home=str(alias), json=True)
            with patch.object(cli, "_validate_install", return_value=(root, exe, exe, exe)):
                with self.assertRaises(ValueError): cli._install(args, io.StringIO())
            self.assertFalse(root.exists())

    def test_missing_previously_bound_runtime_is_not_silently_recreated(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            store = Store(base / "store")
            exe = Path(sys.executable).resolve()
            profile = base / "profile"
            cli._write_config(store.root, {"codex": str(exe), "git": str(exe), "python": str(exe),
                              "entry": str(store.root / "runtime/scripts/team-update.py"), "codex_home": str(profile)})
            args = SimpleNamespace(codex_home=str(profile), json=True)
            with patch.object(cli, "_validate_install", return_value=(store.root, exe, exe, exe)), \
                    patch.object(cli, "_freeze_runtime", side_effect=AssertionError("runtime recreation reached")):
                with self.assertRaisesRegex(RuntimeError, "updater-runtime-migration-required"):
                    cli._install(args, io.StringIO())
            self.assertFalse(profile.exists())
