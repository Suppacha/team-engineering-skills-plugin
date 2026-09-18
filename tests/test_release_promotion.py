"""Publisher state transitions, with remote side effects isolated in a fake."""
import copy
import importlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
A, B, C = "a" * 40, "b" * 40, "c" * 40


class FakePromotionClient:
    def __init__(self, stable=B):
        self.stable = stable
        self.writes = []
        self.events = []
        self.record = None
        self.fail = None
        self.drift = False
        self.valid = True
        self.revalidations = 0

    def read_stable(self):
        self.events.append("read")
        return self.stable

    def revalidate(self, candidate, previous, run_id):
        self.events.append("validate")
        self.revalidations += 1
        if not self.valid or (self.fail == "protection" and self.revalidations > 1):
            raise ValueError("protection/approval absent")
        return {"schema_version": 1, "version": "2.2.0", "candidate_sha": candidate,
                "previous_stable_sha": previous, "run_id": run_id,
                "repository": "test/repo", "approval": {"run_id": run_id}}

    def read_record(self, version):
        return copy.deepcopy(self.record)

    def prepare_record(self, record):
        self.events.append("prepare")
        self.writes.append("prepare")
        if self.fail != "prepare-before":
            self.record = {"record": copy.deepcopy(record), "state": "prepared"}
        if self.drift:
            self.stable = C
        if self.fail in ("prepare-before", "prepare-after"):
            raise RuntimeError("uncertain prepare")

    def create_stable(self, candidate):
        self._move(candidate, "create")

    def update_stable(self, candidate, *, force):
        if force is not False:
            raise AssertionError("force forbidden")
        self._move(candidate, "update")

    def _move(self, candidate, kind):
        self.events.append(kind)
        self.writes.append(kind)
        if self.fail != "ref-before":
            self.stable = candidate
        if self.fail in ("ref-before", "ref-after"):
            raise RuntimeError("uncertain ref write")

    def finalize_record(self, record, approval):
        self.events.append("finalize")
        self.writes.append("finalize")
        if self.fail != "finalize-before":
            self.record["state"] = "recorded"
        if self.fail in ("finalize-before", "finalize-after"):
            raise RuntimeError("uncertain finalize")


class PromotionTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "scripts/promote_release.py"
        self.assertTrue(path.exists(), "isolated release publisher not implemented")
        self.module = importlib.import_module("promote_release")
        self.request = {"candidate_sha": A, "previous_stable_sha": B, "run_id": 42}

    def publish(self, client):
        return self.module.publish_release(client, self.request)

    def test_stable_moved_aborts_without_writes(self):
        client = FakePromotionClient(C)
        with self.assertRaises(ValueError):
            self.publish(client)
        self.assertEqual(client.writes, [])

    def test_prepared_record_precedes_nonforce_move_and_finalize(self):
        client = FakePromotionClient()
        result = self.publish(client)
        self.assertEqual(result["state"], "recorded")
        self.assertEqual(client.stable, A)
        self.assertEqual(client.writes, ["prepare", "update", "finalize"])
        self.assertGreaterEqual(client.revalidations, 2)
        self.assertEqual(client.events[client.events.index("update") - 1], "read")

    def test_initial_release_creates_ref(self):
        client = FakePromotionClient(None)
        self.request["previous_stable_sha"] = None
        self.assertEqual(self.publish(client)["state"], "recorded")
        self.assertEqual(client.writes, ["prepare", "create", "finalize"])

    def test_untrusted_record_fields_do_not_override_live_evidence(self):
        client = FakePromotionClient()
        self.request.update(version="99.0.0", approval={"approved": True}, worktree="secret")
        self.publish(client)
        self.assertEqual(client.record["record"]["version"], "2.2.0")
        self.assertNotIn("worktree", client.record["record"])

    def test_missing_approval_or_protection_rejects(self):
        client = FakePromotionClient()
        client.valid = False
        with self.assertRaises(ValueError):
            self.publish(client)
        self.assertEqual(client.writes, [])

    def test_protection_disappears_after_prepare_no_ref_write(self):
        client = FakePromotionClient()
        client.fail = "protection"
        result = self.publish(client)
        self.assertEqual(result["state"], "prepared")
        self.assertTrue(result["partial_failure"])
        self.assertEqual(client.writes, ["prepare"])

    def test_stable_moves_after_prepare_no_ref_write(self):
        client = FakePromotionClient()
        client.drift = True
        self.assertTrue(self.publish(client)["partial_failure"])
        self.assertEqual(client.writes, ["prepare"])

    def test_uncertain_writes_read_back_never_blind_retry(self):
        for failure, state, writes in [
            ("prepare-before", "unprepared", ["prepare"]),
            ("prepare-after", "recorded", ["prepare", "update", "finalize"]),
            ("ref-before", "prepared", ["prepare", "update"]),
            ("ref-after", "recorded", ["prepare", "update", "finalize"]),
            ("finalize-before", "promoted", ["prepare", "update", "finalize"]),
            ("finalize-after", "recorded", ["prepare", "update", "finalize"]),
        ]:
            with self.subTest(failure=failure):
                client = FakePromotionClient()
                client.fail = failure
                result = self.publish(client)
                self.assertEqual(result["state"], state)
                self.assertEqual(client.writes, writes)
                if state != "recorded":
                    self.assertTrue(result["partial_failure"])
                    self.assertIn("repair", result)

    def test_fresh_dispatch_can_finalize_same_candidate_without_removing_it(self):
        client = FakePromotionClient()
        client.fail = "finalize-before"
        self.publish(client)
        client.fail = None
        client.writes.clear()
        self.request["run_id"] = 43
        self.assertEqual(self.publish(client)["state"], "recorded")
        self.assertEqual(client.writes, ["finalize"])
        self.assertEqual(client.record["record"]["run_id"], 42)

    def test_same_version_conflicting_candidate_rejected(self):
        client = FakePromotionClient()
        record = client.revalidate(C, B, 40)
        client.record = {"record": record, "state": "prepared"}
        with self.assertRaises(ValueError):
            self.publish(client)
        self.assertEqual(client.writes, [])

    def test_existing_stable_candidate_without_matching_record_rejected(self):
        client = FakePromotionClient(A)
        with self.assertRaises(ValueError):
            self.publish(client)
        self.assertEqual(client.writes, [])

    def test_invalid_sha_and_run_fail_before_remote_writes(self):
        for field, value in [("candidate_sha", "main"), ("previous_stable_sha", "bad"), ("run_id", True)]:
            with self.subTest(field=field):
                client = FakePromotionClient()
                request = dict(self.request, **{field: value})
                with self.assertRaises(ValueError):
                    self.module.publish_release(client, request)
                self.assertEqual(client.writes, [])


class ReleaseAPI:
    """In-memory documented GitHub shapes; fake only the network boundary."""
    def __init__(self):
        self.policy = {"repository": "test/repo"}
        self.prefix = "/repos/test/repo"
        self.tags = {}
        self.releases = []
        self.writes = []
        self.fail_after = None

    def _get(self, path, *, missing=False):
        tag = path.split("/git/ref/tags/")[-1]
        if tag not in self.tags:
            return 404, {}, None
        return 200, {}, {"ref": "refs/tags/" + tag, "object": {"type": "commit", "sha": self.tags[tag]}}

    def get_pages(self, path):
        if "/matching-refs/tags/" in path:
            return [{"ref": "refs/tags/" + t} for t in self.tags]
        if path.endswith("/assets?per_page=100"):
            return copy.deepcopy(self.releases[0]["assets"])
        return copy.deepcopy(self.releases)

    def get_json(self, path):
        if "/matching-refs/tags/" in path:
            return self.get_pages(path)
        if path == self.prefix:
            return {"full_name": "test/repo"}
        raise AssertionError(path)

    def write(self, method, path, body, *, upload=False):
        self.writes.append((method, path, copy.deepcopy(body), upload))
        if path.endswith("/git/refs"):
            self.tags[body["ref"].removeprefix("refs/tags/")] = body["sha"]
        elif path.endswith("/releases"):
            self.releases.append(dict(body, id=11, assets=[], immutable=False))
        elif "/assets?name=" in path:
            self.releases[0]["assets"].append({"id": 12, "name": "release-record.json", "state": "uploaded",
                "size": len(body), "digest": "sha256:" + hashlib.sha256(body).hexdigest(),
                "content_type": "application/json"})
        elif path.endswith("/releases/11"):
            self.releases[0].update(body)
        else:
            raise AssertionError(path)
        if self.fail_after and self.fail_after in path:
            raise RuntimeError("uncertain network response")
        return {"id": 11}


class WriterTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "scripts/release_writer.py"
        self.assertTrue(path.exists(), "bounded writer transport not implemented")
        self.module = importlib.import_module("release_writer")
        self.api = ReleaseAPI()
        self.writer = self.module.ReleaseWriter(self.api, self.api.write)
        self.record = {"schema_version": 1, "repository": "test/repo", "version": "2.2.0",
                       "candidate_sha": A, "previous_stable_sha": B, "run_id": 42,
                       "approval": {"run_id": 42}}

    def test_draft_tag_and_digest_verified_asset_precede_publish(self):
        self.writer.prepare_record(self.record)
        self.assertEqual(self.api.tags, {"v2.2.0": A})
        saved = self.writer.read_record("2.2.0")
        self.assertEqual(saved, {"record": self.record, "state": "prepared"})
        self.assertTrue(self.api.releases[0]["draft"])
        self.assertEqual([x[0] for x in self.api.writes], ["POST", "POST", "POST"])
        self.writer.finalize_record(self.record, {"run_id": 43})
        self.assertFalse(self.api.releases[0]["draft"])
        self.assertEqual(self.writer.read_record("2.2.0")["state"], "recorded")
        self.assertEqual(json.loads(self.api.releases[0]["body"])["finalization_approval"], {"run_id": 43})

    def test_conflicting_tag_rejected_without_any_write(self):
        self.api.tags["v2.2.0"] = C
        with self.assertRaises(ValueError):
            self.writer.prepare_record(self.record)
        self.assertEqual(self.api.writes, [])

    def test_asset_digest_mismatch_and_duplicate_records_fail_closed(self):
        self.writer.prepare_record(self.record)
        self.api.releases[0]["assets"][0]["digest"] = "sha256:" + "0" * 64
        with self.assertRaises(ValueError):
            self.writer.read_record("2.2.0")
        self.api.releases.append(copy.deepcopy(self.api.releases[0]))
        with self.assertRaises(ValueError):
            self.writer.read_record("2.2.0")

    def test_each_uncertain_prepare_write_is_read_back_once(self):
        for suffix in ("/git/refs", "/releases", "/assets?name="):
            with self.subTest(suffix=suffix):
                api = ReleaseAPI()
                api.fail_after = suffix
                writer = self.module.ReleaseWriter(api, api.write)
                writer.prepare_record(self.record)
                self.assertEqual(writer.read_record("2.2.0")["state"], "prepared")
                self.assertEqual(len(api.writes), 3)

    def test_existing_prepared_and_published_records_never_overwritten(self):
        self.writer.prepare_record(self.record)
        self.api.writes.clear()
        self.writer.prepare_record(self.record)
        self.assertEqual(self.api.writes, [])
        self.writer.finalize_record(self.record, {"run_id": 42})
        self.api.writes.clear()
        self.writer.finalize_record(self.record, {"run_id": 43})
        self.assertEqual(self.api.writes, [])

    def test_transport_rejects_out_of_scope_routes_and_force(self):
        request = self.module.writer_request("test-credential", "test/repo")
        for method, path, body, upload in [
            ("DELETE", "/repos/test/repo/git/refs/heads/stable", {}, False),
            ("PATCH", "/repos/other/repo/git/refs/heads/stable", {}, False),
            ("PATCH", "/repos/test/repo/git/refs/heads/main", {"sha": A, "force": False}, False),
            ("PATCH", "/repos/test/repo/git/refs/heads/stable", {"sha": A, "force": True}, False),
            ("POST", "https://evil.example/", {}, False),
            ("POST", "/repos/test/repo/releases/1/assets?name=wrong", b"{}", True),
        ]:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    request(method, path, body, upload=upload)

    def test_stable_update_never_allows_force(self):
        with self.assertRaises(ValueError):
            self.writer.update_stable(A, force=True)
        self.assertEqual(self.api.writes, [])

    def test_transport_success_uses_fixed_hosts_and_nonforce_payload(self):
        requests = []
        class Response(io.BytesIO):
            code = 201
        class Opener:
            def open(self, request, timeout):
                requests.append((request, timeout))
                return Response(b'{"id":11}')
        with patch.object(self.module, "build_opener", return_value=Opener()):
            call = self.module.writer_request("test-credential", "test/repo")
            call("PATCH", "/repos/test/repo/git/refs/heads/stable", {"sha": A, "force": False})
            call("POST", "/repos/test/repo/releases/11/assets?name=release-record.json", b"{}", upload=True)
        self.assertEqual(requests[0][0].full_url, "https://api.github.com/repos/test/repo/git/refs/heads/stable")
        self.assertEqual(json.loads(requests[0][0].data), {"sha": A, "force": False})
        self.assertEqual(requests[1][0].full_url, "https://uploads.github.com/repos/test/repo/releases/11/assets?name=release-record.json")
        self.assertEqual([r[1] for r in requests], [20, 20])

    def test_write_errors_are_redacted_and_never_retried(self):
        for error in (URLError("test-credential"), OSError("test-credential"),
                      HTTPError("https://api.github.com", 302, "test-credential", {}, None)):
            class Opener:
                calls = 0
                def open(self, request, timeout):
                    self.calls += 1
                    raise error
            opener = Opener()
            with patch.object(self.module, "build_opener", return_value=opener):
                call = self.module.writer_request("test-credential", "test/repo")
                with self.assertRaises(RuntimeError) as caught:
                    call("PATCH", "/repos/test/repo/git/refs/heads/stable", {"sha": A, "force": False})
            self.assertNotIn("test-credential", str(caught.exception))
            self.assertEqual(opener.calls, 1)
        self.assertIsNone(self.module.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example"))


class CandidateReader:
    policy = {"repository": "test/repo"}
    def __init__(self, stable=B):
        self.stable = stable
        self.baselines = []
        self.bad_ci = False
    def read_stable(self):
        return self.stable
    def collect_candidate(self, candidate, baseline):
        self.baselines.append(baseline)
        return {"candidate": {"sha": candidate, "version": "2.2.0", "valid_package": True,
                              "on_main": True, "skills": {}},
                "baseline": {"sha": baseline, "version": "2.1.0", "skills": {}},
                "ci": {"sha": candidate, "event": "push", "branch": "main", "workflow": ".github/workflows/verify.yml",
                       "status": "completed", "conclusion": "failure" if self.bad_ci else "success", "attempt": 1,
                       "jobs": {"package (windows-latest)": "success", "package (macos-latest)": "success", "package (ubuntu-latest)": "success"},
                       "run_id": 10, "url": "https://github.com/test/repo/actions/runs/10"}}
    def collect_approval(self, run_id, candidate):
        return {"run_id": run_id, "candidate_sha": candidate, "url": "https://github.com/test/repo/actions/runs/42",
                "observed_at": "2026-09-17T00:00:00Z"}


class CLITests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("promote_release")

    def test_preflight_uses_real_baseline_when_absent_and_runs_pure_policy(self):
        reader = CandidateReader(None)
        result = self.module.preflight(reader, A)
        self.assertEqual(result["expected_stable"], "ABSENT")
        self.assertEqual(reader.baselines, ["6ca868dbccba7d2e2f15dfd5cc6ac105980a8b13"])
        reader.bad_ci = True
        with self.assertRaises(ValueError):
            self.module.preflight(reader, A)

    def test_cli_preflight_writes_safe_output_without_protected_config(self):
        reader = CandidateReader()
        with tempfile.TemporaryDirectory() as tmp:
            output, ghoutput = Path(tmp) / "preflight.json", Path(tmp) / "output"
            with patch.dict(os.environ, {"GH_READ_TOKEN": "read-only", "GITHUB_OUTPUT": str(ghoutput)}, clear=True), \
                    patch.object(self.module, "GitHubClient", return_value=reader), patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(self.module.main(["preflight", "--candidate", A, "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text())["candidate_sha"], A)
            self.assertEqual(ghoutput.read_text(), "expected_stable=" + B + "\n")

    def test_publish_wrong_context_or_missing_protected_config_never_reads_network(self):
        env = {"GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "42"}
        for change in ({}, {"GITHUB_RUN_ATTEMPT": "2"}, {"GITHUB_REF": "refs/heads/evil"}, {"GITHUB_EVENT_NAME": "pull_request"}):
            with patch.dict(os.environ, dict(env, **change), clear=True), \
                    patch.object(self.module, "github_request", side_effect=AssertionError("network must not initialize")), \
                    patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(self.module.main(["publish", "--candidate", A, "--expected-stable", B, "--run-id", "42"]), 1)

    def test_fresh_record_contains_observation_time_not_fabricated_approval_time(self):
        client = self.module.PromotionClient(CandidateReader(), None)
        record = client.revalidate(A, B, 42)
        self.assertEqual(record["baseline_version"], "2.1.0")
        self.assertEqual(record["ci_run_id"], 10)
        self.assertIn("observed_at", record["approval"])
        self.assertNotIn("approved_at", record["approval"])

    def test_writer_refusal_does_not_emit_a_credential_in_diagnostics(self):
        with patch.dict(os.environ, {"GH_READ_TOKEN": "secret-material"}, clear=True), \
                patch.object(self.module, "GitHubClient", side_effect=RuntimeError("secret-material")), \
                patch("sys.stderr", new_callable=io.StringIO) as error:
            self.assertEqual(self.module.main(["preflight", "--candidate", A, "--output", "unused.json"]), 1)
        self.assertNotIn("secret-material", error.getvalue())

    def test_recovery_ref_drift_cannot_be_hidden_by_original_record_baseline(self):
        reader = CandidateReader(B)  # Preflight saw A, now stable unexpectedly B.
        reader._package = lambda sha: {"version": "2.2.0"}
        remote = FakePromotionClient(B)
        remote.record = {"record": remote.revalidate(A, B, 40), "state": "prepared"}
        env = {"GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch",
               "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "42",
               "GITHUB_REPOSITORY": "Suppacha/team-engineering-skills-plugin",
               "RELEASE_REVIEWER_ID": "123", "RELEASE_WRITER_APP_ID": "456",
               "RELEASE_ADMIN_EVIDENCE": "{}", "GH_WRITER_TOKEN": "test-only"}
        with patch.dict(os.environ, env, clear=True), patch.object(self.module, "GitHubClient", return_value=reader), \
                patch("release_writer.ReleaseWriter", return_value=remote), \
                patch.object(self.module, "PromotionClient", return_value=remote), \
                patch("sys.stdout", new_callable=io.StringIO), patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(self.module.main(["publish", "--candidate", A, "--expected-stable", A, "--run-id", "42"]), 1)
        self.assertEqual(remote.writes, [])
