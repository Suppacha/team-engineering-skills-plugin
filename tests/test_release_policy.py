from pathlib import Path
import copy
import json
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from release_policy import check_approval, check_candidate, validate_sha, version_tuple


SHA = "a" * 40
CANDIDATE = {
    "sha": SHA,
    "on_main": True,
    "version": "2.2.0",
    "valid_package": True,
    "skills": {"test-case-design": {"version": "1.0.0", "hash": "1" * 64}},
}
BASELINE = {"sha": "b" * 40, "version": "2.1.0", "skills": CANDIDATE["skills"]}
CI = {
    "sha": SHA,
    "event": "push",
    "branch": "main",
    "workflow": ".github/workflows/verify.yml",
    "status": "completed",
    "conclusion": "success",
    "attempt": 1,
    "jobs": {
        f"package ({os})": "success"
        for os in ("windows-latest", "macos-latest", "ubuntu-latest")
    },
}
POLICY = {
    "repository": "Suppacha/team-engineering-skills-plugin",
    "source_branch": "main",
    "verify_workflow": ".github/workflows/verify.yml",
    "environment": "team-plugin-stable",
    "reviewer_login": "Suppacha",
    "reviewer_github_id": 12345,
}
APPROVAL = {
    "repository": POLICY["repository"],
    "run_id": 991,
    "candidate_sha": SHA,
    "environment_id": 77,
    "environment_name": POLICY["environment"],
    "reviewer_github_id": POLICY["reviewer_github_id"],
    "reviewer_login": POLICY["reviewer_login"],
    "state": "approved",
}


