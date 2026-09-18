"""Pure, fail-closed policy checks for stable-channel release evidence.

``check_approval`` accepts only normalized evidence produced from GitHub's
environment and deployment-review APIs.  Its contract is a mapping with:

* ``repository``: exact ``owner/name`` repository identity;
* ``run_id``: positive integer ID of the current promotion workflow run;
* ``candidate_sha``: the immutable, full candidate commit SHA;
* ``environment_id`` and ``environment_name``: positive GitHub environment ID
  and the policy's exact protected environment name;
* ``reviewer_github_id`` and ``reviewer_login``: the approved reviewer's
  numeric GitHub account ID and configured login; and
* ``state``: exactly ``"approved"``.

Task 2 is responsible for deriving that shape from fresh GitHub responses.
No caller-supplied boolean (including ``approved: true``), chat approval, or
unresolved reviewer login grants publication authority.

Likewise, ``candidate["valid_package"]`` is normalized evidence rather than
an independent integrity check performed here.  Before setting it to true,
Task 2 must extract the exact-SHA package as bounded data and invoke the
trusted workflow checkout's ``framework.validate_release(Path)``.  This pure
module intentionally accepts no package path and executes no candidate code.
"""

import re
from typing import Any


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_JOBS = {
    "package (windows-latest)",
    "package (macos-latest)",
    "package (ubuntu-latest)",
}
VERIFY_WORKFLOW = ".github/workflows/verify.yml"
INITIAL_BASELINE_VERSION = (2, 1, 0)


def validate_sha(value: str) -> str:
    """Return a canonical full SHA or raise ``ValueError``."""
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise ValueError("SHA must be exactly 40 lowercase hexadecimal characters")
    return value


def version_tuple(value: str) -> tuple[int, int, int]:
    """Parse the stable three-component version format used by releases."""
    if not isinstance(value, str):
        raise ValueError("version must be a string")
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ValueError("version must be stable SemVer with three components and no leading zeros")
    return tuple(int(component) for component in match.groups())


def jobs_pass(jobs: Any) -> bool:
    return (
        isinstance(jobs, dict)
        and set(jobs) == REQUIRED_JOBS
        and all(value == "success" for value in jobs.values())
    )


def _mapping(value: Any, label: str, errors: list[str]) -> dict:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    return value


def _valid_skill(skill: Any) -> bool:
    if not isinstance(skill, dict):
        return False
    try:
        version_tuple(skill.get("version"))
    except ValueError:
        return False
    return isinstance(skill.get("hash"), str) and HASH_RE.fullmatch(skill["hash"]) is not None


