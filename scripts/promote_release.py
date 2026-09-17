"""Trusted, stdlib-only stable publisher. Candidate trees are data, never code.

GitHub refs are NOT compare-and-swap. Workflow concurrency, the Admin-reviewed
sole writer restriction, and an immediate stable read are required together.
"""
import argparse
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from release_github import GitHubClient, github_request
from release_policy import check_candidate, validate_sha

ROOT = Path(__file__).resolve().parents[1]
# Real reviewed 2.1.0 package, never a fabricated 0.0.0 baseline.
INITIAL_BASELINE = "6ca868dbccba7d2e2f15dfd5cc6ac105980a8b13"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def matching(saved, fresh):
    if saved is None:
        return False
    require(isinstance(saved, dict) and saved.get("state") in ("prepared", "recorded")
            and isinstance(saved.get("record"), dict), "invalid persisted release record")
    for key in ("schema_version", "repository", "version", "candidate_sha", "previous_stable_sha"):
        require(saved["record"].get(key) == fresh.get(key), "conflicting release record: " + key)
    return True


def partial(state):
    return {"state": state, "partial_failure": True,
            "repair": "Inspect the remote stable ref, version tag, draft release and JSON asset. "
                      "Do not force, delete, or blindly retry writes. After resolving incomplete "
                      "records, use a fresh dispatch for the same candidate and approve again; "
                      "a matching promoted candidate can finalize without moving stable."}


def publish_release(client, record):
    """Recollect evidence; input authorizes no action beyond its three selectors."""
    candidate = validate_sha(record.get("candidate_sha"))
    previous = record.get("previous_stable_sha")
    if previous is not None:
        validate_sha(previous)
    run_id = record.get("run_id")
    require(type(run_id) is int and run_id > 0, "positive run ID required")
    stable = client.read_stable()
    require(stable in (previous, candidate), "stable moved; fresh dispatch required")
    fresh = client.revalidate(candidate, previous, run_id)
    saved = client.read_record(fresh["version"])
    exists = matching(saved, fresh)
    require(stable != candidate or exists, "stable already candidate without matching prepared record")
    require(not exists or saved["state"] != "recorded" or stable == candidate,
            "published record exists but stable differs")
    if not exists:
        try:
            client.prepare_record(fresh)
        except (RuntimeError, ValueError, OSError):
            pass  # Any uncertain write is reconciled by readback, never retried.
        try:
            saved = client.read_record(fresh["version"])
            if not matching(saved, fresh):
                return partial("unprepared")
        except (RuntimeError, ValueError, OSError):
            return partial("unprepared")
    durable = saved["record"]
    state = "promoted" if stable == candidate else "prepared"
    try:
        # Includes approval, visible protections, Admin evidence, ancestry and CI.
        newest = client.revalidate(candidate, previous, run_id)
        matching(saved, newest)
        stable = client.read_stable()  # Last remote operation before ref mutation.
        require(stable in (previous, candidate), "stable moved before write")
        if stable != candidate:
            try:
                if previous is None:
                    client.create_stable(candidate)
                else:
                    client.update_stable(candidate, force=False)
            except (RuntimeError, ValueError, OSError):
                pass
            require(client.read_stable() == candidate, "stable write not confirmed")
        state = "promoted"
        if saved["state"] != "recorded":
            # Revalidate again before publishing metadata, including recovery.
            newest = client.revalidate(candidate, previous, run_id)
            require(client.read_stable() == candidate, "stable changed before finalization")
            try:
                client.finalize_record(durable, newest["approval"])
            except (RuntimeError, ValueError, OSError):
                pass
        final = client.read_record(fresh["version"])
        require(matching(final, fresh) and final["state"] == "recorded", "final record not confirmed")
        require(client.read_stable() == candidate, "stable changed after finalization")
        return {"state": "recorded", "partial_failure": False, "candidate_sha": candidate,
                "version": fresh["version"]}
    except (RuntimeError, ValueError, OSError):
        return partial(state)


def candidate_evidence(reader, candidate, previous):
    data = reader.collect_candidate(candidate, previous or INITIAL_BASELINE)
    if previous is None:
        require(data["baseline"]["version"] == "2.1.0", "initial reviewed baseline is not 2.1.0")
    errors = check_candidate(data["candidate"], data["baseline"], data["ci"])
    require(not errors, "candidate policy rejected: " + "; ".join(errors))
    return data


