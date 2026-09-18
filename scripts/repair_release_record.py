"""One-off, approved missing-asset repair; never promotes or edits a record."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, build_opener

from release_github import GitHubClient, github_request
from release_policy import check_approval, validate_sha
from release_writer import MAX_RECORD, NoRedirect, ReleaseWriter, encoded, require

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "Suppacha/team-engineering-skills-plugin"
PREFIX = "/repos/" + REPOSITORY
CANDIDATE = "390c967b6daadaab0719a75a35147cb26ff5866f"
RELEASE_ID, ORIGINAL_RUN, CI_RUN = 391171745, 35296621274, 35294455224
WORKFLOW = ".github/workflows/repair-release-record.yml"
TITLE = "Repair v2.2.0 release record"
ASSET_PATH = PREFIX + "/releases/391171745/assets?name=release-record.json"
BASELINE = "6ca868dbccba7d2e2f15dfd5cc6ac105980a8b13"


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None, "time lacks timezone")
    return result


def deny_write(*args, **kwargs):
    raise ValueError("publisher writes forbidden during repair")


def asset_uploader(token):
    """Only one possible write endpoint; no redirects, retries or response text."""
    require(isinstance(token, str) and token and not any(c in token for c in "\r\n"), "credential required")
    opener = build_opener(NoRedirect())
    used = False

    def upload(raw):
        nonlocal used
        require(not used and isinstance(raw, bytes) and 0 < len(raw) <= MAX_RECORD, "upload refused")
        used = True
        request = Request("https://uploads.github.com" + ASSET_PATH, data=raw, method="POST", headers={
            "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
            "Content-Type": "application/json", "Content-Length": str(len(raw)),
            "X-GitHub-Api-Version": "2026-03-10", "User-Agent": "team-plugin-record-repair"})
        try:
            with opener.open(request, timeout=20) as response:
                status = response.code
            return {"failure_class": "none" if status == 201 else "http",
                    "http_status": status if type(status) is int and 100 <= status <= 599 else None}
        except HTTPError as error:
            code = error.code
            try:
                error.close()
            except Exception:
                pass
            return {"failure_class": "http", "http_status": code if type(code) is int and 100 <= code <= 599 else None}
        except Exception:
            return {"failure_class": "transport", "http_status": None}
    return upload


def protection_environment(reader):
    """Explicit one-off check; normal promoter's approval collector is untouched."""
    policy = reader.policy
    require(policy.get("repository") == REPOSITORY and policy.get("environment") == "team-plugin-stable", "policy differs")
    reader._repository()
    path = PREFIX + "/environments/team-plugin-stable"
    env = reader.get_json(path)
    require(isinstance(env, dict) and env.get("name") == "team-plugin-stable"
            and type(env.get("id")) is int and env["id"] > 0, "environment differs")
    rules = env.get("protection_rules")
    require(isinstance(rules, list) and len(rules) == 2 and all(isinstance(r, dict) for r in rules)
            and {r.get("type") for r in rules} == {"required_reviewers", "branch_policy"}, "protection differs")
    mode = env.get("deployment_branch_policy")
    require(isinstance(mode, dict) and mode.get("protected_branches") is False
            and mode.get("custom_branch_policies") is True, "branch mode differs")
    branches = reader.get_pages(path + "/deployment-branch-policies?per_page=100")
    require(len(branches) == 1 and isinstance(branches[0], dict) and type(branches[0].get("id")) is int
            and branches[0]["id"] > 0 and branches[0].get("name") == "main" and branches[0].get("type") == "branch", "branch policy differs")
    rule = next(r for r in rules if r["type"] == "required_reviewers")
    reviewers = rule.get("reviewers")
    require(type(rule.get("prevent_self_review")) is bool and isinstance(reviewers, list) and len(reviewers) == 1
            and isinstance(reviewers[0], dict) and reviewers[0].get("type") == "User"
            and isinstance(reviewers[0].get("reviewer"), dict), "reviewer rule differs")
    reviewer = reviewers[0]["reviewer"]
    require(type(policy.get("reviewer_github_id")) is int and policy["reviewer_github_id"] > 0
            and reviewer.get("id") == policy["reviewer_github_id"]
            and reviewer.get("login") == policy.get("reviewer_login"), "reviewer differs")
    rules = reader.get_pages(PREFIX + "/rules/branches/stable?per_page=100")
    kinds = {"creation", "update", "deletion", "non_fast_forward"}
    require(bool(rules) and all(isinstance(r, dict) and r.get("type") in kinds
            and type(r.get("ruleset_id")) is int and r["ruleset_id"] > 0
            and r.get("ruleset_source_type") == "Repository" and r.get("ruleset_source") == REPOSITORY
            and (not r.get("parameters") or (r["type"] == "update" and r["parameters"] == {"update_allows_fetch_and_merge": False}))
            for r in rules) and {r["type"] for r in rules} == kinds, "stable protection differs")
    reader._admin(env, sorted({r["ruleset_id"] for r in rules}))
    return env


