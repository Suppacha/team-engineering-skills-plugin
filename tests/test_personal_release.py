from pathlib import Path
import base64
import copy
import hashlib
import io
import json
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from team_updater.release import Candidate, PublicReleaseClient, check_upgrade


REPOSITORY = "Suppacha/team-engineering-skills-plugin"
PREFIX = "/repos/" + REPOSITORY
SHA = "a" * 40
OLD_SHA = "b" * 40
VERSION = "2.2.0"


def approval(run_id):
    return {
        "repository": REPOSITORY,
        "run_id": run_id,
        "candidate_sha": SHA,
        "environment_id": 77,
        "environment_name": "team-plugin-stable",
        "reviewer_github_id": 12345,
        "reviewer_login": "Suppacha",
        "state": "approved",
        "observed_at": "2026-09-17T01:02:03+00:00",
        "url": f"https://github.com/{REPOSITORY}/actions/runs/{run_id}",
        "binding": "trusted-run-name-first-attempt",
        "admin_evidence_reference": "admin/release-controls-2026-09-17",
    }


def fixture_routes():
    record = {
        "schema_version": 1,
        "repository": REPOSITORY,
        "version": VERSION,
        "candidate_sha": SHA,
        "previous_stable_sha": OLD_SHA,
        "baseline_sha": OLD_SHA,
        "baseline_version": "2.1.0",
        "run_id": 991,
        "run_url": f"https://github.com/{REPOSITORY}/actions/runs/991",
        "ci_run_id": 881,
        "ci_url": f"https://github.com/{REPOSITORY}/actions/runs/881",
        "approval": approval(991),
    }
    canonical = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
    release = {
        "id": 42,
        "tag_name": "v" + VERSION,
        "target_commitish": SHA,
        "draft": False,
        "prerelease": False,
        "body": json.dumps({
            "state": "promoted",
            "record": record,
            "finalization_approval": approval(992),
        }),
    }
    return {
        PREFIX + "/git/ref/heads/stable": {
            "ref": "refs/heads/stable", "object": {"type": "commit", "sha": SHA}
        },
        PREFIX + f"/contents/VERSION?ref={SHA}": {
            "type": "file", "encoding": "base64", "size": len(VERSION) + 1,
            "content": base64.b64encode((VERSION + "\n").encode()).decode(),
            "sha": "c" * 40,
        },
        PREFIX + "/releases/tags/v" + VERSION: release,
        PREFIX + "/git/ref/tags/v" + VERSION: {
            "ref": "refs/tags/v" + VERSION, "object": {"type": "commit", "sha": SHA}
        },
        PREFIX + "/releases/42/assets?per_page=100&page=1": [{
            "id": 43, "name": "release-record.json", "state": "uploaded",
            "content_type": "application/json", "size": len(canonical),
            "digest": "sha256:" + hashlib.sha256(canonical).hexdigest(),
        }],
    }


class Fixture:
    def __init__(self):
        self.routes = fixture_routes()
        self.paths = []

    def request(self, path):
        self.paths.append(path)
        if path not in self.routes:
            raise RuntimeError("unexpected test path: " + path)
        value = self.routes[path]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)


class PublicReleaseTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.client = PublicReleaseClient(self.fixture.request)

    def test_reads_valid_promoted_release(self):
        candidate = self.client.candidate()
        self.assertEqual(candidate.version, VERSION)
        self.assertEqual(candidate.sha, SHA)
        self.assertEqual(candidate.record["approval"]["reviewer_github_id"], 12345)

    def test_accepts_github_base64_line_wrapping(self):
        path = PREFIX + f"/contents/VERSION?ref={SHA}"
        content = self.fixture.routes[path]["content"]
        self.fixture.routes[path]["content"] = content[:4] + "\n" + content[4:]
        self.assertEqual(self.client.candidate().version, VERSION)

    def test_read_stable_requires_exact_fixed_ref(self):
        self.assertEqual(self.client.read_stable(), SHA)
        self.fixture.routes[PREFIX + "/git/ref/heads/stable"]["ref"] = "refs/heads/main"
        with self.assertRaisesRegex(ValueError, "stable-unavailable"):
            self.client.read_stable()

    def test_stable_absence_or_transport_failure_never_falls_back(self):
        path = PREFIX + "/git/ref/heads/stable"
        for error in (RuntimeError("not-found"), RuntimeError("offline sensitive body"),
                      ValueError("sensitive decoder failure")):
            with self.subTest(error=str(error)):
                fixture = Fixture()
                fixture.routes[path] = error
                with self.assertRaisesRegex(RuntimeError, "release-unavailable") as caught:
                    PublicReleaseClient(fixture.request).candidate()
                self.assertNotIn("sensitive", str(caught.exception))
                self.assertEqual(fixture.paths, [path])

    def test_refuses_wrong_tag_target_or_asset_digest(self):
        mutations = (
            lambda f: f.routes[PREFIX + "/releases/tags/v" + VERSION].update(tag_name="v9.9.9"),
            lambda f: f.routes[PREFIX + "/git/ref/tags/v" + VERSION]["object"].update(sha=OLD_SHA),
            lambda f: f.routes[PREFIX + "/releases/tags/v" + VERSION].update(target_commitish=OLD_SHA),
            lambda f: f.routes[PREFIX + "/releases/42/assets?per_page=100&page=1"][0].update(digest="sha256:" + "0" * 64),
        )
        for mutate in mutations:
            fixture = Fixture()
            mutate(fixture)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                PublicReleaseClient(fixture.request).candidate()

    def test_refuses_prepared_draft_or_prerelease(self):
        def prepared(fixture):
            body = json.loads(fixture.routes[PREFIX + "/releases/tags/v" + VERSION]["body"])
            body["state"] = "prepared"
            fixture.routes[PREFIX + "/releases/tags/v" + VERSION]["body"] = json.dumps(body)

        mutations = (
            prepared,
            lambda f: f.routes[PREFIX + "/releases/tags/v" + VERSION].update(draft=True),
            lambda f: f.routes[PREFIX + "/releases/tags/v" + VERSION].update(prerelease=True),
        )
        for mutate in mutations:
            fixture = Fixture()
            mutate(fixture)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                PublicReleaseClient(fixture.request).candidate()

    def test_refuses_malformed_contents_or_release_json(self):
        contents = PREFIX + f"/contents/VERSION?ref={SHA}"
        release = PREFIX + "/releases/tags/v" + VERSION
        cases = (
            (contents, {"type": "file", "encoding": "utf-8", "size": 6, "content": VERSION}),
            (contents, {"type": "file", "encoding": "base64", "size": 6, "content": "%%%"}),
            (release, {**fixture_routes()[release], "body": "{"}),
        )
        for path, value in cases:
            fixture = Fixture()
            fixture.routes[path] = value
            with self.subTest(path=path, value=value), self.assertRaises(ValueError):
                PublicReleaseClient(fixture.request).candidate()

    def test_refuses_missing_or_fabricated_approval(self):
        release_path = PREFIX + "/releases/tags/v" + VERSION
        for mutation in (
            lambda body: body["record"].pop("approval"),
            lambda body: body["record"].update(approval={"approved": True}),
            lambda body: body["record"]["approval"].update(run_id=True),
            lambda body: body["finalization_approval"].update(state="pending"),
        ):
            fixture = Fixture()
            release = fixture.routes[release_path]
            body = json.loads(release["body"])
            mutation(body)
            release["body"] = json.dumps(body)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                PublicReleaseClient(fixture.request).candidate()

    def test_refuses_foreign_or_mismatched_evidence_urls(self):
        release_path = PREFIX + "/releases/tags/v" + VERSION
        for field, value in (
            ("run_url", "https://evil.test/actions/runs/991"),
            ("ci_url", f"https://github.com/{REPOSITORY}/actions/runs/999"),
        ):
            fixture = Fixture()
            release = fixture.routes[release_path]
            body = json.loads(release["body"])
            body["record"][field] = value
            release["body"] = json.dumps(body)
            with self.subTest(field=field), self.assertRaises(ValueError):
                PublicReleaseClient(fixture.request).candidate()

    def test_refuses_wrong_record_identity_and_nonpositive_or_bool_ids(self):
        release_path = PREFIX + "/releases/tags/v" + VERSION
        for field, value in (("repository", "attacker/fork"), ("schema_version", 2),
                             ("run_id", 0), ("ci_run_id", True)):
            fixture = Fixture()
            release = fixture.routes[release_path]
            body = json.loads(release["body"])
            body["record"][field] = value
            release["body"] = json.dumps(body)
            with self.subTest(field=field), self.assertRaises(ValueError):
                PublicReleaseClient(fixture.request).candidate()

    def test_asset_pagination_is_bounded_to_ten_pages(self):
        fixture = Fixture()
        first = PREFIX + "/releases/42/assets?per_page=100&page=1"
        fixture.routes[first] = [{}] * 100
        for page in range(2, 11):
            fixture.routes[PREFIX + f"/releases/42/assets?per_page=100&page={page}"] = [{}] * 100
        with self.assertRaisesRegex(ValueError, "pagination"):
            PublicReleaseClient(fixture.request).candidate()
        self.assertNotIn(PREFIX + "/releases/42/assets?per_page=100&page=11", fixture.paths)