class PromotionClient:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer

    def read_stable(self):
        return self.reader.read_stable()

    def revalidate(self, candidate, previous, run_id):
        data = candidate_evidence(self.reader, candidate, previous)
        approval = self.reader.collect_approval(run_id, candidate)
        return {"schema_version": 1, "repository": self.reader.policy["repository"],
                "version": data["candidate"]["version"], "candidate_sha": candidate,
                "previous_stable_sha": previous, "baseline_sha": data["baseline"]["sha"],
                "baseline_version": data["baseline"]["version"], "run_id": run_id,
                "run_url": approval["url"], "ci_run_id": data["ci"]["run_id"],
                "ci_url": data["ci"]["url"], "approval": approval}

    def read_record(self, version):
        return self.writer.read_record(version)

    def prepare_record(self, record):
        self.writer.prepare_record(record)

    def finalize_record(self, record, approval):
        self.writer.finalize_record(record, approval)

    def create_stable(self, candidate):
        self.writer.create_stable(candidate)

    def update_stable(self, candidate, *, force):
        self.writer.update_stable(candidate, force=force)


def preflight(reader, candidate):
    """No protected-environment config or writer credential is available here."""
    validate_sha(candidate)
    stable = reader.read_stable()
    # Recovery after ref movement must still use the original baseline. Public
    # release metadata may be a draft and is not readable by preflight's token;
    # use the reviewed baseline for eligibility, resolve exact prior SHA later.
    previous = None if stable == candidate else stable
    data = candidate_evidence(reader, candidate, previous)
    require(reader.read_stable() == stable, "stable changed during preflight")
    return {"schema_version": 1, "candidate_sha": candidate,
            "expected_stable": stable or "ABSENT", "version": data["candidate"]["version"],
            "ci_url": data["ci"]["url"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--candidate", required=True, type=validate_sha)
    pre.add_argument("--output", required=True, type=Path)
    pub = sub.add_parser("publish")
    pub.add_argument("--candidate", required=True, type=validate_sha)
    pub.add_argument("--expected-stable", required=True)
    pub.add_argument("--run-id", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            reader = GitHubClient(github_request(os.environ.get("GH_READ_TOKEN")))
            result = preflight(reader, args.candidate)
            args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                    output.write("expected_stable=" + result["expected_stable"] + "\n")
        else:
            require(os.environ.get("GITHUB_REF") == "refs/heads/main"
                    and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
                    and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
                    and os.environ.get("GITHUB_RUN_ID") == str(args.run_id),
                    "publication requires first-attempt trusted main dispatch")
            previous = None if args.expected_stable == "ABSENT" else validate_sha(args.expected_stable)
            policy = json.loads((ROOT / "config/release-policy.json").read_text())
            policy["reviewer_github_id"] = int(os.environ["RELEASE_REVIEWER_ID"])
            policy["writer_app_id"] = int(os.environ["RELEASE_WRITER_APP_ID"])
            require(os.environ.get("GITHUB_REPOSITORY") == policy["repository"], "repository mismatch")
            admin = json.loads(os.environ["RELEASE_ADMIN_EVIDENCE"])
            token = os.environ["GH_WRITER_TOKEN"]
            reader = GitHubClient(github_request(token), policy=policy, admin_evidence=admin)
            from release_writer import ReleaseWriter, writer_request
            writer = ReleaseWriter(reader, writer_request(token, policy["repository"]))
            require(reader.read_stable() == previous, "stable moved since preflight approval request")
            if previous == args.candidate:
                # Only the durable, same-candidate record supplies a recovery
                # baseline; dispatch input cannot substitute a different one.
                version = reader._package(args.candidate)["version"]
                saved = writer.read_record(version)
                require(saved is not None and saved["record"]["candidate_sha"] == args.candidate,
                        "recovery needs matching durable release record")
                previous = saved["record"]["previous_stable_sha"]
            result = publish_release(PromotionClient(reader, writer), {
                "candidate_sha": args.candidate, "previous_stable_sha": previous, "run_id": args.run_id})
        print(json.dumps(result, sort_keys=True))
        return 1 if result.get("partial_failure") else 0
    except (ValueError, RuntimeError, KeyError, OSError):
        # Do not print exception payloads: transports/config may carry secrets.
        print("Release refused: evidence/configuration unavailable or inconsistent; inspect trusted run diagnostics.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
