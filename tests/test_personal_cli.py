from contextlib import contextmanager
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import os
import subprocess
from contextlib import redirect_stderr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from team_updater import cli


class MemoryStore:
    def __init__(self, state): self.state = dict(state); self.locked = False
    @contextmanager
    def lock(self):
        self.locked = True
        try: yield
        finally: self.locked = False
    def read_state(self): return dict(self.state)
    def write_state(self, value): self.state = dict(value)


class Engine:
    def __init__(self, store): self.store = store; self.reconciles = 0
    def reconcile_completed(self): self.reconciles += 1; return self.store.read_state()
    def reconcile_completed_locked(self):
        self.reconciles += 1
        if not self.store.locked: raise AssertionError("reconcile outside lock")
        return self.store.read_state()
    def status(self): return self.store.read_state()
    def check(self): return self.store.read_state()


class Schedule:
    def __init__(self, active=False): self.active = active; self.calls = []
    def status(self): return self.active
    def enable(self): self.calls.append("enable"); self.active = True
    def disable(self): self.calls.append("disable"); self.active = False


class CliLifecycleTests(unittest.TestCase):
    def invoke(self, command, state, *, active=False):
        store = MemoryStore(state)
        engine = Engine(store)
        scheduler = Schedule(active)
        output = io.StringIO()
        code = cli.run_lifecycle(command, store, engine, scheduler, output=output)
        return code, store.state, engine, scheduler, output.getvalue()

    def test_pause_reconciles_then_disables_and_records_readback(self):
        code, state, engine, scheduler, _ = self.invoke("pause", {"enabled": True}, active=True)
        self.assertEqual(code, 0)
        self.assertEqual(engine.reconciles, 1)
        self.assertEqual(scheduler.calls, ["disable"])
        self.assertFalse(state["enabled"])

    def test_lifecycle_holds_store_lock_through_scheduler_and_state_write(self):
        store = MemoryStore({"enabled": True})

        class LockCheckingSchedule(Schedule):
            def disable(self):
                self.assert_locked = store.locked
                super().disable()

        scheduler = LockCheckingSchedule(True)
        engine = Engine(store)
        cli.run_lifecycle("pause", store, engine, scheduler, output=io.StringIO())
        self.assertTrue(scheduler.assert_locked)
        self.assertFalse(store.locked)

    def test_resume_does_not_claim_enabled_when_scheduler_readback_fails(self):
        class BrokenSchedule(Schedule):
            def enable(self): self.calls.append("enable")
        store = MemoryStore({"enabled": False, "installed": {"version": "2.2.0"}})
        engine = Engine(store)
        scheduler = BrokenSchedule()
        with self.assertRaisesRegex(RuntimeError, "scheduler-readback-failed"):
            cli.run_lifecycle("resume", store, engine, scheduler, output=io.StringIO())
        self.assertFalse(store.state["enabled"])
        self.assertEqual(store.state["last_result"], "repair-required")

    def test_resume_rolls_back_only_a_proven_owned_active_scheduler(self):
        class UncertainAfterCreate(Schedule):
            def enable(self):
                self.calls.append("enable")
                self.active = True
                raise RuntimeError("scheduler-readback-failed")

        store = MemoryStore({"enabled": False, "installed": {"version": "2.2.0"}})
        engine = Engine(store)
        scheduler = UncertainAfterCreate()
        with self.assertRaisesRegex(RuntimeError, "scheduler-readback-failed"):
            cli.run_lifecycle("resume", store, engine, scheduler, output=io.StringIO())
        self.assertEqual(scheduler.calls, ["enable", "disable"])
        self.assertFalse(scheduler.active)
        self.assertEqual(store.state["last_result"], "repair-required")

    def test_uninstall_updater_keeps_installed_metadata(self):
        installed = {"version": "2.2.0", "sha": "b" * 40, "cache": {"tree": {}}}
        _, state, _, scheduler, _ = self.invoke(
            "uninstall-updater", {"enabled": True, "installed": installed}, active=True)
        self.assertEqual(scheduler.calls, ["disable"])
        self.assertEqual(state["installed"], installed)
        self.assertFalse(state["enabled"])

    def test_status_json_distinguishes_installed_from_loaded(self):
        _, _, _, _, output = self.invoke(
            "status", {"enabled": True, "installed": {"version": "2.2.0"}}, active=True)
        value = json.loads(output)
        self.assertEqual(value["installed_version"], "2.2.0")
        self.assertEqual(value["loaded_session"], "unknown")
        self.assertTrue(value["scheduler_enabled"])

    def test_linux_install_is_rejected_before_creating_state_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "new-state"
            with patch.object(cli.sys, "platform", "linux"):
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(cli.main(["install", "--state-dir", str(state),
                                               "--codex", "/bin/true", "--git", "/bin/true"]), 2)
            self.assertFalse(state.exists())

    def test_install_probes_client_before_creating_state_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            state = parent / "new-state"
            codex = parent / "codex"
            codex.write_text("#!/bin/sh\necho unsupported\n")
            codex.chmod(0o700)
            with patch.object(cli.sys, "platform", "darwin"):
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(cli.main(["install", "--state-dir", str(state),
                                               "--codex", str(codex),
                                               "--git", "/usr/bin/true"]), 2)
            self.assertFalse(state.exists())

    def test_macos_installer_forwards_spaced_arguments_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "path with spaces"
            scripts.mkdir()
            wrapper = scripts / "install-updater.command"
            wrapper.write_bytes((ROOT / "scripts/install-updater.command").read_bytes())
            wrapper.chmod(0o700)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_python = fake_bin / "python3"
            fake_python.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
            fake_python.chmod(0o700)
            environment = dict(os.environ)
            environment["PATH"] = str(fake_bin) + os.pathsep + environment.get("PATH", "")
            result = subprocess.run([str(wrapper), "--codex", "/Applications/Path With Space/codex",
                                     "--git", "/usr/bin/git"], capture_output=True, text=True,
                                    check=True, env=environment)
            self.assertEqual(result.stdout.splitlines(), [
                str(scripts / "team-update.py"), "install", "--codex",
                "/Applications/Path With Space/codex", "--git", "/usr/bin/git"
            ])


if __name__ == "__main__":
    unittest.main()