class ReleasePolicyTests(unittest.TestCase):
    def test_accept_exact_evidence(self):
        self.assertEqual(check_candidate(CANDIDATE, BASELINE, CI), [])

    def test_reject_pending_windows(self):
        ci = {**CI, "jobs": {**CI["jobs"], "package (windows-latest)": "pending"}}
        self.assertTrue(check_candidate(CANDIDATE, BASELINE, ci))

    def test_sha_and_version_parsers_are_narrow(self):
        self.assertEqual(validate_sha(SHA), SHA)
        self.assertEqual(version_tuple("10.2.0"), (10, 2, 0))
        for value in ("A" * 40, "a" * 39, "g" * 40, "refs/heads/main"):
            with self.subTest(sha=value), self.assertRaises(ValueError):
                validate_sha(value)
        for value in ("1.2", "1.2.3-rc1", "01.2.3", "1.-2.3", "1.2.03"):
            with self.subTest(version=value), self.assertRaises(ValueError):
                version_tuple(value)

    def test_candidate_rejection_table(self):
        cases = {
            "candidate malformed SHA": ({**CANDIDATE, "sha": "bad"}, BASELINE, CI),
            "baseline malformed SHA": (CANDIDATE, {**BASELINE, "sha": "bad"}, CI),
            "not on main": ({**CANDIDATE, "on_main": False}, BASELINE, CI),
            "CI another SHA": (CANDIDATE, BASELINE, {**CI, "sha": "c" * 40}),
            "wrong event": (CANDIDATE, BASELINE, {**CI, "event": "pull_request"}),
            "wrong branch": (CANDIDATE, BASELINE, {**CI, "branch": "stable"}),
            "wrong workflow": (CANDIDATE, BASELINE, {**CI, "workflow": "verify.yml"}),
            "missing job": (CANDIDATE, BASELINE, {**CI, "jobs": dict(list(CI["jobs"].items())[1:])}),
            "extra duplicate-like job": (CANDIDATE, BASELINE, {**CI, "jobs": {**CI["jobs"], "package (ubuntu-latest) #2": "success"}}),
            "rerun not finished": (CANDIDATE, BASELINE, {**CI, "status": "in_progress", "attempt": 2}),
            "cancelled": (CANDIDATE, BASELINE, {**CI, "conclusion": "cancelled"}),
            "skipped job": (CANDIDATE, BASELINE, {**CI, "jobs": {**CI["jobs"], "package (macos-latest)": "skipped"}}),
            "failed job": (CANDIDATE, BASELINE, {**CI, "jobs": {**CI["jobs"], "package (ubuntu-latest)": "failure"}}),
            "equal version": ({**CANDIDATE, "version": "2.1.0"}, BASELINE, CI),
            "lower version": ({**CANDIDATE, "version": "2.0.9"}, BASELINE, CI),
            "invalid package": ({**CANDIDATE, "valid_package": False}, BASELINE, CI),
        }
        for label, args in cases.items():
            with self.subTest(label):
                self.assertTrue(check_candidate(*args))

    def test_missing_or_invalid_baseline_rejects(self):
        for baseline in (None, {}, {**BASELINE, "version": "0.0.0"}):
            with self.subTest(baseline=baseline):
                self.assertTrue(check_candidate(CANDIDATE, baseline, CI))

    def test_skill_payload_change_requires_version_bump(self):
        candidate = copy.deepcopy(CANDIDATE)
        candidate["skills"]["test-case-design"]["hash"] = "2" * 64
        self.assertTrue(check_candidate(candidate, BASELINE, CI))
        candidate["skills"]["test-case-design"]["version"] = "1.0.1"
        self.assertEqual(check_candidate(candidate, BASELINE, CI), [])

    def test_added_skill_requires_version_hash_and_provenance(self):
        for added in (
            {"version": "1.0.0", "hash": "2" * 64},
            {"version": "1.0.0", "hash": "bad", "provenance": "team-owned"},
            {"version": "01.0.0", "hash": "2" * 64, "provenance": "team-owned"},
        ):
            candidate = copy.deepcopy(CANDIDATE)
            candidate["skills"]["new-skill"] = added
            with self.subTest(added=added):
                self.assertTrue(check_candidate(candidate, BASELINE, CI))
        candidate = copy.deepcopy(CANDIDATE)
        candidate["skills"]["new-skill"] = {
            "version": "1.0.0", "hash": "2" * 64, "provenance": "team-owned"
        }
        self.assertEqual(check_candidate(candidate, BASELINE, CI), [])

    def test_removed_skill_requires_notes_and_explicit_release_review(self):
        baseline = copy.deepcopy(BASELINE)
        baseline["skills"]["removed-skill"] = {"version": "1.0.0", "hash": "3" * 64}
        self.assertTrue(check_candidate(CANDIDATE, baseline, CI))
        candidate = {**CANDIDATE, "release_notes": "Remove obsolete skill", "release_review": True}
        self.assertEqual(check_candidate(candidate, baseline, CI), [])

    def test_baseline_skill_metadata_must_be_valid_even_when_removed(self):
        baseline = copy.deepcopy(BASELINE)
        baseline["skills"]["removed-skill"] = {"version": "bad", "hash": "3" * 64}
        candidate = {**CANDIDATE, "release_notes": "Remove obsolete skill", "release_review": True}
        self.assertTrue(check_candidate(candidate, baseline, CI))

    def test_skill_version_cannot_decrease_when_payload_is_unchanged(self):
        candidate = copy.deepcopy(CANDIDATE)
        candidate["skills"]["test-case-design"]["version"] = "0.9.0"
        self.assertTrue(check_candidate(candidate, BASELINE, CI))

    def test_accept_exact_normalized_approval(self):
        self.assertEqual(check_approval(APPROVAL, POLICY, 991, SHA), [])

    def test_approval_rejection_table(self):
        cases = {
            "arbitrary boolean": {"approved": True},
            "wrong repository": {**APPROVAL, "repository": "attacker/fork"},
            "wrong run": {**APPROVAL, "run_id": 992},
            "wrong candidate": {**APPROVAL, "candidate_sha": "c" * 40},
            "missing environment id": {k: v for k, v in APPROVAL.items() if k != "environment_id"},
            "wrong environment": {**APPROVAL, "environment_name": "production"},
            "wrong reviewer id": {**APPROVAL, "reviewer_github_id": 999},
            "wrong reviewer login": {**APPROVAL, "reviewer_login": "suppacha"},
            "pending state": {**APPROVAL, "state": "pending"},
        }
        for label, evidence in cases.items():
            with self.subTest(label):
                self.assertTrue(check_approval(evidence, POLICY, 991, SHA))

    def test_unresolved_policy_reviewer_never_approves(self):
        self.assertTrue(check_approval(APPROVAL, {**POLICY, "reviewer_github_id": None}, 991, SHA))

    def test_policy_file_has_public_activation_contract_only(self):
        policy = json.loads((ROOT / "config" / "release-policy.json").read_text())
        self.assertEqual(policy["schema_version"], 1)
        self.assertEqual(policy["repository"], "Suppacha/team-engineering-skills-plugin")
        self.assertEqual(policy["plugin_name"], "team-engineering-skills")
        self.assertEqual(policy["marketplace_name"], "team-engineering-skills-marketplace")
        self.assertEqual(policy["source_branch"], "main")
        self.assertEqual(policy["channel"], "stable")
        self.assertEqual(policy["environment"], "team-plugin-stable")
        self.assertEqual(policy["reviewer_login"], "Suppacha")
        self.assertIsNone(policy["reviewer_github_id"])
        self.assertFalse(any("token" in key.lower() or "secret" in key.lower() for key in policy))


if __name__ == "__main__":
    unittest.main()
