from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from team_updater.client import CodexClient
from team_updater import client as client_module
from team_updater.release import Candidate


SHA = "a" * 40
CANDIDATE = Candidate("2.2.0", SHA, {})
SELECTOR = "team-engineering-skills@team-engineering-skills-marketplace"


class Runner:
    def __init__(self, codex_home, source):
        self.codex_home = codex_home
        self.source = source
        self.calls = []
        self.installed = False
        self.enabled = True
        self.version = "2.2.0"
        self.marketplace_exists = True

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        args = command[1:]
        if args in (["--version"], ["plugin", "--help"],
                    ["plugin", "marketplace", "--help"]):
            return subprocess.CompletedProcess(command, 0, b"codex-cli 0.155\n", b"")
        if args == ["plugin", "marketplace", "list", "--json"]:
            marketplaces = [{"name": "team-engineering-skills-marketplace",
                    "root": str(self.source), "marketplaceSource": {
                    "sourceType": "local", "source": str(self.source)}}]
            body = {"marketplaces": marketplaces if self.marketplace_exists else []}
        elif args == ["plugin", "list", "--json"]:
            installed = []
            if self.installed:
                installed = [{"pluginId": SELECTOR, "name": "team-engineering-skills",
                    "marketplaceName": "team-engineering-skills-marketplace",
                    "version": self.version, "installed": True, "enabled": self.enabled,
                    "source": {"source": "local", "path": str(self.source / "plugins/team-engineering-skills")},
                    "marketplaceSource": {"sourceType": "local", "source": str(self.source)},
                    "installPolicy": "AVAILABLE", "authPolicy": "ON_USE"}]
            body = {"installed": installed, "available": []}
        elif args[:4] == ["plugin", "marketplace", "add", "--json"]:
            body = {"marketplaceName": "team-engineering-skills-marketplace",
                    "installedRoot": str(self.source), "alreadyAdded": False}
        elif args == ["plugin", "add", "--json", SELECTOR]:
            self.installed = True
            cache = self.codex_home / "plugins/cache/team-engineering-skills-marketplace/team-engineering-skills/2.2.0"
            cache.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copytree(self.source / "plugins/team-engineering-skills", cache)
            body = {"pluginId": SELECTOR, "name": "team-engineering-skills",
                    "marketplaceName": "team-engineering-skills-marketplace", "version": "2.2.0",
                    "installedPath": str(cache), "authPolicy": "ON_USE"}
        else:
            raise AssertionError(args)
        return subprocess.CompletedProcess(command, 0, json.dumps(body).encode(), b"")


class CodexClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.exe = self.base / "codex"
        self.exe.write_text("fixture")
        self.source = self.base / "owned-source"
        plugin = self.source / "plugins/team-engineering-skills"
        (plugin / ".codex-plugin").mkdir(parents=True)
        (plugin / ".codex-plugin/plugin.json").write_text(json.dumps({
            "name": "team-engineering-skills", "version": "2.2.0"}))
        (plugin / "payload.txt").write_text("verified bytes")
        self.home = self.base / "codex-home"
        self.home.mkdir()
        self.runner = Runner(self.home, self.source)
        self.client = CodexClient(self.exe, run=self.runner, codex_home=self.home)

    def test_probe_uses_absolute_executable_bounded_subprocess_and_frozen_profile(self):
        result = self.client.probe()
        self.assertEqual(result["version"], "codex-cli 0.155")
        for command, options in self.runner.calls:
            self.assertEqual(command[0], str(self.exe))
            self.assertFalse(options["shell"])
            self.assertTrue(Path(options["cwd"]).is_dir())
            self.assertNotEqual(options["cwd"], self.home)
            self.assertEqual(options["env"]["CODEX_HOME"], str(self.home))
            self.assertLessEqual(options["timeout"], 30)

    def test_inventory_rejects_foreign_source_before_mutation(self):
        foreign = self.base / "foreign"
        foreign.mkdir()
        self.runner.source = foreign
        with self.assertRaisesRegex(ValueError, "source-collision"):
            self.client.register(self.source)
        self.assertFalse(any(call[0][1:3] == ["plugin", "add"] for call in self.runner.calls))

    def test_malformed_or_unsupported_json_is_rejected(self):
        def malformed(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, b'{"installed":"secret"}', b"")
        client = CodexClient(self.exe, run=malformed, codex_home=self.home)
        with self.assertRaisesRegex(ValueError, "unsupported-client-response") as caught:
            client.inventory()
        self.assertNotIn("secret", str(caught.exception))

    def test_install_evidence_is_path_bounded_and_verify_checks_cache_bytes(self):
        self.runner.marketplace_exists = False
        self.client.register(self.source)
        evidence = self.client.install(self.source, CANDIDATE)
        self.assertEqual(evidence["version"], "2.2.0")
        mutation_calls = [(command, options) for command, options in self.runner.calls
                          if command[1:4] in (["plugin", "marketplace", "add"],
                                              ["plugin", "add", "--json"])]
        self.assertEqual(len(mutation_calls), 2)
        self.assertTrue(all(options["cwd"] == self.source
                            for _command, options in mutation_calls))
        self.assertTrue(self.client.verify(self.source, CANDIDATE))
        cache_file = Path(evidence["installed_path"]) / "payload.txt"
        cache_file.write_text("tampered")
        self.assertFalse(self.client.verify(self.source, CANDIDATE))

    def test_disabled_plugin_is_not_silently_reenabled(self):
        self.runner.installed = True
        self.runner.enabled = False
        with self.assertRaisesRegex(ValueError, "plugin-disabled"):
            self.client.register(self.source)

    def test_cache_link_escape_is_rejected_on_install_and_verify(self):
        for intermediate in (False, True):
            with self.subTest(intermediate=intermediate):
                home = self.base / ("home-" + str(intermediate))
                runner = Runner(home, self.source)
                outside = self.base / ("outside-" + str(intermediate))
                def linked(command, **kwargs):
                    result = runner(command, **kwargs)
                    if command[1:] == ["plugin", "add", "--json", SELECTOR]:
                        cache = home / "plugins/cache/team-engineering-skills-marketplace/team-engineering-skills/2.2.0"
                        target = cache.parent if intermediate else cache
                        target.rename(outside)
                        if os.name == "nt":
                            subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(outside)],
                                           check=True, capture_output=True)
                        else:
                            target.symlink_to(outside, target_is_directory=True)
                    return result
                client = CodexClient(self.exe, run=linked, codex_home=home)
                client.register(self.source)
                with self.assertRaisesRegex(ValueError, "invalid-plugin-cache"):
                    client.install(self.source, CANDIDATE)
                self.assertFalse(client.verify(self.source, CANDIDATE))

    def test_disabled_plugin_is_refused_by_preactivation_validation(self):
        self.runner.installed = True
        self.runner.enabled = False
        with self.assertRaisesRegex(ValueError, "plugin-disabled"):
            self.client.validate_source(self.source)

    def test_timeout_with_successful_readback_is_not_blindly_retried(self):
        original = self.runner
        calls = 0
        def uncertain(command, **kwargs):
            nonlocal calls
            if command[1:] == ["plugin", "add", "--json", SELECTOR]:
                calls += 1
                original(command, **kwargs)
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            return original(command, **kwargs)
        client = CodexClient(self.exe, run=uncertain, codex_home=self.home)
        client.register(self.source)
        evidence = client.install(self.source, CANDIDATE)
        self.assertEqual(evidence["version"], "2.2.0")
        self.assertEqual(calls, 1)

    def test_nonzero_add_with_successful_readback_is_not_blindly_retried(self):
        original = self.runner
        calls = 0
        def uncertain(command, **kwargs):
            nonlocal calls
            if command[1:] == ["plugin", "add", "--json", SELECTOR]:
                calls += 1
                original(command, **kwargs)
                raise subprocess.CalledProcessError(1, command, stderr=b"sensitive")
            return original(command, **kwargs)
        client = CodexClient(self.exe, run=uncertain, codex_home=self.home)
        client.register(self.source)
        self.assertEqual(Path(client.install(self.source, CANDIDATE)["installed_path"]).name, "2.2.0")
        self.assertEqual(calls, 1)

    def test_uncertain_add_without_matching_readback_is_not_retried(self):
        for error in (subprocess.TimeoutExpired(["codex"], 30),
                      subprocess.CalledProcessError(1, ["codex"], stderr=b"sensitive")):
            with self.subTest(error=type(error).__name__):
                original = self.runner
                calls = 0
                def uncertain(command, **kwargs):
                    nonlocal calls
                    if command[1:] == ["plugin", "add", "--json", SELECTOR]:
                        calls += 1
                        raise error
                    return original(command, **kwargs)
                client = CodexClient(self.exe, run=uncertain, codex_home=self.home)
                client.register(self.source)
                with self.assertRaisesRegex(RuntimeError, "client-(status-unknown|command-failed)"):
                    client.install(self.source, CANDIDATE)
                self.assertEqual(calls, 1)

    def test_uncertain_add_with_mismatched_readback_is_not_retried(self):
        original = self.runner
        calls = 0
        def uncertain(command, **kwargs):
            nonlocal calls
            if command[1:] == ["plugin", "add", "--json", SELECTOR]:
                calls += 1
                original.installed = True
                original.version = "2.1.0"
                raise subprocess.TimeoutExpired(command, 30)
            return original(command, **kwargs)
        client = CodexClient(self.exe, run=uncertain, codex_home=self.home)
        client.register(self.source)
        with self.assertRaisesRegex(RuntimeError, "client-status-unknown"):
            client.install(self.source, CANDIDATE)
        self.assertEqual(calls, 1)

    def test_default_transport_terminates_when_either_output_stream_exceeds_cap(self):
        for stream_name in ("stdout", "stderr"):
            with self.subTest(stream=stream_name):
                script = self.base / ("noisy-codex-" + stream_name)
                marker = self.base / ("should-not-exist-" + stream_name)
                setup = ("stream=sys.stdout\n" if stream_name == "stdout" else
                         "sys.stdout.write('codex-cli fixture\\n'); sys.stdout.flush(); stream=sys.stderr\n")
                script.write_text("#!/usr/bin/env python3\nimport pathlib,sys\n" + setup
                                  + "stream.write('x' * 2097152); stream.flush()\n"
                                  + f"pathlib.Path({str(marker)!r}).write_text('unbounded')\n")
                script.chmod(0o700)
                def native_python(command, **kwargs):
                    return client_module._bounded_run([sys.executable, str(script), *command[1:]], **kwargs)
                client = CodexClient(Path(sys.executable).resolve(), run=native_python, codex_home=self.home)
                with self.assertRaisesRegex(RuntimeError, "client-output-limit"):
                    client.probe()
                self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