def check_candidate(candidate: dict, baseline: dict, ci: dict) -> list[str]:
    """Check normalized evidence; package integrity is established upstream."""
    errors: list[str] = []
    candidate = _mapping(candidate, "candidate", errors)
    baseline = _mapping(baseline, "baseline", errors)
    ci = _mapping(ci, "CI evidence", errors)

    try:
        candidate_sha = validate_sha(candidate.get("sha"))
    except ValueError as error:
        candidate_sha = None
        errors.append(f"candidate {error}")
    try:
        validate_sha(baseline.get("sha"))
    except ValueError as error:
        errors.append(f"baseline {error}")
    try:
        baseline_version = version_tuple(baseline.get("version"))
        if baseline_version < INITIAL_BASELINE_VERSION:
            errors.append("baseline predates the reviewed 2.1.0 release contract")
    except ValueError as error:
        baseline_version = None
        errors.append(f"baseline {error}")
    try:
        candidate_version = version_tuple(candidate.get("version"))
    except ValueError as error:
        candidate_version = None
        errors.append(f"candidate {error}")

    if candidate_version is not None and baseline_version is not None and candidate_version <= baseline_version:
        errors.append("candidate version must be greater than baseline version")
    if candidate.get("on_main") is not True:
        errors.append("candidate must be proven reachable from main")
    if candidate.get("valid_package") is not True:
        errors.append("candidate package validation must pass")

    try:
        ci_sha = validate_sha(ci.get("sha"))
    except ValueError as error:
        ci_sha = None
        errors.append(f"CI {error}")
    if candidate_sha is not None and ci_sha != candidate_sha:
        errors.append("CI SHA does not match candidate SHA")
    expected_ci = {
        "event": "push",
        "branch": "main",
        "workflow": VERIFY_WORKFLOW,
        "status": "completed",
        "conclusion": "success",
    }
    for field, expected in expected_ci.items():
        if ci.get(field) != expected:
            errors.append(f"CI {field} must equal {expected!r}")
    attempt = ci.get("attempt")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        errors.append("CI attempt must be a positive integer")
    if not jobs_pass(ci.get("jobs")):
        errors.append("CI jobs must be the exact successful three-platform package matrix")

    candidate_skills = _mapping(candidate.get("skills"), "candidate skills", errors)
    baseline_skills = _mapping(baseline.get("skills"), "baseline skills", errors)
    for name, skill in baseline_skills.items():
        if not isinstance(name, str) or not name or not _valid_skill(skill):
            errors.append(f"baseline skill {name!r} needs a valid version and payload hash")
    for name, skill in candidate_skills.items():
        if not isinstance(name, str) or not name:
            errors.append("candidate skill names must be non-empty strings")
            continue
        if not _valid_skill(skill):
            errors.append(f"candidate skill {name!r} needs a valid version and payload hash")
            continue
        previous = baseline_skills.get(name)
        if previous is None:
            provenance = skill.get("provenance")
            if not isinstance(provenance, str) or not provenance.strip():
                errors.append(f"added skill {name!r} requires provenance")
        elif not _valid_skill(previous):
            errors.append(f"baseline skill {name!r} is invalid")
        else:
            skill_version = version_tuple(skill["version"])
            previous_version = version_tuple(previous["version"])
            if skill_version < previous_version:
                errors.append(f"skill {name!r} version cannot decrease")
            elif skill["hash"] != previous["hash"] and skill_version <= previous_version:
                errors.append(f"changed skill {name!r} requires an increased version")

    removed = set(baseline_skills) - set(candidate_skills)
    if removed:
        notes = candidate.get("release_notes")
        if not isinstance(notes, str) or not notes.strip():
            errors.append("removed skills require release notes")
        if candidate.get("release_review") is not True:
            errors.append("removed skills require explicit release review")
    return errors


def check_approval(evidence: dict, policy: dict, run_id: int, candidate_sha: str) -> list[str]:
    """Validate normalized, identity-bound GitHub release approval evidence."""
    errors: list[str] = []
    evidence = _mapping(evidence, "approval evidence", errors)
    policy = _mapping(policy, "release policy", errors)
    try:
        expected_sha = validate_sha(candidate_sha)
    except ValueError as error:
        expected_sha = None
        errors.append(f"expected candidate {error}")
    if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id < 1:
        errors.append("expected run ID must be a positive integer")

    required_policy = ("repository", "environment", "reviewer_login", "reviewer_github_id")
    for field in required_policy:
        if field not in policy:
            errors.append(f"policy is missing {field}")
    reviewer_id = policy.get("reviewer_github_id")
    if isinstance(reviewer_id, bool) or not isinstance(reviewer_id, int) or reviewer_id < 1:
        errors.append("policy reviewer GitHub ID must be resolved at activation")

    expected = {
        "repository": policy.get("repository"),
        "run_id": run_id,
        "candidate_sha": expected_sha,
        "environment_name": policy.get("environment"),
        "reviewer_github_id": reviewer_id,
        "reviewer_login": policy.get("reviewer_login"),
        "state": "approved",
    }
    for field, value in expected.items():
        if field not in evidence:
            errors.append(f"approval evidence is missing {field}")
        elif evidence[field] != value:
            errors.append(f"approval evidence {field} does not match policy context")
    environment_id = evidence.get("environment_id")
    if isinstance(environment_id, bool) or not isinstance(environment_id, int) or environment_id < 1:
        errors.append("approval evidence requires a positive environment ID")
    return errors