class UpgradeTests(unittest.TestCase):
    def test_upgrade_decisions_are_fail_closed(self):
        candidate = Candidate("2.2.0", "b" * 40, {})
        self.assertTrue(check_upgrade(candidate, None))
        self.assertTrue(check_upgrade(candidate, {"version": "2.1.9", "sha": "a" * 40}))
        self.assertFalse(check_upgrade(candidate, {"version": "2.2.0", "sha": "b" * 40}))
        for installed in (
            {"version": "2.3.0", "sha": "a" * 40},
            {"version": "2.2.0", "sha": "a" * 40},
            {"version": "bad", "sha": "a" * 40},
            {"version": "2.2.0", "sha": "bad"},
        ):
            with self.subTest(installed=installed), self.assertRaises(ValueError):
                check_upgrade(candidate, installed)

    def test_same_version_changed_sha_is_refused(self):
        candidate = Candidate("2.2.0", "b" * 40, {})
        with self.assertRaises(ValueError):
            check_upgrade(candidate, {"version": "2.2.0", "sha": "a" * 40})


class PublicTransportTests(unittest.TestCase):
    class Response(io.BytesIO):
        code = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    class Opener:
        def __init__(self, results):
            self.results = iter(results)
            self.requests = []

        def open(self, request, timeout):
            self.requests.append((request, timeout))
            result = next(self.results)
            if isinstance(result, Exception):
                raise result
            return result

    def test_default_transport_is_anonymous_get_only_with_timeout_and_cap(self):
        from team_updater import release as module
        response = self.Response(b"{}")
        opener = self.Opener([response])
        with patch.object(module, "build_opener", return_value=opener):
            self.assertEqual(PublicReleaseClient().request(PREFIX + "/x"), {})
        request, timeout = opener.requests[0]
        self.assertEqual(request.full_url, "https://api.github.com" + PREFIX + "/x")
        self.assertEqual(request.method, "GET")
        self.assertEqual(timeout, 20)
        self.assertNotIn("Authorization", request.headers)

        opener = self.Opener([self.Response(b"x" * (1024 * 1024 + 1))])
        with patch.object(module, "build_opener", return_value=opener), self.assertRaisesRegex(RuntimeError, "release-unavailable"):
            PublicReleaseClient().request(PREFIX + "/x")

    def test_transport_retries_transient_failure_at_most_three_times_and_redacts(self):
        from team_updater import release as module
        error = URLError("Authorization: secret-material")
        opener = self.Opener([error, error, error])
        with patch.object(module, "build_opener", return_value=opener), patch.object(module.time, "sleep") as sleep, \
                self.assertRaisesRegex(RuntimeError, "release-unavailable") as caught:
            PublicReleaseClient().request(PREFIX + "/x")
        self.assertEqual(len(opener.requests), 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertNotIn("secret-material", str(caught.exception))

    def test_rate_limit_and_redirect_are_not_retried(self):
        from team_updater import release as module
        for status in (302, 403, 429):
            error = HTTPError("https://api.github.com/x", status, "sensitive", {}, io.BytesIO(b"secret"))
            opener = self.Opener([error])
            with self.subTest(status=status), patch.object(module, "build_opener", return_value=opener), \
                    patch.object(module.time, "sleep") as sleep, self.assertRaisesRegex(RuntimeError, "release-unavailable"):
                PublicReleaseClient().request(PREFIX + "/x")
            self.assertEqual(len(opener.requests), 1)
            sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
