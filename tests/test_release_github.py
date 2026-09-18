"""Read-only REST boundary tests; package fixtures use real repository bytes."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from release_github import GitHubClient, github_request
except ImportError:
    GitHubClient = github_request = None

SHA, BASE, MAIN = "a" * 40, "b" * 40, "c" * 40
REPO = "Suppacha/team-engineering-skills-plugin"
PREFIX = "/repos/" + REPO
POLICY = {**json.loads((ROOT / "config/release-policy.json").read_text()),
          "reviewer_github_id": 123, "writer_app_id": 456}
RULES = [{"type": kind, "ruleset_id": 88, "ruleset_source_type": "Repository",
          "ruleset_source": REPO} for kind in ("creation", "update", "deletion", "non_fast_forward")]
RULES[1]["parameters"] = {"update_allows_fetch_and_merge": False}
ADMIN = {"schema_version": 1, "repository": REPO, "environment_id": 77,
         "reviewer_github_id": 123, "writer_app_id": 456, "ruleset_ids": [88],
         "reviewed_at": "2026-09-17T00:00:00Z",
         "evidence_reference": "https://github.com/" + REPO + "/issues/1",
         "bypass_review": "only-dedicated-writer-app", "environment_admin_bypass": "disabled"}


def run(run_id=10, attempt=1, promotion=False):
    return {"id": run_id, "run_number": run_id, "run_attempt": attempt,
            "repository": {"full_name": REPO}, "head_repository": {"full_name": REPO},
            "head_sha": MAIN if promotion else SHA, "head_branch": "main",
            "event": "workflow_dispatch" if promotion else "push",
            "path": ".github/workflows/promote.yml" if promotion else ".github/workflows/verify.yml",
            "workflow_id": 6 if promotion else 5,
            "display_title": "Promote " + SHA if promotion else "Verify",
            "status": "in_progress" if promotion else "completed", "conclusion": None if promotion else "success"}


class Fixture:
    def __init__(self):
        self.calls = []
        self.routes = {
            PREFIX: {"full_name": REPO},
            PREFIX + "/git/ref/heads/main": {"ref": "refs/heads/main", "object": {"type": "commit", "sha": MAIN}},
            PREFIX + "/git/ref/heads/stable": {"ref": "refs/heads/stable", "object": {"type": "commit", "sha": BASE}},
            PREFIX + f"/compare/{SHA}...{MAIN}": {"status": "ahead", "merge_base_commit": {"sha": SHA}},
            PREFIX + f"/compare/{BASE}...{SHA}": {"status": "ahead", "merge_base_commit": {"sha": BASE}},
            PREFIX + "/actions/workflows/verify.yml": {"id": 5, "path": ".github/workflows/verify.yml", "state": "active"},
            PREFIX + "/actions/workflows/promote.yml": {"id": 6, "path": ".github/workflows/promote.yml", "state": "active"},
            PREFIX + f"/actions/workflows/5/runs?head_sha={SHA}&event=push&branch=main&per_page=100": {"total_count": 1, "workflow_runs": [run()]},
            PREFIX + "/actions/runs/10": run(),
            PREFIX + "/actions/runs/10/attempts/1/jobs?per_page=100": {"total_count": 3, "jobs": [
                {"id": i, "run_id": 10, "head_sha": SHA, "run_attempt": 1, "name": f"package ({os})", "status": "completed", "conclusion": "success"}
                for i, os in enumerate(("windows-latest", "macos-latest", "ubuntu-latest"), 1)]},
            PREFIX + "/actions/runs/20": run(20, promotion=True),
            PREFIX + "/actions/runs/20/approvals": [{"state": "approved", "comment": "Ship it", "user": {"id": 123, "login": "Suppacha"}, "environments": [{"id": 77, "name": "team-plugin-stable"}]}],
            PREFIX + "/environments/team-plugin-stable": {"id": 77, "name": "team-plugin-stable", "protection_rules": [{"type": "required_reviewers", "prevent_self_review": True, "reviewers": [{"type": "User", "reviewer": {"id": 123, "login": "Suppacha"}}]}, {"type": "branch_policy"}], "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True}},
            PREFIX + "/environments/team-plugin-stable/deployment-branch-policies?per_page=100": {"total_count": 1, "branch_policies": [{"id": 89, "node_id": "synthetic", "name": "main", "type": "branch"}]},
            PREFIX + "/rules/branches/stable?per_page=100": copy.deepcopy(RULES),
        }

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method != "GET" or body is not None:
            raise AssertionError("collector must never write")
        if path not in self.routes:
            raise AssertionError("unexpected REST request: " + path)
        result = self.routes[path]
        return result if isinstance(result, tuple) else (200, {}, copy.deepcopy(result))

    def package(self, sha, mutation=None):
        files = {p.relative_to(ROOT).as_posix(): p.read_bytes()
                 for p in (ROOT / "plugins/team-engineering-skills").rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts}
        for name in ("config/skills-lock.json", ".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json", "LICENSE", "CHANGELOG.md"):
            files[name] = (ROOT / name).read_bytes()
        if mutation:
            mutation(files)
        entries = []
        for name, data in files.items():
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            entries.append({"path": name, "mode": "100644", "type": "blob", "sha": blob, "size": len(data)})
            self.routes[PREFIX + "/git/blobs/" + blob] = {"sha": blob, "size": len(data), "encoding": "base64", "content": base64.b64encode(data).decode()}
        self.routes[PREFIX + f"/git/trees/{sha}?recursive=1"] = {"sha": sha, "truncated": False, "tree": entries}


def apache_license_fixture(files, license_path, payload=None):
    """Keep registry/notices consistent so only license evidence is under test."""
    plugin = "plugins/team-engineering-skills/"
    lock = json.loads(files["config/skills-lock.json"])
    next(s for s in lock["skills"] if s["name"] == "mcp-builder")["notice"]["license_file"] = license_path
    files["config/skills-lock.json"] = json.dumps(lock).encode()
    notices = plugin + "THIRD_PARTY_NOTICES.md"
    files[notices] = files[notices].replace(b"skills/mcp-builder/LICENSE.txt", ("skills/mcp-builder/" + license_path).encode())
    if payload is not None:
        skill_prefix = plugin + "skills/mcp-builder/"
        files[skill_prefix + license_path] = payload
        digest = hashlib.sha256()
        for name in sorted((n for n in files if n.startswith(skill_prefix)), key=lambda n: tuple(n[len(skill_prefix):].split("/"))):
            digest.update(name[len(skill_prefix):].encode())
            digest.update(b"\0")
            digest.update(hashlib.sha256(files[name]).digest())
        registry = json.loads(files[plugin + "registry.json"])
        next(s for s in registry["skills"] if s["name"] == "mcp-builder")["tree_sha256"] = digest.hexdigest()
        files[plugin + "registry.json"] = json.dumps(registry).encode()


class GitHubEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(GitHubClient, "read-only GitHub evidence collector is not implemented")
        self.fixture = Fixture()
        self.client = GitHubClient(self.fixture.request, policy=POLICY, admin_evidence=ADMIN)

    def test_auth_and_unknown_errors_never_mean_first_release(self):
        for status in (401, 403, 404, 429, 500, 502, 302):
            with self.subTest(status=status), self.assertRaises(RuntimeError):
                GitHubClient(lambda *args: (status, {}, {"message": "secret"})).read_stable()

    def test_absence_requires_accessible_repository_and_empty_matching_refs(self):
        self.fixture.routes[PREFIX + "/git/ref/heads/stable"] = (404, {}, {})
        self.fixture.routes[PREFIX + "/git/matching-refs/heads/stable"] = []
        self.assertIsNone(self.client.read_stable())

    def test_two_page_job_listing(self):
        path = PREFIX + "/actions/runs/10/attempts/1/jobs?per_page=100"
        jobs = self.fixture.routes[path]["jobs"]
        self.fixture.routes[path] = (200, {"Link": f'<https://api.github.com{path}&page=2>; rel="next"'}, {"total_count": 3, "jobs": jobs[:1]})
        self.fixture.routes[path + "&page=2"] = {"total_count": 3, "jobs": jobs[1:]}
        self.assertEqual(len(self.client.get_pages(path)), 3)

    def test_attempt_scoped_jobs_need_no_undocumented_attempt_field(self):
        self.fixture.package(SHA)
        self.fixture.package(BASE)
        for job in self.fixture.routes[PREFIX + "/actions/runs/10/attempts/1/jobs?per_page=100"]["jobs"]:
            del job["run_attempt"]
        self.assertEqual(self.client.collect_candidate(SHA, BASE)["ci"]["attempt"], 1)

    def test_retries_are_bounded_and_errors_are_redacted(self):
        for status, expected_calls in ((403, 1), (404, 1), (429, 3), (503, 3)):
            calls = []
            def fail(method, path, body=None):
                calls.append(path)
                return status, {}, {"message": "Authorization: secret-token"}
            with self.subTest(status=status), patch("release_github.time.sleep"), self.assertRaises(RuntimeError) as caught:
                GitHubClient(fail).get_json(PREFIX)
            self.assertNotIn("secret-token", str(caught.exception))
            self.assertEqual(len(calls), expected_calls)

    def test_incomplete_and_cyclic_pagination_rejected(self):
        path = PREFIX + "/rules/branches/stable?per_page=100"
        for response in ((200, {}, {"total_count": 2, "jobs": [{}]}),
                         (200, {"Link": f'<https://api.github.com{path}>; rel="next"'}, [])):
            self.fixture.routes[path] = response
            with self.subTest(response=response), self.assertRaises(RuntimeError):
                self.client.get_pages(path)

    def test_blob_tamper_rejected_even_when_size_matches(self):
        self.fixture.package(SHA)
        key = next(k for k in self.fixture.routes if "/git/blobs/" in k)
        blob = self.fixture.routes[key]
        blob["content"] = base64.b64encode(b"x" * blob["size"]).decode()
        with self.assertRaises(RuntimeError):
            self.client.collect_candidate(SHA, BASE)

    def test_non_ancestor_candidate_or_baseline_rejected(self):
        for path in (f"/compare/{SHA}...{MAIN}", f"/compare/{BASE}...{SHA}"):
            fixture = Fixture()
            fixture.routes[PREFIX + path]["status"] = "diverged"
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                GitHubClient(fixture.request).collect_candidate(SHA, BASE)

    def test_candidate_validator_script_is_never_executed(self):
        self.fixture.package(SHA, lambda files: files.update({"plugins/team-engineering-skills/scripts/framework.py": b"raise SystemExit('candidate script executed')"}))
        self.fixture.package(BASE)
        self.assertTrue(self.client.collect_candidate(SHA, BASE)["candidate"]["valid_package"])

    def test_malicious_pagination_never_receives_request(self):
        path = PREFIX + "/rules/branches/stable?per_page=100"
        for url in ("https://evil.test/stolen", "https://api.github.com@evil.test/stolen", "https://api.github.com/repos/other/repo", "http://api.github.com" + path):
            self.fixture.routes[path] = (200, {"Link": f'<{url}>; rel="next"'}, [])
            with self.subTest(url=url), self.assertRaises(RuntimeError):
                self.client.get_pages(path)

    def test_real_package_and_ci_are_normalized(self):
        self.fixture.package(SHA)
        self.fixture.package(BASE)
        evidence = self.client.collect_candidate(SHA, BASE)
        self.assertTrue(evidence["candidate"]["valid_package"])
        self.assertEqual(evidence["candidate"]["version"], "2.2.0")
        self.assertEqual(len(evidence["candidate"]["skills"]), 15)
        self.assertEqual(len(evidence["ci"]["jobs"]), 3)
        self.assertTrue(evidence["candidate"]["on_main"])

    def test_tampered_actual_package_rejected(self):
        for name in ("plugins/team-engineering-skills/standards/security.md", "plugins/team-engineering-skills/skills/load-testing/SKILL.md", "plugins/team-engineering-skills/VERSION", ".claude-plugin/marketplace.json", "config/skills-lock.json", "plugins/team-engineering-skills/THIRD_PARTY_NOTICES.md"):
            with self.subTest(name=name):
                fixture = Fixture()
                fixture.package(SHA, lambda files: files.update({name: b"tampered"}))
                fixture.package(BASE)
                with self.assertRaises((ValueError, RuntimeError)):
                    GitHubClient(fixture.request).collect_candidate(SHA, BASE)

    def test_apache_license_file_must_be_present_nonempty_and_skill_local(self):
        for path, payload in (("MISSING-LICENSE", None), ("EMPTY-LICENSE", b""),
                              ("BLANK-LICENSE", b" \n\t"), ("../supabase/SKILL.md", None),
                              ("../../standards/security.md", None), ("/LICENSE", None),
                              ("..\\supabase\\SKILL.md", None), ("C:\\LICENSE", None),
                              ("LICENSE.txt.", None)):
            fixture = Fixture()
            fixture.package(SHA, lambda files: apache_license_fixture(files, path, payload))
            fixture.package(BASE)
            with self.subTest(path=path), self.assertRaises((ValueError, RuntimeError)):
                GitHubClient(fixture.request).collect_candidate(SHA, BASE)

    def test_apache_license_file_can_be_nested_inside_skill(self):
        payload = (ROOT / "plugins/team-engineering-skills/skills/mcp-builder/LICENSE.txt").read_bytes()
        self.fixture.package(SHA, lambda files: apache_license_fixture(files, "legal/LICENSE.txt", payload))
        self.fixture.package(BASE)
        self.assertTrue(self.client.collect_candidate(SHA, BASE)["candidate"]["valid_package"])

    def test_tree_rejects_symlink_submodule_traversal_and_truncation(self):
        for mode, kind, path in (("120000", "blob", "plugins/link"), ("160000", "commit", "plugins/submodule"), ("100644", "blob", "../escape"), ("100644", "blob", "plugins/CON")):
            self.fixture.package(SHA)
            tree = self.fixture.routes[PREFIX + f"/git/trees/{SHA}?recursive=1"]
            tree["tree"].append({"path": path, "mode": mode, "type": kind, "sha": BASE, "size": 1})
            with self.subTest(mode=mode, path=path), self.assertRaises((RuntimeError, ValueError)):
                self.client.collect_candidate(SHA, BASE)
        self.fixture.package(SHA)
        self.fixture.routes[PREFIX + f"/git/trees/{SHA}?recursive=1"]["truncated"] = True
        with self.assertRaises(RuntimeError):
            self.client.collect_candidate(SHA, BASE)

    def test_latest_rerun_failure_is_not_hidden_by_old_success(self):
        self.fixture.package(SHA)
        self.fixture.package(BASE)
        latest = run(11, 2)
        latest["conclusion"] = "failure"
        self.fixture.routes[PREFIX + f"/actions/workflows/5/runs?head_sha={SHA}&event=push&branch=main&per_page=100"] = {"total_count": 2, "workflow_runs": [run(), latest]}
        self.fixture.routes[PREFIX + "/actions/runs/11"] = latest
        self.fixture.routes[PREFIX + "/actions/runs/11/attempts/2/jobs?per_page=100"] = {"total_count": 0, "jobs": []}
        evidence = self.client.collect_candidate(SHA, BASE)
        self.assertEqual(evidence["ci"]["attempt"], 2)
        self.assertEqual(evidence["ci"]["conclusion"], "failure")

    def test_newer_verification_run_during_collection_rejected(self):
        self.fixture.package(SHA)
        self.fixture.package(BASE)
        original = self.fixture.request
        count = 0
        def newer(method, path, body=None):
            nonlocal count
            result = original(method, path, body)
            if "/runs?head_sha=" in path:
                count += 1
                if count > 1:
                    result[2]["workflow_runs"].append(run(11))
                    result[2]["total_count"] = 2
            return result
        with self.assertRaises(RuntimeError):
            GitHubClient(newer).collect_candidate(SHA, BASE)

    def test_wrong_repository_rejected(self):
        self.fixture.routes[PREFIX]["full_name"] = "attacker/fork"
        with self.assertRaises(RuntimeError):
            self.client.collect_candidate(SHA, BASE)

    def test_main_movement_rejected(self):
        self.fixture.package(SHA)
        self.fixture.package(BASE)
        original = self.fixture.request
        count = 0
        def moving(method, path, body=None):
            nonlocal count
            result = original(method, path, body)
            if path == PREFIX + "/git/ref/heads/main":
                count += 1
                if count > 1:
                    result[2]["object"]["sha"] = "d" * 40
            return result
        with self.assertRaises(RuntimeError):
            GitHubClient(moving).collect_candidate(SHA, BASE)

    def test_real_review_shape_has_observation_time_not_invented_approval_time(self):
        result = self.client.collect_approval(20, SHA)
        self.assertEqual(result["reviewer_github_id"], 123)
        self.assertEqual(result["candidate_sha"], SHA)
        self.assertIn("observed_at", result)
        self.assertNotIn("approved_at", result)

    def test_owner_can_explicitly_approve_own_dispatched_run(self):
        self.fixture.routes[PREFIX + "/actions/runs/20"]["actor"] = {"id": 123, "login": "Suppacha"}
        self.fixture.routes[PREFIX + "/environments/team-plugin-stable"]["protection_rules"][0]["prevent_self_review"] = False
        self.assertEqual(self.client.collect_approval(20, SHA)["reviewer_github_id"], 123)

    def test_environment_protection_rule_order_is_irrelevant(self):
        self.fixture.routes[PREFIX + "/environments/team-plugin-stable"]["protection_rules"].reverse()
        self.assertEqual(self.client.collect_approval(20, SHA)["environment_id"], 77)

    def test_environment_modes_and_duplicate_or_missing_rules_rejected(self):
        env_path = PREFIX + "/environments/team-plugin-stable"
        for mode in (None, {}, {"protected_branches": True, "custom_branch_policies": False},
                     {"protected_branches": False, "custom_branch_policies": False},
                     {"protected_branches": True, "custom_branch_policies": True},
                     {"protected_branches": 0, "custom_branch_policies": 1}):
            fixture = Fixture()
            fixture.routes[env_path]["deployment_branch_policy"] = mode
            with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                GitHubClient(fixture.request, policy=POLICY, admin_evidence=ADMIN).collect_approval(20, SHA)
        for types in (("required_reviewers",), ("branch_policy",),
                      ("required_reviewers", "required_reviewers"),
                      ("branch_policy", "branch_policy"), ("required_reviewers", "unknown")):
            fixture = Fixture()
            rules = fixture.routes[env_path]["protection_rules"]
            by_type = {r["type"]: r for r in rules}
            fixture.routes[env_path]["protection_rules"] = [copy.deepcopy(by_type.get(t, {"type": t})) for t in types]
            with self.subTest(types=types), self.assertRaises(RuntimeError):
                GitHubClient(fixture.request, policy=POLICY, admin_evidence=ADMIN).collect_approval(20, SHA)

    def test_environment_branch_policy_rejects_extra_wildcard_tag_and_unknown_type(self):
        path = PREFIX + "/environments/team-plugin-stable/deployment-branch-policies?per_page=100"
        main = {"id": 89, "name": "main", "type": "branch"}
        for policies in ([], [main, {**main, "id": 90, "name": "feature"}],
                         [{**main, "name": "*"}], [{**main, "name": "release/*"}],
                         [{**main, "name": "refs/heads/main"}], [{**main, "type": "tag"}],
                         [{"id": 89, "name": "main"}], [{**main, "type": None}],
                         [{**main, "type": "unknown"}], [{**main, "id": True}]):
            fixture = Fixture()
            fixture.routes[path] = {"total_count": len(policies), "branch_policies": policies}
            with self.subTest(policies=policies), self.assertRaises(RuntimeError):
                GitHubClient(fixture.request, policy=POLICY, admin_evidence=ADMIN).collect_approval(20, SHA)

    def test_environment_branch_policy_pagination_is_complete_before_decision(self):
        path = PREFIX + "/environments/team-plugin-stable/deployment-branch-policies?per_page=100"
        next_page = path + "&page=2"
        main = self.fixture.routes[path]["branch_policies"]
        self.fixture.routes[path] = (200, {"Link": f'<https://api.github.com{next_page}>; rel="next"'}, {"total_count": 1, "branch_policies": []})
        self.fixture.routes[next_page] = {"total_count": 1, "branch_policies": main}
        self.assertEqual(self.client.collect_approval(20, SHA)["environment_id"], 77)
        self.fixture.routes[path] = (200, {"Link": f'<https://api.github.com{next_page}>; rel="next"'}, {"total_count": 2, "branch_policies": main})
        self.fixture.routes[next_page] = {"total_count": 2, "branch_policies": [{"id": 90, "name": "main", "type": "tag"}]}
        with self.assertRaisesRegex(RuntimeError, "main-only"):
            self.client.collect_approval(20, SHA)

    def test_environment_branch_policy_permission_failure_is_not_bypassed(self):
        path = PREFIX + "/environments/team-plugin-stable/deployment-branch-policies?per_page=100"
        self.fixture.routes[path] = (403, {}, {"message": "secret"})
        with self.assertRaisesRegex(RuntimeError, "403"):
            self.client.collect_approval(20, SHA)

    def test_approval_failclosed_table(self):
        cases = [
            ("/actions/runs/20", lambda x: x.update(display_title="Promote " + BASE)),
            ("/actions/runs/20", lambda x: x.update(run_attempt=2)),
            ("/actions/runs/20", lambda x: x.update(head_branch="feature")),
            ("/actions/runs/20", lambda x: x["repository"].update(full_name="attacker/fork")),
            ("/actions/runs/20/approvals", lambda x: x[0]["user"].update(id=999)),
            ("/actions/runs/20/approvals", lambda x: x[0].update(state="rejected")),
            ("/environments/team-plugin-stable", lambda x: x["protection_rules"].append({"type": "unknown"})),
            ("/environments/team-plugin-stable", lambda x: x["protection_rules"][0].update(prevent_self_review="false")),
            ("/rules/branches/stable?per_page=100", lambda x: x.pop()),
            ("/rules/branches/stable?per_page=100", lambda x: x[1]["parameters"].update(update_allows_fetch_and_merge=True)),
            ("/rules/branches/stable?per_page=100", lambda x: x.append({"type": "unknown", "ruleset_id": 88})),
        ]
        for path, mutation in cases:
            fixture = Fixture()
            mutation(fixture.routes[PREFIX + path])
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                GitHubClient(fixture.request, policy=POLICY, admin_evidence=ADMIN).collect_approval(20, SHA)

    def test_admin_evidence_missing_or_mismatched_rejected(self):
        for admin in (None, {}, {**ADMIN, "writer_app_id": 999}, {**ADMIN, "ruleset_ids": [99]}, {**ADMIN, "evidence_reference": ""}):
            with self.subTest(admin=admin), self.assertRaises(RuntimeError):
                GitHubClient(self.fixture.request, policy=POLICY, admin_evidence=admin).collect_approval(20, SHA)

    def test_unreadable_approval_history_is_actionable_failure(self):
        self.fixture.routes[PREFIX + "/actions/runs/20/approvals"] = (403, {}, {"message": "sensitive"})
        with self.assertRaisesRegex(RuntimeError, "403") as caught:
            self.client.collect_approval(20, SHA)
        self.assertNotIn("sensitive", str(caught.exception))

    def test_transport_refuses_write_and_cross_host(self):
        request = github_request("do-not-leak")
        for method, path in (("POST", PREFIX), ("GET", "https://evil.test/"), ("GET", "//evil.test/")):
            with self.subTest(method=method, path=path), self.assertRaises(RuntimeError):
                request(method, path)

    def test_transport_timeout_body_bound_redirect_and_secret_redaction(self):
        class Response(io.BytesIO):
            code = 200
            headers = {}
        class Opener:
            def __init__(self, response=None, error=None):
                self.response, self.error, self.requests = response, error, []
            def open(self, req, timeout):
                self.requests.append((req.full_url, timeout))
                if self.error:
                    raise self.error
                return self.response
        from release_github import MAX_BODY, _NoRedirect
        for response in (Response(b"x" * (MAX_BODY + 1)), Response(b"not-json")):
            opener = Opener(response)
            with patch("release_github.build_opener", return_value=opener), self.assertRaises(RuntimeError):
                github_request("secret-token")("GET", PREFIX)
            self.assertEqual(opener.requests, [("https://api.github.com" + PREFIX, 20)])
        opener = Opener(error=URLError("Authorization: secret-token"))
        with patch("release_github.build_opener", return_value=opener), self.assertRaises(RuntimeError) as caught:
            github_request("secret-token")("GET", PREFIX)
        self.assertNotIn("secret-token", str(caught.exception))
        redirect = HTTPError("https://api.github.com" + PREFIX, 302, "redirect", {"Location": "https://evil.test/"}, io.BytesIO())
        with patch("release_github.build_opener", return_value=Opener(error=redirect)):
            self.assertEqual(github_request("secret-token")("GET", PREFIX)[0], 302)
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://evil.test/"))


if __name__ == "__main__":
    unittest.main()
