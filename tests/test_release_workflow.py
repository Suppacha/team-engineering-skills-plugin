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
                junction = next(s for s in steps if s.get("name") == "Mandatory live NTFS junction regression")
                self.assertEqual(junction["if"], "runner.os == 'Windows'")
                self.assertIn("--required-test", junction["run"])