def review(reader, run_id, env, *, historical=False):
    reviews = reader.get_pages(PREFIX + f"/actions/runs/{run_id}/approvals")
    if historical and not reviews:
        return "recorded-not-live"
    matches = []
    for item in reviews:
        require(isinstance(item, dict) and isinstance(item.get("environments"), list)
                and isinstance(item.get("user"), dict) and item.get("state") in ("approved", "rejected"), "unknown review")
        for target in item["environments"]:
            require(isinstance(target, dict), "unknown review environment")
            if target.get("id") == env["id"]:
                require(target.get("name") == env["name"], "review environment differs")
                matches.append(item)
    require(len(matches) == 1 and matches[0]["state"] == "approved", "approval absent or ambiguous")
    require(matches[0]["user"].get("id") == reader.policy["reviewer_github_id"]
            and matches[0]["user"].get("login") == reader.policy["reviewer_login"], "approval reviewer differs")
    return "live-matched"


def fresh_approval(reader, run_id, head_sha):
    require(type(run_id) is int and run_id > 0 and run_id != ORIGINAL_RUN, "fresh run required")
    validate_sha(head_sha)
    workflow = reader._workflow(WORKFLOW)
    path = PREFIX + f"/actions/runs/{run_id}"
    run = reader.get_json(path)
    reader._run_identity(run, workflow, WORKFLOW, "workflow_dispatch")
    require(run["id"] == run_id and run["run_attempt"] == 1 and run["head_sha"] == head_sha
            and run.get("display_title") == TITLE and run.get("status") == "in_progress", "repair run differs")
    env = protection_environment(reader)
    review(reader, run_id, env)
    require(reader.get_json(path) == run, "repair run changed")
    return env


def historical_provenance(reader, record, env):
    expected = dict(schema_version=1, repository=REPOSITORY, version="2.2.0", candidate_sha=CANDIDATE,
                    previous_stable_sha=None, baseline_sha=BASELINE, baseline_version="2.1.0", run_id=ORIGINAL_RUN,
                    run_url=f"https://github.com/{REPOSITORY}/actions/runs/{ORIGINAL_RUN}", ci_run_id=CI_RUN,
                    ci_url=f"https://github.com/{REPOSITORY}/actions/runs/{CI_RUN}")
    require(set(record) == set(expected) | {"approval"} and all(record.get(k) == v for k, v in expected.items()), "record differs")
    evidence = record["approval"]
    fields = {"repository", "run_id", "candidate_sha", "environment_id", "environment_name", "reviewer_github_id",
              "reviewer_login", "state", "observed_at", "url", "binding", "admin_evidence_reference"}
    require(isinstance(evidence, dict) and set(evidence) == fields and not check_approval(evidence, reader.policy, ORIGINAL_RUN, CANDIDATE), "recorded approval differs")
    require(evidence["environment_id"] == env["id"] and evidence["url"] == expected["run_url"]
            and evidence["binding"] == "trusted-run-name-first-attempt"
            and evidence["admin_evidence_reference"] == reader.admin_evidence["evidence_reference"], "recorded binding differs")
    workflow = reader._workflow(".github/workflows/promote.yml")
    path = PREFIX + f"/actions/runs/{ORIGINAL_RUN}/attempts/1"
    run = reader.get_json(path)
    reader._run_identity(run, workflow, ".github/workflows/promote.yml", "workflow_dispatch")
    require(run["id"] == ORIGINAL_RUN and run["run_attempt"] == 1 and run["head_sha"] == CANDIDATE
            and run.get("display_title") == "Promote " + CANDIDATE and run.get("status") == "completed"
            and run.get("conclusion") == "failure", "original attempt differs")
    observed = timestamp(evidence["observed_at"])
    require(timestamp(run["run_started_at"]) <= observed <= timestamp(run["updated_at"]) <= datetime.now(timezone.utc), "original timing differs")
    jobs = reader.get_pages(path + "/jobs?per_page=100")
    require(len(jobs) == 2 and all(isinstance(j, dict) and j.get("run_id") == ORIGINAL_RUN
            and j.get("head_sha") == CANDIDATE and j.get("run_attempt", 1) == 1 and j.get("status") == "completed"
            for j in jobs), "original jobs differ")
    by_name = {j.get("name"): j for j in jobs}
    require(set(by_name) == {"preflight", "publish"} and by_name["preflight"].get("conclusion") == "success"
            and by_name["publish"].get("conclusion") == "failure", "original execution differs")
    preflight, publish = by_name["preflight"], by_name["publish"]
    require(preflight.get("id") == 105450373603 and publish.get("id") == 105450687760
            and timestamp(run["run_started_at"]) <= timestamp(preflight["started_at"])
            <= timestamp(preflight["completed_at"]) <= timestamp(publish["started_at"])
            <= observed <= timestamp(publish["completed_at"]) <= timestamp(run["updated_at"]), "original job timing differs")
    steps = publish.get("steps")
    require(isinstance(steps, list) and all(isinstance(s, dict) for s in steps), "original steps unavailable")
    for name, conclusion in {
        "Run actions/create-github-app-token@fee1f7d63c2ff003460e3d139729b119787bc349": "success",
        "Revalidate live evidence and publish without candidate execution": "failure",
    }.items():
        matches = [step for step in steps if step.get("name") == name]
        require(len(matches) == 1 and matches[0].get("status") == "completed"
                and matches[0].get("conclusion") == conclusion, "original step differs")
    mode = review(reader, ORIGINAL_RUN, env, historical=True)
    require(reader.get_json(path) == run, "original attempt changed")
    ci = reader._ci(CANDIDATE)
    require(ci["run_id"] == CI_RUN and ci["status"] == "completed" and ci["conclusion"] == "success"
            and all(ci["jobs"].get("package (" + system + ")") == "success"
                    for system in ("windows-latest", "macos-latest", "ubuntu-latest")), "original CI differs")
    return mode


