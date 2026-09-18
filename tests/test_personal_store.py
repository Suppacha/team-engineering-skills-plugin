from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from team_updater.release import Candidate
from team_updater.cli import _absolute_executable
from team_updater.store import Store, validate_snapshot


SHA = "a" * 40


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "team-updater"
        self.store = Store(self.root)

    def test_two_holders_cannot_write_and_release_allows_next_holder(self):
        with self.store.lock():
            with self.assertRaises(BlockingIOError):
                with Store(self.root).lock():
                    self.fail("second writer entered")
        with Store(self.root).lock():
            pass

    def test_state_and_journal_are_atomic_bounded_json(self):
        self.store.write_state({"installed": {"version": "2.2.0", "sha": SHA}})
        self.assertEqual(self.store.read_state()["installed"]["sha"], SHA)
        if os.name != "nt":
            self.assertEqual(self.store.state.stat().st_mode & 0o077, 0)
        else:
            # Windows mode bits are not ACL evidence; prove usable atomic IO.
            self.store.write_state({"installed": {"version": "2.2.0", "sha": SHA}})
            self.assertEqual(self.store.read_state()["installed"]["sha"], SHA)
        self.assertEqual(list(self.root.glob(".state.json.*")), [])
        self.store.write_journal({"operation": "activate", "sha": SHA})
        self.assertEqual(self.store.read_journal()["operation"], "activate")
        self.store.write_journal(None)
        self.assertIsNone(self.store.read_journal())
        with self.assertRaises(ValueError):
            self.store.write_state({"too_large": "x" * (70 * 1024)})

    def test_malformed_journal_error_is_sanitized(self):
        self.store.journal.write_text('{"secret":')
        with self.assertRaisesRegex(ValueError, "^invalid-journal$") as caught:
            self.store.read_journal()
        self.assertNotIn("secret", str(caught.exception))

    def test_state_and_journal_reads_reject_links_created_after_startup(self):
        outside = self.base / "outside.json"
        outside.write_text('{"private":"fixture"}')
        for path, read in ((self.store.state, self.store.read_state),
                           (self.store.journal, self.store.read_journal)):
            with self.subTest(path=path.name):
                path.symlink_to(outside)
                with self.assertRaises(ValueError):
                    read()
                path.unlink()

    def test_unsafe_roots_and_symlink_ancestors_are_rejected(self):
        for unsafe in (Path.home(), ROOT, Path("/"), self.base):
            with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                Store(unsafe)
        real = self.base / "real"
        real.mkdir()
        alias = self.base / "alias"
        alias.symlink_to(real, target_is_directory=True)
        with self.assertRaises(ValueError):
            Store(alias / "store")

    def test_preexisting_empty_directory_is_not_claimed(self):
        unowned = self.base / "unowned"
        unowned.mkdir()
        with self.assertRaisesRegex(ValueError, "unowned-store-root"):
            Store(unowned)
        self.assertEqual(list(unowned.iterdir()), [])

    @unittest.skipUnless(os.name == "nt", "requires live Windows NTFS link semantics")
    def test_windows_lock_link_is_rejected_before_target_write(self):
        outside = self.base / "outside.lock"
        outside.write_bytes(b"private-fixture")
        self.store.lock_file.symlink_to(outside)
        with self.assertRaises(ValueError):
            with self.store.lock():
                self.fail("linked lock entered")
        self.assertEqual(outside.read_bytes(), b"private-fixture")

    @unittest.skipUnless(os.name == "nt", "requires live Windows lock sharing semantics")
    def test_windows_held_lock_cannot_be_deleted_or_replaced(self):
        replacement = self.base / "replacement.lock"
        replacement.write_bytes(b"replacement")
        with self.store.lock():
            with self.assertRaises(OSError):
                self.store.lock_file.unlink()
            with self.assertRaises(OSError):
                os.replace(replacement, self.store.lock_file)
            self.assertTrue(self.store.lock_file.is_file())
        self.assertEqual(replacement.read_bytes(), b"replacement")

    def test_activation_rejects_outside_staging(self):
        outside = self.base / "outside"
        outside.mkdir()
        with self.assertRaises(ValueError):
            self.store.activate(outside)

    def test_activation_preserves_current_when_new_rename_fails(self):
        self.store.current.mkdir()
        (self.store.current / "marker").write_text("old")
        staged = self.store.staging / SHA
        staged.mkdir(parents=True)
        (staged / "marker").write_text("new")
        real_replace = os.replace

        def fail_new(source, destination):
            if Path(source) == staged and Path(destination) == self.store.current:
                raise OSError("locked")
            return real_replace(source, destination)

        with patch("team_updater.store.os.replace", side_effect=fail_new):
            with self.assertRaises(OSError):
                self.store.activate(staged)
        self.assertEqual((self.store.current / "marker").read_text(), "old")


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.snapshot = Path(self.temporary.name).resolve() / "snapshot"
        for name in ("plugins", "config", ".agents", ".claude-plugin"):
            source = ROOT / name
            if name == "plugins":
                shutil.copytree(source / "team-engineering-skills", self.snapshot / name / "team-engineering-skills")
            elif name == "config":
                (self.snapshot / name).mkdir(parents=True)
                shutil.copy2(source / "skills-lock.json", self.snapshot / name / "skills-lock.json")
            else:
                shutil.copytree(source, self.snapshot / name)
        shutil.copy2(ROOT / "LICENSE", self.snapshot / "LICENSE")
        self.candidate = Candidate("2.2.0", SHA, {})

    def test_valid_snapshot_returns_registry(self):
        registry = validate_snapshot(self.snapshot, self.candidate)
        self.assertEqual(registry["version"], "2.2.0")

    def test_tampered_snapshot_is_rejected(self):
        target = self.snapshot / "plugins/team-engineering-skills/standards/security.md"
        target.write_text("tampered")
        with self.assertRaises(ValueError):
            validate_snapshot(self.snapshot, self.candidate)

    def test_candidate_version_and_marketplace_identity_are_bound(self):
        with self.assertRaisesRegex(ValueError, "package-version-mismatch"):
            validate_snapshot(self.snapshot, Candidate("9.9.9", SHA, {}))
        catalog = self.snapshot / ".agents/plugins/marketplace.json"
        data = json.loads(catalog.read_text())
        data["name"] = "attacker-marketplace"
        catalog.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            validate_snapshot(self.snapshot, self.candidate)

    def test_apache_license_must_exist_inside_skill(self):
        license_file = self.snapshot / "plugins/team-engineering-skills/skills/mcp-builder/LICENSE.txt"
        license_file.unlink()
        with self.assertRaises(ValueError):
            validate_snapshot(self.snapshot, self.candidate)


