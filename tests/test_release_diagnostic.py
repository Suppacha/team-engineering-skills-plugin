"""Offline, publisher-shaped evidence for the single incident diagnostic."""
import importlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


class ReleaseDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.d = importlib.import_module("diagnose_release")
        self.calls = []
        self.record = dict(schema_version=1, version="2.2.0", repository=self.d.REPOSITORY,
                           candidate_sha=self.d.CANDIDATE, previous_stable_sha=None,
                           run_id=35296621274, approval={"sentinel": "SECRET_SENTINEL"})
        self.release = dict(id=123, tag_name="v2.2.0", target_commitish=self.d.CANDIDATE,
                            draft=True, prerelease=False,
                            body=json.dumps(dict(state="prepared", record=self.record)))
        self.assets = []

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        self.assertEqual(method, "GET")
        self.assertIsNone(body)
        if "/git/ref/" in path:
            return 200, {}, dict(ref="refs/tags/v2.2.0", object=dict(type="commit", sha=self.d.CANDIDATE))
        if "/assets?" in path:
            return 200, {}, self.assets
        return 200, {}, [self.release]

    def test_prepared_without_asset_uses_real_metadata_validator(self):
        result = self.d.diagnose(self.request)
        self.assertEqual(result["metadata"], "valid")
        self.assertEqual(result["asset_count"], 0)
        self.assertEqual(result["target_commitish"], "candidate")
        self.assertEqual(set(result), self.d.OUTPUT_KEYS)
        self.assertNotIn("SECRET_SENTINEL", json.dumps(result))

    def test_main_target_is_distinguished_and_validator_rejects(self):
        self.release["target_commitish"] = "main"
        result = self.d.diagnose(self.request)
        self.assertEqual(result["target_commitish"], "main")
        self.assertEqual(result["metadata"], "target-mismatch")
        self.assertEqual(result["asset_count"], 0)

    def test_invisible_known_draft_is_indeterminate_and_cli_fails(self):
        def filtered(method, path, body=None):
            if path == self.d.PREFIX + "/releases?per_page=100":
                return 200, {}, []
            return self.request(method, path, body)
        env = dict(GITHUB_REPOSITORY=self.d.REPOSITORY, GITHUB_REF="refs/heads/main",
                   GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_RUN_ATTEMPT="1",
                   GH_DIAGNOSTIC_TOKEN="SECRET_SENTINEL")
        with patch.dict("os.environ", env, clear=True), \
                patch.object(self.d, "github_request", return_value=filtered), \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            code = self.d.main([])
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "release-not-visible")
        self.assertEqual(code, 1)
        self.assertIsNone(result["asset_count"])
        self.assertEqual(result["metadata"], "not-checked")
        self.assertNotIn("SECRET_SENTINEL", output.getvalue())

    def test_untrusted_body_and_exception_are_redacted(self):
        self.release["body"] = "SECRET_SENTINEL"
        self.release["target_commitish"] = "SECRET_SENTINEL"
        result = self.d.diagnose(self.request)
        self.assertEqual(result["metadata"], "body-not-json")
        self.assertNotIn("SECRET_SENTINEL", json.dumps(result))
        def broken(*args):
            raise RuntimeError("SECRET_SENTINEL")
        result = self.d.diagnose(broken)
        self.assertEqual(result["status"], "read-failed")
        self.assertNotIn("SECRET_SENTINEL", json.dumps(result))

    def test_invalid_release_id_cannot_inject_path(self):
        self.release["id"] = "123/../../SECRET_SENTINEL"
        result = self.d.diagnose(self.request)
        self.assertEqual(result["metadata"], "invalid-id")
        self.assertFalse(any("assets" in path for _, path, _ in self.calls))
        self.assertNotIn("SECRET_SENTINEL", json.dumps(result))

    def test_transport_rejects_writes_other_targets_and_pagination_injection(self):
        request = self.d.fixed_request(self.request)
        for method, path, body in [
            ("POST", self.d.PREFIX + "/releases", {}),
            ("GET", "/repos/other/repo/releases?per_page=100", None),
            ("GET", self.d.PREFIX + "/git/ref/tags/other", None),
            ("GET", self.d.PREFIX + "/releases?per_page=100&evil=SECRET_SENTINEL", None),
        ]:
            with self.assertRaises(ValueError):
                request(method, path, body)
        self.assertEqual(self.calls, [])
        with self.assertRaises(ValueError):
            self.d.deny_write("POST", "anything")

    def test_cli_gate_and_arguments_refuse_before_transport(self):
        env = dict(GITHUB_REPOSITORY=self.d.REPOSITORY, GITHUB_REF="refs/heads/main",
                   GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_RUN_ATTEMPT="1")
        for change, args in [({"GITHUB_RUN_ATTEMPT": "2"}, []),
                             ({"GITHUB_REF": "refs/heads/other"}, []),
                             ({"GITHUB_REPOSITORY": "other/repo"}, []),
                             ({"GITHUB_EVENT_NAME": "push"}, []),
                             ({}, ["SECRET_SENTINEL"])]:
            with patch.dict("os.environ", env | change, clear=True), \
                    patch.object(self.d, "github_request") as network, \
                    patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(self.d.main(args), 1)
                network.assert_not_called()
                self.assertNotIn("SECRET_SENTINEL", output.getvalue())

    def test_workflow_is_fixed_read_only_and_approval_gated(self):
        import yaml
        path = Path(__file__).resolve().parents[1] / ".github/workflows/diagnose-release.yml"
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        job = workflow["jobs"]["diagnose"]
        self.assertEqual(job["environment"], "team-plugin-stable")
        self.assertEqual(job["timeout-minutes"], 5)
        self.assertIn("github.run_attempt == 1", job["if"])
        self.assertIn("github.ref == 'refs/heads/main'", job["if"])
        self.assertIn("github.repository == 'Suppacha/team-engineering-skills-plugin'", job["if"])
        steps = job["steps"]
        token = next(s for s in steps if "create-github-app-token@" in s.get("uses", ""))
        self.assertEqual(token["with"]["permission-contents"], "read")
        self.assertEqual(token["with"]["permission-actions"], "read")
        self.assertEqual(token["with"]["owner"], "Suppacha")
        self.assertEqual(token["with"]["repositories"], "team-engineering-skills-plugin")
        self.assertFalse(any("upload-artifact" in s.get("uses", "") for s in steps))
        for step in steps:
            if "uses" in step:
                self.assertRegex(step["uses"], r"@[0-9a-f]{40}$")