def snapshot(validator):
    release = validator._release("v2.2.0")
    require(isinstance(release, dict) and release.get("id") == RELEASE_ID and release.get("draft") is True, "fixed draft absent")
    body = validator._metadata(release, "2.2.0")
    require(set(body) == {"state", "record"} and body["state"] == "prepared"
            and body["record"].get("candidate_sha") == CANDIDATE, "prepared record differs")
    return release, body["record"]


def repair(reader, upload, run_id, head_sha):
    result = dict(status="refused", failure_class="validation", http_status=None, historical_review="not-checked", stage="fresh-approval")
    try:
        env = fresh_approval(reader, run_id, head_sha)
        validator = ReleaseWriter(reader, deny_write)
        result["stage"] = "draft"
        release, record = snapshot(validator)
        result["stage"] = "historical"
        result["historical_review"] = historical_provenance(reader, record, env)
        require(reader.read_stable() is None, "stable must remain absent")
        # Repeat approval/protections, then immutable inputs and assets immediately before the only write.
        result["stage"] = "recheck"
        require(fresh_approval(reader, run_id, head_sha) == env, "environment changed")
        again, saved = snapshot(validator)
        keys = ("id", "tag_name", "target_commitish", "draft", "prerelease", "body")
        require(all(again.get(k) == release.get(k) for k in keys) and saved == record, "draft changed")
        require(reader.read_stable() is None, "stable moved")
        if validator._asset_matches(again, saved):
            result.update(status="already-matching", failure_class="none")
            return result
        raw = encoded(saved)
        result.update(status="unconfirmed", failure_class="transport", stage="upload")
        try:
            outcome = upload(raw)
            if isinstance(outcome, dict) and outcome.get("failure_class") in ("none", "http", "transport"):
                result["failure_class"] = outcome["failure_class"]
                code = outcome.get("http_status")
                result["http_status"] = code if type(code) is int and 100 <= code <= 599 else None
        except Exception:
            pass  # Readback after every uncertain outcome; never invoke upload again.
        result["stage"] = "readback"
        after, saved = snapshot(validator)
        require(all(after.get(k) == release.get(k) for k in keys) and saved == record, "draft changed after write")
        require(validator._asset_matches(after, saved) and reader.read_stable() is None, "repair unconfirmed")
        result["status"] = "repaired"
    except Exception:
        pass  # Exceptions may contain tokens/server bodies. Only the fixed result is exposed.
    return result


def main(argv=None):
    result = {"status": "refused", "failure_class": "validation", "http_status": None, "historical_review": "not-checked", "stage": "context"}
    try:
        args = sys.argv[1:] if argv is None else argv
        require(not args and all(os.environ.get(k) == v for k, v in {
            "GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ATTEMPT": "1"}.items()), "workflow context refused")
        run_id = int(os.environ["GITHUB_RUN_ID"])
        head_sha = validate_sha(os.environ["GITHUB_SHA"])
        policy = json.loads((ROOT / "config/release-policy.json").read_text(encoding="utf-8"))
        policy["reviewer_github_id"] = int(os.environ["RELEASE_REVIEWER_ID"])
        policy["writer_app_id"] = int(os.environ["RELEASE_WRITER_APP_ID"])
        require(policy.get("repository") == REPOSITORY, "repository differs")
        token = os.environ["GH_REPAIR_TOKEN"]
        reader = GitHubClient(github_request(token), policy=policy, admin_evidence=json.loads(os.environ["RELEASE_ADMIN_EVIDENCE"]))
        result = repair(reader, asset_uploader(token), run_id, head_sha)
    except Exception:
        pass
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in ("repaired", "already-matching") else 1


if __name__ == "__main__":
    raise SystemExit(main())
