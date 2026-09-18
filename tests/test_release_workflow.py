"""Semantic checks on privilege and data flow of the promotion workflow."""
from pathlib import Path
import re
import unittest

import yaml  # CI test dependency only; never a plugin runtime dependency.

ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / ".github/workflows/promote.yml"
        self.assertTrue(path.exists(), "approval-gated workflow not implemented")
        # BaseLoader deliberately avoids YAML 1.1 treating 'on' as a boolean.
        self.workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)

    def test_dispatch_only_default_branch_serialization(self):
        w = self.workflow
        self.assertEqual(set(w["on"]), {"workflow_dispatch"})
        self.assertEqual(w["on"]["workflow_dispatch"]["inputs"], {
            "candidate_sha": {"required": "true", "type": "string"}})
        self.assertEqual(w["concurrency"], {"group": "team-plugin-stable-promotion", "cancel-in-progress": "false"})
        self.assertEqual(w["run-name"], "Promote ${{ inputs.candidate_sha }}")
        self.assertEqual(w["permissions"], {"contents": "read", "actions": "read"})
        for job in w["jobs"].values():
            self.assertIn("github.ref == 'refs/heads/main'", job["if"])
            self.assertIn("github.run_attempt == 1", job["if"])

    def test_readonly_preflight_before_environment_and_writer(self):
        jobs = self.workflow["jobs"]
        self.assertEqual(set(jobs), {"preflight", "publish"})
        self.assertNotIn("environment", jobs["preflight"])
        self.assertEqual(jobs["publish"]["needs"], "preflight")
        self.assertEqual(jobs["publish"]["environment"], "team-plugin-stable")
        before = str(jobs["preflight"])
        self.assertNotIn("secrets.", before)
        self.assertNotIn("create-github-app-token", before)
        publish = jobs["publish"]["steps"]
        mint = next(s for s in publish if "create-github-app-token@" in s.get("uses", ""))
        self.assertEqual(mint["with"]["permission-contents"], "write")
        self.assertEqual({k: v for k, v in mint["with"].items() if k.startswith("permission-")},
                         {"permission-contents": "write", "permission-actions": "read"})
        self.assertEqual(mint["with"]["repositories"], "${{ github.event.repository.name }}")
        self.assertNotIn("permission-administration", mint["with"])

    def test_pinned_trusted_checkout_and_no_candidate_shell_interpolation(self):
        for job in self.workflow["jobs"].values():
            for step in job["steps"]:
                if "uses" in step:
                    self.assertRegex(step["uses"], r"^[\w/-]+@[0-9a-f]{40}$")
                if step.get("uses", "").startswith("actions/checkout@"):
                    self.assertEqual(step["with"]["ref"], "${{ github.sha }}")
                    self.assertEqual(step["with"]["persist-credentials"], "false")
                if "run" in step:
                    self.assertNotIn("${{", step["run"])
                    self.assertNotRegex(step["run"], r"git\s+(checkout|push)|--force|pip install")
        publish = self.workflow["jobs"]["publish"]["steps"]
        call = next(s for s in publish if "promote_release.py publish" in s.get("run", ""))
        self.assertEqual(call["env"]["CANDIDATE_SHA"], "${{ inputs.candidate_sha }}")
        self.assertEqual(call["env"]["EXPECTED_STABLE"], "${{ needs.preflight.outputs.expected_stable }}")
        self.assertIn('"$CANDIDATE_SHA"', call["run"])

    def test_test_parser_install_keeps_ntfs_gate(self):
        for name in ("verify", "release"):
            w = yaml.load((ROOT / f".github/workflows/{name}.yml").read_text(), Loader=yaml.BaseLoader)
            steps = next(iter(w["jobs"].values()))["steps"]
            install = [i for i, s in enumerate(steps) if "pip install PyYAML==" in s.get("run", "")]
            self.assertEqual(len(install), 1)
            self.assertLess(install[0], next(i for i, s in enumerate(steps) if "scripts/" in s.get("run", "")))
            if name == "verify":
                required = {
                    "test_project_update.ProjectUpdateTests.test_windows_junction_alias_into_project_is_refused_without_writes",
                    "test_personal_store.StoreTests.test_windows_lock_link_is_rejected_before_target_write",
                    "test_personal_store.StoreTests.test_windows_held_lock_cannot_be_deleted_or_replaced",
                }
                gates = [s for s in steps if s.get("name", "").startswith("Mandatory live NTFS")]
                self.assertEqual(len(gates), 3)
                self.assertTrue(all(step["if"] == "runner.os == 'Windows'" for step in gates))
                commands = "\n".join(step["run"] for step in gates)
                for test_id in required:
                    self.assertIn("--required-test", commands)
                    self.assertIn(test_id, commands)
                additional = {
                    "test_personal_client.CodexClientTests.test_cache_link_escape_is_rejected_on_install_and_verify",
                    "test_personal_integration_fixes.PersistenceTests.test_native_shell_management_command_preserves_spaces_and_metacharacters",
                    "test_personal_cli.CliLifecycleTests.test_native_installer_forwards_spaced_arguments_unchanged",
                    "test_personal_integration_fixes.PersistenceTests.test_config_state_journal_write_without_unix_fchmod",
                }
                safety = [s for s in steps if s.get("name", "").startswith("Mandatory Windows updater")]
                self.assertEqual(len(safety), len(additional))
                self.assertTrue(all(s["if"] == "runner.os == 'Windows'" for s in safety))
                self.assertEqual({s["run"].split("--required-test")[1].strip() for s in safety}, additional)
