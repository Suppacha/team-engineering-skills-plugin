"""Offline REST fixtures exercise the one-off repair's real policy and writer."""
import copy
import hashlib
import importlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from test_release_github import Fixture, POLICY, ADMIN, PREFIX, run
from release_github import GitHubClient

SHA = "390c967b6daadaab0719a75a35147cb26ff5866f"
HEAD = "d" * 40
ORIGINAL, CI, CURRENT, RELEASE = 35296621274, 35294455224, 999, 391171745


class ReleaseRepairTests(unittest.TestCase):
    def setUp(self):
        self.m = importlib.import_module("repair_release_record")
        self.f = Fixture()
        self.routes = self.f.routes
        self.writes = []
        original = run(ORIGINAL, promotion=True)
        original.update(head_sha=SHA, display_title="Promote " + SHA, status="completed", conclusion="failure",
                        run_started_at="2026-09-18T02:00:00Z", updated_at="2026-09-18T02:20:00Z")
        self.routes[PREFIX + f"/actions/runs/{ORIGINAL}/attempts/1"] = original
        self.routes[PREFIX + f"/actions/runs/{ORIGINAL}/attempts/1/jobs?per_page=100"] = dict(total_count=2, jobs=[
            dict(id=105450373603, run_id=ORIGINAL, head_sha=SHA, run_attempt=1, name="preflight", status="completed", conclusion="success", started_at="2026-09-18T02:00:01Z", completed_at="2026-09-18T02:01:00Z"),
            dict(id=105450687760, run_id=ORIGINAL, head_sha=SHA, run_attempt=1, name="publish", status="completed", conclusion="failure", started_at="2026-09-18T02:18:00Z", completed_at="2026-09-18T02:19:00Z",
                 steps=[dict(name="Run actions/create-github-app-token@fee1f7d63c2ff003460e3d139729b119787bc349", status="completed", conclusion="success"),
                        dict(name="Revalidate live evidence and publish without candidate execution", status="completed", conclusion="failure")])])
        fresh = run(CURRENT, promotion=True)
        fresh.update(head_sha=HEAD, path=".github/workflows/repair-release-record.yml", workflow_id=7,
                     display_title="Repair v2.2.0 release record")
        self.routes[PREFIX + f"/actions/runs/{CURRENT}"] = fresh
        self.routes[PREFIX + "/actions/workflows/repair-release-record.yml"] = dict(id=7, path=fresh["path"], state="active")
        for ident in (ORIGINAL, CURRENT):
            self.routes[PREFIX + f"/actions/runs/{ident}/approvals"] = copy.deepcopy(self.routes[PREFIX + "/actions/runs/20/approvals"])
        ci = run(CI)
        ci.update(head_sha=SHA)
        self.routes[PREFIX + f"/actions/runs/{CI}"] = ci
        self.routes[PREFIX + f"/actions/workflows/5/runs?head_sha={SHA}&event=push&branch=main&per_page=100"] = dict(total_count=1, workflow_runs=[ci])
        self.routes[PREFIX + f"/actions/runs/{CI}/attempts/1/jobs?per_page=100"] = dict(total_count=3, jobs=[
            dict(id=i, run_id=CI, head_sha=SHA, run_attempt=1, name="package (" + os + ")", status="completed", conclusion="success")
            for i, os in enumerate(("windows-latest", "macos-latest", "ubuntu-latest"), 1)])
        self.routes[PREFIX + "/git/ref/heads/stable"] = (404, {}, None)
        self.routes[PREFIX + "/git/matching-refs/heads/stable"] = []
        self.routes[PREFIX + "/git/ref/tags/v2.2.0"] = dict(ref="refs/tags/v2.2.0", object=dict(type="commit", sha=SHA))
        approval = dict(repository=POLICY["repository"], run_id=ORIGINAL, candidate_sha=SHA,
                        environment_id=77, environment_name="team-plugin-stable", reviewer_github_id=123,
                        reviewer_login="Suppacha", state="approved", observed_at="2026-09-18T02:18:43Z",
                        url=f"https://github.com/{POLICY['repository']}/actions/runs/{ORIGINAL}",
                        binding="trusted-run-name-first-attempt", admin_evidence_reference=ADMIN["evidence_reference"])
        self.record = dict(schema_version=1, repository=POLICY["repository"], version="2.2.0", candidate_sha=SHA,
                           previous_stable_sha=None, baseline_sha="6ca868dbccba7d2e2f15dfd5cc6ac105980a8b13", baseline_version="2.1.0",
                           run_id=ORIGINAL, run_url=approval["url"], ci_run_id=CI,
                           ci_url=f"https://github.com/{POLICY['repository']}/actions/runs/{CI}", approval=approval)
        self.release = dict(id=RELEASE, tag_name="v2.2.0", target_commitish=SHA, draft=True, prerelease=False,
                            body=json.dumps(dict(state="prepared", record=self.record)))
        self.routes[PREFIX + "/releases?per_page=100"] = [self.release]
        self.assets_path = PREFIX + f"/releases/{RELEASE}/assets?per_page=100"
        self.routes[self.assets_path] = []
        self.reader = GitHubClient(self.f.request, policy=POLICY, admin_evidence=ADMIN)

    def upload(self, raw):
        self.writes.append(raw)
        self.routes[self.assets_path] = [dict(id=100, name="release-record.json", state="uploaded",
            content_type="application/json", size=len(raw), digest="sha256:" + hashlib.sha256(raw).hexdigest())]
        return {"failure_class": "none", "http_status": 201}

    def repair(self, upload=None):
        return self.m.repair(self.reader, upload or self.upload, CURRENT, HEAD)

    def test_single_upload_preserves_original_canonical_record_and_no_other_mutations(self):
        original = copy.deepcopy(self.release)
        result = self.repair()
        self.assertEqual(result["status"], "repaired")
        self.assertEqual(self.writes, [(json.dumps(self.record, sort_keys=True, separators=(",", ":")) + "\n").encode()])
        self.assertEqual(self.release, original)
        self.assertTrue(all(method == "GET" and body is None for method, _, body in self.f.calls))
        self.assertTrue(any(path.endswith(f"/actions/runs/{ORIGINAL}/attempts/1") for _, path, _ in self.f.calls))
        self.assertFalse(any(path.endswith(f"/actions/runs/{ORIGINAL}") for _, path, _ in self.f.calls))

    def test_matching_present_asset_is_noop_and_conflicting_asset_refuses(self):
        self.upload((json.dumps(self.record, sort_keys=True, separators=(",", ":")) + "\n").encode())
        self.writes.clear()
        self.assertEqual(self.repair()["status"], "already-matching")
        self.assertEqual(self.writes, [])
        self.routes[self.assets_path][0]["digest"] = "sha256:" + "0" * 64
        self.assertEqual(self.repair()["status"], "refused")
        self.assertEqual(self.writes, [])

    def test_empty_historical_reviews_require_attempt_jobs_and_report_recorded_only(self):
        self.routes[PREFIX + f"/actions/runs/{ORIGINAL}/approvals"] = []
        self.assertEqual(self.repair()["historical_review"], "recorded-not-live")
        self.setUp()
        self.routes[PREFIX + f"/actions/runs/{ORIGINAL}/approvals"] = []
        self.routes[PREFIX + f"/actions/runs/{ORIGINAL}/attempts/1/jobs?per_page=100"]["jobs"][1]["conclusion"] = "skipped"
        self.assertEqual(self.repair()["status"], "refused")
        self.assertEqual(self.writes, [])

    def test_uncertain_upload_is_read_back_never_retried(self):
        def uncertain(raw):
            self.upload(raw)
            return {"failure_class": "http", "http_status": 502}
        result = self.repair(uncertain)
        self.assertEqual(result["status"], "repaired")
        self.assertEqual(result["http_status"], 502)
        self.assertEqual(len(self.writes), 1)

    def test_historical_observation_requires_original_publish_execution_interval(self):
        path = PREFIX + f"/actions/runs/{ORIGINAL}/attempts/1/jobs?per_page=100"
        self.routes[path]["jobs"][1]["completed_at"] = "2026-09-18T02:18:01Z"
        self.assertEqual(self.repair()["status"], "refused")
        self.assertEqual(self.writes, [])
        self.setUp()
        self.routes[path]["jobs"][1]["steps"][0]["conclusion"] = "failure"
        self.assertEqual(self.repair()["status"], "refused")
        self.assertEqual(self.writes, [])

    def test_post_upload_asset_fields_are_all_required_for_confirmation(self):
        for key, value in [("size", 0), ("state", "starter"), ("digest", "sha256:" + "0" * 64),
                           ("name", "other.json"), ("content_type", "text/plain")]:
            with self.subTest(key=key):
                self.setUp()
                def wrong(raw):
                    result = self.upload(raw)
                    self.routes[self.assets_path][0][key] = value
                    return result
                self.assertEqual(self.repair(wrong)["status"], "unconfirmed")
                self.assertEqual(len(self.writes), 1)

    def test_read_errors_and_extra_record_fields_never_leak_or_upload(self):
        self.reader.request = lambda *args: (_ for _ in ()).throw(RuntimeError("SECRET_SENTINEL"))
        self.assertNotIn("SECRET_SENTINEL", json.dumps(self.repair()))
        self.assertEqual(self.writes, [])
        self.setUp()
        self.record["private"] = "SECRET_SENTINEL"
        self.release["body"] = json.dumps(dict(state="prepared", record=self.record))
        result = self.repair()
        self.assertEqual(result["status"], "refused")
        self.assertNotIn("SECRET_SENTINEL", json.dumps(result))
        self.assertEqual(self.writes, [])

    def test_failed_upload_without_asset_stops_and_redacts(self):
        def failed(raw):
            self.writes.append(raw)
            raise RuntimeError("SECRET_SENTINEL")
        result = self.repair(failed)
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(len(self.writes), 1)
        self.assertNotIn("SECRET_SENTINEL", json.dumps(result))

    def test_provenance_and_live_guards_reject_before_write(self):
        changes = [
            (f"/actions/runs/{CURRENT}", lambda x: x.update(run_attempt=2)),
            (f"/actions/runs/{CURRENT}", lambda x: x.update(head_sha="e" * 40)),
            (f"/actions/runs/{CURRENT}", lambda x: x.update(path=".github/workflows/promote.yml")),
            (f"/actions/runs/{CURRENT}", lambda x: x.update(display_title="SECRET_SENTINEL")),
            (f"/actions/runs/{ORIGINAL}/attempts/1", lambda x: x.update(run_attempt=3)),
            (f"/actions/runs/{ORIGINAL}/attempts/1", lambda x: x.update(head_sha="e" * 40)),
            (f"/actions/runs/{ORIGINAL}/attempts/1", lambda x: x.update(conclusion="success")),
            (f"/actions/runs/{ORIGINAL}/approvals", lambda x: x[0].update(state="rejected")),
            (f"/actions/runs/{CURRENT}/approvals", lambda x: x[0]["user"].update(id=999)),
            (f"/actions/runs/{ORIGINAL}/approvals", lambda x: x.append(copy.deepcopy(x[0]))),
            ("/environments/team-plugin-stable", lambda x: x["protection_rules"].append({"type": "unknown"})),
            ("/environments/team-plugin-stable/deployment-branch-policies?per_page=100", lambda x: x["branch_policies"][0].update(type="tag")),
            ("/rules/branches/stable?per_page=100", lambda x: x.pop()),
            (f"/actions/runs/{CI}", lambda x: x.update(conclusion="failure")),
        ]
        for suffix, change in changes:
            with self.subTest(suffix=suffix):
                self.setUp()
                change(self.routes[PREFIX + suffix])
                result = self.repair()
                self.assertEqual(result["status"], "refused")
                self.assertEqual(self.writes, [])
                self.assertNotIn("SECRET_SENTINEL", json.dumps(result))

    def test_drift_between_initial_snapshot_and_final_read_refuses(self):
        original_request = self.reader.request
        count = 0
        def drift(method, path, body=None):
            nonlocal count
            if path == PREFIX + "/releases?per_page=100":
                count += 1
                if count == 2:
                    self.release["body"] += " "
            return original_request(method, path, body)
        self.reader.request = drift
        self.assertEqual(self.repair()["status"], "refused")
        self.assertEqual(self.writes, [])

    def test_wrong_record_provenance_and_existing_stable_refuse(self):
        for field, value in [("run_id", 1), ("ci_run_id", 2), ("previous_stable_sha", "e" * 40)]:
            with self.subTest(field=field):
                self.setUp()
                self.record[field] = value
                self.release["body"] = json.dumps(dict(state="prepared", record=self.record))
                self.assertEqual(self.repair()["status"], "refused")
                self.assertEqual(self.writes, [])
        self.setUp()
        self.routes[PREFIX + "/git/ref/heads/stable"] = dict(ref="refs/heads/stable", object=dict(type="commit", sha=SHA))
        self.assertEqual(self.repair()["status"], "refused")
        self.assertEqual(self.writes, [])

    def test_fixed_upload_transport_sends_only_exact_asset_and_sanitizes_http(self):
        seen = []
        class Opener:
            def open(inner, request, timeout):
                seen.append((request, timeout))
                raise HTTPError(request.full_url, 403, "SECRET_SENTINEL", {}, None)
        with patch.object(self.m, "build_opener", return_value=Opener()):
            result = self.m.asset_uploader("SECRET_SENTINEL")(b"{}\n")
        self.assertEqual(result, {"failure_class": "http", "http_status": 403})
        self.assertEqual(len(seen), 1)
        request, timeout = seen[0]
        self.assertEqual(request.full_url, f"https://uploads.github.com{PREFIX}/releases/391171745/assets?name=release-record.json")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.data, b"{}\n")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(timeout, 20)
        self.assertNotIn("SECRET_SENTINEL", json.dumps(result))

    def test_upload_http_status_survives_response_close_failure(self):
        class BadClose(HTTPError):
            def close(self):
                raise RuntimeError("SECRET_SENTINEL")
        class Opener:
            def open(inner, request, timeout):
                raise BadClose(request.full_url, 403, "SECRET_SENTINEL", {}, None)
        with patch.object(self.m, "build_opener", return_value=Opener()):
            result = self.m.asset_uploader("SECRET_SENTINEL")(b"{}\n")
        self.assertEqual(result, {"failure_class": "http", "http_status": 403})

    def test_cli_refuses_wrong_context_before_creating_transport(self):
        with patch.dict("os.environ", {}, clear=True), patch.object(self.m, "github_request") as network, \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(self.m.main([]), 1)
            network.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())["status"], "refused")

    def test_workflow_serializes_with_promoter_and_cannot_select_other_targets(self):
        import yaml
        root = Path(__file__).resolve().parents[1]
        value = yaml.safe_load((root / ".github/workflows/repair-release-record.yml").read_text(encoding="utf-8"))
        trigger = value.get("on", value.get(True))
        self.assertEqual(trigger, {"workflow_dispatch": None})
        self.assertEqual(value["run-name"], "Repair v2.2.0 release record")
        self.assertEqual(value["concurrency"], {"group": "team-plugin-stable-promotion", "cancel-in-progress": False})
        job = value["jobs"]["repair"]
        self.assertEqual(job["environment"], "team-plugin-stable")
        for guard in ("github.run_attempt == 1", "github.ref == 'refs/heads/main'", "github.repository == 'Suppacha/team-engineering-skills-plugin'"):
            self.assertIn(guard, job["if"])
        token = next(s for s in job["steps"] if "create-github-app-token@" in s.get("uses", ""))
        self.assertEqual(token["with"]["permission-contents"], "write")
        self.assertEqual(token["with"]["permission-actions"], "read")
        self.assertFalse(any("upload-artifact" in s.get("uses", "") for s in job["steps"]))
