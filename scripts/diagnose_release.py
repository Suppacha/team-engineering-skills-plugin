"""GET-only diagnostic for the failed v2.2.0 activation; never repairs state."""
import json
import os
import re
import sys

from release_github import GitHubClient, github_request
from release_writer import ReleaseWriter

REPOSITORY = "Suppacha/team-engineering-skills-plugin"
CANDIDATE = "390c967b6daadaab0719a75a35147cb26ff5866f"
PREFIX = "/repos/" + REPOSITORY
OUTPUT_KEYS = {"status", "tag_matches_candidate", "release_id", "draft", "prerelease",
               "target_commitish", "metadata", "asset_count"}
METADATA_ERRORS = {
    "invalid release ID": "invalid-id", "invalid release body": "invalid-body",
    "release body is not a publisher record": "body-not-json",
    "invalid release metadata": "invalid-metadata", "release identity mismatch": "identity-mismatch",
    "release approval provenance missing": "approval-missing",
    "release target differs from fixed candidate": "target-mismatch",
    "version tag differs from release": "tag-mismatch",
    "release publication state mismatch": "publication-mismatch",
}


def deny_write(*args, **kwargs):
    raise ValueError("diagnostic forbids writes")


def fixed_request(request):
    def get(method, path, body=None):
        suffix = path.removeprefix(PREFIX) if isinstance(path, str) and path.startswith(PREFIX) else ""
        allowed = suffix in ("/git/ref/tags/v2.2.0", "/git/matching-refs/tags/v2.2.0") or re.fullmatch(
            r"/releases(?:/[1-9][0-9]*/assets)?\?per_page=100(?:&page=[1-9][0-9]*)?", suffix)
        if method != "GET" or body is not None or not allowed:
            raise ValueError("diagnostic endpoint refused")
        return request(method, path)
    return get


def diagnose(request):
    result = dict(status="read-failed", tag_matches_candidate=None, release_id=None,
                  draft=None, prerelease=None, target_commitish="unknown", metadata="not-checked", asset_count=None)
    try:
        reader = GitHubClient(fixed_request(request), policy=dict(repository=REPOSITORY,
                              source_branch="main", channel="stable", verify_workflow=".github/workflows/verify.yml"))
        validator = ReleaseWriter(reader, deny_write)
        result["tag_matches_candidate"] = validator._tag_sha("v2.2.0") == CANDIDATE
        release = validator._release("v2.2.0")
        if release is None:
            # The draft is known to exist; a filtered list cannot prove absence.
            result["status"] = "release-not-visible"
            return result
        identity = release.get("id")
        if type(identity) is int and 0 < identity < 2**63:
            result["release_id"] = identity
        for key in ("draft", "prerelease"):
            result[key] = release.get(key) if type(release.get(key)) is bool else None
        target = release.get("target_commitish")
        result["target_commitish"] = "candidate" if target == CANDIDATE else "main" if target == "main" else "other"
        try:
            body = validator._metadata(release, "2.2.0")
            result["metadata"] = "valid" if body["record"]["candidate_sha"] == CANDIDATE else "candidate-mismatch"
        except (ValueError, RuntimeError) as error:
            result["metadata"] = METADATA_ERRORS.get(str(error), "validation-failed")
        if result["release_id"] is not None:
            assets = reader.get_pages(PREFIX + f"/releases/{identity}/assets?per_page=100")
            result["asset_count"] = len(assets)
        result["status"] = "observed"
    except Exception:
        # No raw server body, URL, token, exception text or traceback is output.
        pass
    return result


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    gate = {"GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ATTEMPT": "1"}
    if argv or any(os.environ.get(key) != value for key, value in gate.items()):
        print('{"status":"refused"}')
        return 1
    try:
        result = diagnose(github_request(os.environ.get("GH_DIAGNOSTIC_TOKEN", "")))
    except Exception:
        result = {"status": "read-failed"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