class GitPathTests(unittest.TestCase):
    def test_rejects_symlink_reparse_reserved_and_case_colliding_paths(self):
        from team_updater.store import _validate_tree

        ordinary = ("100644", "blob", "b" * 40, 1, "LICENSE")
        bad_sets = (
            [("120000", "blob", "b" * 40, 1, "link")],
            [("160000", "commit", "b" * 40, None, "submodule")],
            [("100644", "blob", "b" * 40, 1, "plugins/CON/readme")],
            [ordinary, ("100644", "blob", "c" * 40, 1, "license")],
            [("100644", "blob", "b" * 40, 1, "plugins/x/../escape")],
        )
        for entries in bad_sets:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                _validate_tree(entries)

    def test_total_limit_counts_unselected_blobs(self):
        from team_updater.store import MAX_FILE, MAX_TOTAL, _validate_tree

        entries = []
        count = MAX_TOTAL // MAX_FILE + 1
        for index in range(count):
            entries.append(("100644", "blob", f"{index + 1:040x}", MAX_FILE,
                            f"unselected-{index}.bin"))
        with self.assertRaisesRegex(ValueError, "oversized-git-tree"):
            _validate_tree(entries)


class GitStagingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.source = self.base / "source"
        self.source.mkdir()
        for name in ("plugins", "config", ".agents", ".claude-plugin"):
            source = ROOT / name
            if name == "plugins":
                shutil.copytree(source / "team-engineering-skills", self.source / name / "team-engineering-skills",
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            elif name == "config":
                (self.source / name).mkdir()
                shutil.copy2(source / "skills-lock.json", self.source / name / "skills-lock.json")
            else:
                shutil.copytree(source, self.source / name)
        shutil.copy2(ROOT / "LICENSE", self.source / "LICENSE")
        subprocess.run(["git", "init", "-q", str(self.source)], check=True)
        subprocess.run(["git", "-C", str(self.source), "add", "."], check=True)
        subprocess.run([
            "git", "-C", str(self.source), "-c", "user.name=Fixture",
            "-c", "user.email=fixture@example.test", "commit", "-qm", "fixture",
        ], check=True)
        self.sha = subprocess.run(
            ["git", "-C", str(self.source), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()

    def test_stage_exports_verified_raw_blobs_from_fixed_remote_command(self):
        calls = []
        actual_git = Path(shutil.which("git")).resolve(strict=True)
        discovered_git = self.base / "git-from-package-manager"
        discovered_git.symlink_to(actual_git)

        def local_transport(command, **kwargs):
            calls.append((list(command), dict(kwargs.get("env", {}))))
            command = list(command)
            if "https://github.com/Suppacha/team-engineering-skills-plugin.git" in command:
                command[command.index("https://github.com/Suppacha/team-engineering-skills-plugin.git")] = str(self.source)
            while "protocol.file.allow=never" in command:
                index = command.index("protocol.file.allow=never")
                del command[index - 1:index + 1]
            return subprocess.run(command, **kwargs)

        with patch.dict(os.environ, {"GIT_CONFIG_COUNT": "99", "GIT_CONFIG_KEY_0": "filter.bad.clean"}), \
                patch.object(shutil, "which", return_value=str(discovered_git)):
            store = Store(self.base / "updater", run=local_transport)
            # Match the public installer's frozen executable binding, including
            # package-manager PATH entries that are symlinks on macOS.
            staged = store.stage(Candidate("2.2.0", self.sha, {}), _absolute_executable("git", "git"))
        self.assertEqual((staged / "plugins/team-engineering-skills/VERSION").read_text(), "2.2.0\n")
        remote_calls = [call for call, _env in calls if "remote" in call]
        self.assertTrue(any("https://github.com/Suppacha/team-engineering-skills-plugin.git" in call
                            for call in remote_calls))
        for _call, environment in calls:
            self.assertEqual(_call[0], str(actual_git))
            self.assertNotIn("GIT_CONFIG_COUNT", environment)
            self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)


if __name__ == "__main__":
    unittest.main()
