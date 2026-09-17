"""Read-only, fail-closed GitHub evidence collection from a trusted checkout.

``request`` is an authenticated transport, never credentials from candidate JSON.
``policy`` and ``admin_evidence`` must come from trusted workflow/protected
environment configuration, not PR files or dispatch inputs. Admin evidence is a
human attestation, NOT proof that REST exposes every bypass setting. Re-attest
after permissions/rules change. Default configuration cannot authorize release.
No candidate Python, shell, workflow or plugin script is imported or executed.
"""
import base64
import binascii
from datetime import datetime, timezone
import fnmatch
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from release_files import CATALOGS, DENIED_NAMES, DENIED_PARTS
from release_policy import check_approval, validate_sha

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = "plugins/team-engineering-skills"
MAX_BODY = 8 * 1024 * 1024
MAX_PACKAGE = 64 * 1024 * 1024
MAX_FILES = 10000
MAX_PAGES = 20
PROMOTE_WORKFLOW = ".github/workflows/promote.yml"


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _positive(value):
    return type(value) is int and value > 0


def _api_path(path):
    _require(isinstance(path, str) and path.startswith("/") and not path.startswith("//")
             and not any(c in path for c in "\\\r\n\t#")
             and not urlsplit(path).scheme and not urlsplit(path).netloc,
             "GitHub request must use a relative API path")
    return path


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def github_request(token):
    """Create a GET-only fixed-host stdlib transport, with no redirects."""
    _require(isinstance(token, str) and bool(token) and "\n" not in token and "\r" not in token,
             "GitHub read credential is required")
    opener = build_opener(_NoRedirect())

    def request(method, path, body=None):
        _require(method == "GET" and body is None, "evidence transport permits GET only")
        _api_path(path)
        req = Request("https://api.github.com" + path, headers={
            "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10", "User-Agent": "team-plugin-release-evidence"})
        try:
            try:
                response = opener.open(req, timeout=20)
            except HTTPError as error:
                response = error
            with response:
                status = response.code
                headers = dict(response.headers)
                # Never parse or surface server errors (may contain credentials).
                if status != 200:
                    return status, headers, None
                raw = response.read(MAX_BODY + 1)
                _require(len(raw) <= MAX_BODY, "GitHub response exceeds size limit")
                return status, headers, json.loads(raw)
        except (URLError, OSError, ValueError):
            raise RuntimeError("GitHub read transport failed; check connectivity/credentials") from None
    return request


def _trusted_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GitHubClient:
    def __init__(self, request, *, policy=None, admin_evidence=None):
        self.request = request
        self.policy = dict(policy) if policy is not None else json.loads((ROOT / "config/release-policy.json").read_text())
        self.admin_evidence = dict(admin_evidence) if admin_evidence is not None else None
        repository = self.policy.get("repository")
        _require(isinstance(repository, str) and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository), "invalid repository policy")
        _require(self.policy.get("source_branch") == "main" and self.policy.get("channel") == "stable"
                 and self.policy.get("verify_workflow") == ".github/workflows/verify.yml", "unsupported release policy")
        self.prefix = "/repos/" + repository

    def _get(self, path, *, missing=False):
        _api_path(path)
        _require(path == self.prefix or path.startswith(self.prefix + "/"), "API path outside configured repository")
        for attempt in range(3):
            status, headers, data = self.request("GET", path)
            if status == 200 or (status == 404 and missing):
                _require(isinstance(headers, dict), "invalid GitHub response headers")
                return status, {k.lower(): v for k, v in headers.items()}, data
            if status in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(0.1 * (2 ** attempt))
                continue
            raise RuntimeError(f"GitHub read failed (HTTP {status}); check API permissions and availability")

    def get_json(self, path):
        return self._get(path)[2]

    def get_pages(self, path):
        """Flatten supported REST lists; follow bounded same-endpoint links only."""
        initial = urlsplit(_api_path(path)).path
        seen, result, total = set(), [], None
        for _ in range(MAX_PAGES):
            _require(path not in seen, "GitHub pagination cycle")
            seen.add(path)
            _, headers, data = self._get(path)
            if isinstance(data, dict):
                keys = [key for key in ("jobs", "workflow_runs", "branch_policies") if key in data]
                _require(len(keys) == 1 and type(data.get("total_count")) is int, "unknown paginated evidence shape")
                if total is None:
                    total = data["total_count"]
                _require(total == data["total_count"] and 0 <= total <= MAX_FILES, "pagination count changed or exceeds limit")
                data = data[keys[0]]
            _require(isinstance(data, list), "expected GitHub evidence list")
            result.extend(data)
            _require(len(result) <= MAX_FILES, "too many evidence entries")
            links = headers.get("link", "")
            _require(isinstance(links, str), "invalid pagination header")
            next_links = re.findall(r'<([^>]+)>;\s*rel="next"', links)
            _require(len(next_links) <= 1, "ambiguous pagination link")
            if not next_links:
                _require(total is None or len(result) == total, "incomplete paginated evidence")
                return result
            url = urlsplit(next_links[0])
            _require(url.scheme == "https" and url.netloc == "api.github.com"
                     and url.path == initial and not url.fragment, "unsafe pagination URL")
            path = url.path + ("?" + url.query if url.query else "")
        raise RuntimeError("GitHub pagination exceeds limit")

    def _repository(self):
        data = self.get_json(self.prefix)
        _require(isinstance(data, dict) and data.get("full_name") == self.policy["repository"], "repository identity mismatch")

    def _ref(self, branch):
        data = self.get_json(self.prefix + "/git/ref/heads/" + branch)
        return self._ref_sha(data, branch)

    @staticmethod
    def _ref_sha(data, branch):
        _require(isinstance(data, dict) and data.get("ref") == "refs/heads/" + branch
                 and isinstance(data.get("object"), dict) and data["object"].get("type") == "commit", "invalid commit reference")
        return validate_sha(data["object"].get("sha"))

    def read_stable(self):
        self._repository()
        status, _, data = self._get(self.prefix + "/git/ref/heads/stable", missing=True)
        if status == 200:
            return self._ref_sha(data, "stable")
        # A 404 alone is ambiguous (not-found or inaccessible). Require a
        # successful matching-ref read without the exact stable reference.
        refs = self.get_json(self.prefix + "/git/matching-refs/heads/stable")
        _require(isinstance(refs, list) and all(isinstance(r, dict) and isinstance(r.get("ref"), str) for r in refs), "cannot establish stable absence")
        _require(not any(r["ref"] == "refs/heads/stable" for r in refs), "stable changed while reading")
        return None

    def _ancestor(self, base, head):
        data = self.get_json(self.prefix + f"/compare/{base}...{head}")
        _require(isinstance(data, dict) and data.get("status") in ("ahead", "identical")
                 and isinstance(data.get("merge_base_commit"), dict)
                 and data["merge_base_commit"].get("sha") == base, "commit ancestry check failed")

    def _workflow(self, path):
        workflow = self.get_json(self.prefix + "/actions/workflows/" + path.rsplit("/", 1)[1])
        _require(isinstance(workflow, dict) and workflow.get("path") == path
                 and workflow.get("state") == "active" and _positive(workflow.get("id")), "workflow identity mismatch")
        return workflow["id"]

    def _run_identity(self, run, workflow, path, event):
        _require(isinstance(run, dict) and run.get("workflow_id") == workflow and run.get("path") == path
                 and run.get("event") == event and run.get("head_branch") == "main"
                 and _positive(run.get("id")) and _positive(run.get("run_attempt")), "run identity mismatch")
        for key in ("repository", "head_repository"):
            _require(isinstance(run.get(key), dict) and run[key].get("full_name") == self.policy["repository"], "run repository mismatch")
        validate_sha(run.get("head_sha"))

    def _ci(self, sha):
        path = self.policy["verify_workflow"]
        workflow = self._workflow(path)
        listing = self.prefix + f"/actions/workflows/{workflow}/runs?head_sha={sha}&event=push&branch=main&per_page=100"
        runs = self.get_pages(listing)
        _require(bool(runs), "no verification run for candidate")
        for run in runs:
            self._run_identity(run, workflow, path, "push")
            _require(run["head_sha"] == sha and _positive(run.get("run_number")), "verification SHA mismatch")
        run = max(runs, key=lambda r: (r["run_number"], r["id"]))
        fresh = self.get_json(self.prefix + f'/actions/runs/{run["id"]}')
        self._run_identity(fresh, workflow, path, "push")
        _require(fresh["id"] == run["id"] and fresh["head_sha"] == sha, "verification run changed")
        jobs = self.get_pages(self.prefix + f'/actions/runs/{fresh["id"]}/attempts/{fresh["run_attempt"]}/jobs?per_page=100')
        normalized, ids = {}, set()
        for job in jobs:
            _require(isinstance(job, dict) and job.get("run_id") == fresh["id"] and job.get("head_sha") == sha
                     and ("run_attempt" not in job or job["run_attempt"] == fresh["run_attempt"])
                     and _positive(job.get("id"))
                     and job["id"] not in ids and isinstance(job.get("name"), str)
                     and job["name"] not in normalized, "job identity mismatch or duplicate job")
            ids.add(job["id"])
            normalized[job["name"]] = job.get("conclusion") if job.get("status") == "completed" else job.get("status")
        again = self.get_json(self.prefix + f'/actions/runs/{fresh["id"]}')
        _require(again == fresh, "verification run changed while reading jobs")
        latest = self.get_pages(listing)
        _require(bool(latest), "verification run disappeared")
        for item in latest:
            self._run_identity(item, workflow, path, "push")
            _require(item["head_sha"] == sha and _positive(item.get("run_number")), "verification listing changed identity")
        newest = max(latest, key=lambda r: (r["run_number"], r["id"]))
        _require(newest["id"] == fresh["id"] and newest["run_attempt"] == fresh["run_attempt"], "new verification run or attempt appeared; retry")
        return {"sha": sha, "event": "push", "branch": "main", "workflow": path,
                "status": fresh.get("status"), "conclusion": fresh.get("conclusion"),
                "attempt": fresh["run_attempt"], "jobs": normalized, "run_id": fresh["id"],
                "url": f'https://github.com/{self.policy["repository"]}/actions/runs/{fresh["id"]}'}

    @staticmethod
    def _safe_path(name):
        _require(isinstance(name, str) and bool(name) and not name.startswith("/")
                 and "\\" not in name and ":" not in name and not any(ord(c) < 32 for c in name), "unsafe tree path")
        parts = name.split("/")
        reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
        _require(all(p not in ("", ".", "..") and not p.endswith((" ", "."))
                     and p.split(".")[0].upper() not in reserved for p in parts), "unsafe portable tree path")
        return PurePosixPath(name)

    def _package(self, sha):
        tree = self.get_json(self.prefix + f"/git/trees/{sha}?recursive=1")
        _require(isinstance(tree, dict) and tree.get("truncated") is False and isinstance(tree.get("tree"), list)
                 and len(tree["tree"]) <= MAX_FILES, "truncated or oversized Git tree")
        selected, seen, total = [], set(), 0
        for item in tree["tree"]:
            _require(isinstance(item, dict), "invalid tree entry")
            name = item.get("path")
            path = self._safe_path(name)
            _require(name.casefold() not in seen, "duplicate or case-colliding Git path")
            seen.add(name.casefold())
            if item.get("type") == "tree" and item.get("mode") == "040000":
                continue
            _require(item.get("type") == "blob" and item.get("mode") in ("100644", "100755"), "links and submodules are not release data")
            if not (name.startswith(PLUGIN + "/") or name in CATALOGS or name in {"config/skills-lock.json", "LICENSE", "CHANGELOG.md"}):
                continue
            _require(not any(p in DENIED_PARTS or any(fnmatch.fnmatch(p.lower(), pattern) for pattern in DENIED_NAMES) for p in path.parts), "denied packaged file")
            size = item.get("size")
            _require(type(size) is int and 0 <= size <= MAX_BODY // 2, "invalid or oversized blob")
            validate_sha(item.get("sha"))
            total += size
            _require(total <= MAX_PACKAGE, "package exceeds size limit")
            selected.append(item)
        with tempfile.TemporaryDirectory(prefix="release-evidence-") as directory:
            root = Path(directory).resolve()
            for item in selected:
                blob = self.get_json(self.prefix + "/git/blobs/" + item["sha"])
                _require(isinstance(blob, dict) and blob.get("encoding") == "base64" and blob.get("sha") == item["sha"]
                         and blob.get("size") == item["size"] and isinstance(blob.get("content"), str)
                         and len(blob["content"]) <= MAX_BODY, "invalid Git blob")
                try:
                    data = base64.b64decode("".join(blob["content"].split()), validate=True)
                except (ValueError, binascii.Error):
                    raise RuntimeError("invalid blob encoding") from None
                digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
                _require(len(data) == item["size"] and digest == item["sha"], "blob size/hash mismatch")
                destination = root / item["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            # Load only the validator in the trusted checkout, never root/scripts.
            framework = _trusted_module("release_trusted_framework", PLUGIN + "/scripts/framework.py")
            registry = framework.validate_release(root / PLUGIN)
            self._catalogs(root, registry["version"])
            lock = json.loads((root / "config/skills-lock.json").read_text())
            license_validator = _trusted_module("release_trusted_licenses", "scripts/sync-skills.py")
            entries = lock.get("skills")
            _require(isinstance(entries, list) and bool(entries), "missing license allowlist")
            licenses = {}
            for entry in entries:
                _require(isinstance(entry, dict) and all(isinstance(entry.get(k), str) and entry[k].strip() for k in license_validator.REQUIRED_FIELDS), "incomplete license evidence")
                license_validator.validate_license_evidence(entry)
                _require(entry["name"] not in licenses, "duplicate license entry")
                _require(entry["name"] in {s["name"] for s in registry["skills"]}, "license entry has no packaged skill")
                if entry["license"] == "Apache-2.0":
                    relative_license = self._safe_path(entry["notice"]["license_file"])
                    skill_root = (root / PLUGIN / "skills" / entry["name"]).resolve()
                    license_path = (skill_root / relative_license).resolve()
                    _require(license_path.is_relative_to(skill_root) and license_path.is_file(),
                             "Apache license payload must be a packaged skill-local file")
                    _require(bool(license_path.read_bytes().strip()), "Apache license payload must not be empty")
                licenses[entry["name"]] = entry
            _require(set(licenses) == {s["name"] for s in registry["skills"]}, "license allowlist differs from package")
            _require((root / PLUGIN / "THIRD_PARTY_NOTICES.md").read_text() == license_validator.render_notices(entries), "distribution notices differ from license evidence")
            _require(bool((root / "LICENSE").read_text().strip()), "missing distribution license")
            return {"sha": sha, "version": registry["version"], "valid_package": True,
                    "skills": {s["name"]: {"version": s["version"], "hash": s["tree_sha256"],
                               "provenance": licenses[s["name"]]["source"] + "@" + licenses[s["name"]]["revision"]}
                               for s in registry["skills"]}}

    @staticmethod
    def _catalogs(root, version):
        for name in CATALOGS:
            catalog = json.loads((root / name).read_text())
            _require(catalog.get("name") == "team-engineering-skills-marketplace", "marketplace identity mismatch")
            entries = catalog.get("plugins")
            _require(isinstance(entries, list) and len(entries) == 1 and entries[0].get("name") == "team-engineering-skills", "marketplace plugin mismatch")
            expected = "./" + PLUGIN
            if name.startswith(".agents/"):
                _require(entries[0].get("source") == {"source": "local", "path": expected}, "Codex marketplace source mismatch")
            else:
                _require(entries[0].get("source") == expected and entries[0].get("version") == version, "Claude marketplace version/source mismatch")

    def collect_candidate(self, sha, baseline_sha):
        validate_sha(sha)
        validate_sha(baseline_sha)
        self._repository()
        main = self._ref("main")
        self._ancestor(sha, main)
        self._ancestor(baseline_sha, sha)
        candidate, baseline = self._package(sha), self._package(baseline_sha)
        ci = self._ci(sha)
        _require(self._ref("main") == main, "main changed during evidence collection; retry")
        candidate["on_main"] = True
        return {"candidate": candidate, "baseline": baseline, "ci": ci, "main_sha": main}

    def collect_approval(self, run_id, candidate_sha):
        validate_sha(candidate_sha)
        _require(_positive(run_id), "invalid promotion run ID")
        self._repository()
        workflow = self._workflow(PROMOTE_WORKFLOW)
        run = self.get_json(self.prefix + f"/actions/runs/{run_id}")
        self._run_identity(run, workflow, PROMOTE_WORKFLOW, "workflow_dispatch")
        _require(run["id"] == run_id and run["run_attempt"] == 1
                 and run.get("display_title") == "Promote " + candidate_sha
                 and run.get("status") == "in_progress", "approval not bound to first-attempt promotion candidate")
        environment = self.policy.get("environment")
        _require(isinstance(environment, str) and bool(environment), "missing protected environment policy")
        environment_path = self.prefix + "/environments/" + quote(environment, safe="")
        env = self.get_json(environment_path)
        _require(isinstance(env, dict) and env.get("name") == environment and _positive(env.get("id")), "environment identity mismatch")
        protection = env.get("protection_rules")
        _require(isinstance(protection, list) and len(protection) == 2
                 and all(isinstance(r, dict) and isinstance(r.get("type"), str) for r in protection)
                 and {r["type"] for r in protection} == {"required_reviewers", "branch_policy"},
                 "unknown, duplicate or missing environment protection rules")
        mode = env.get("deployment_branch_policy")
        _require(isinstance(mode, dict) and mode.get("protected_branches") is False
                 and mode.get("custom_branch_policies") is True, "environment must use custom main-only branch policy")
        branches = self.get_pages(environment_path + "/deployment-branch-policies?per_page=100")
        # The official response schema permits absent type but then does not
        # distinguish branches from tags. Never infer branch from its name.
        _require(len(branches) == 1 and isinstance(branches[0], dict)
                 and _positive(branches[0].get("id")) and branches[0].get("name") == "main"
                 and branches[0].get("type") == "branch", "environment requires one unambiguous main-only branch policy")
        rule = next(r for r in protection if r["type"] == "required_reviewers")
        _require(isinstance(rule, dict) and rule.get("type") == "required_reviewers"
                 and type(rule.get("prevent_self_review")) is bool, "required reviewers/self-review setting missing")
        reviewers = rule.get("reviewers")
        _require(isinstance(reviewers, list) and len(reviewers) == 1 and reviewers[0].get("type") == "User", "unsupported reviewer configuration")
        reviewer = reviewers[0].get("reviewer", {})
        _require(_positive(self.policy.get("reviewer_github_id")) and reviewer.get("id") == self.policy["reviewer_github_id"]
                 and reviewer.get("login") == self.policy.get("reviewer_login"), "configured reviewer differs from activation policy")
        rules = self.get_pages(self.prefix + "/rules/branches/stable?per_page=100")
        required = {"creation", "update", "deletion", "non_fast_forward"}
        _require(bool(rules) and all(isinstance(r, dict) and r.get("type") in required and _positive(r.get("ruleset_id"))
                                     and r.get("ruleset_source_type") == "Repository" and r.get("ruleset_source") == self.policy["repository"]
                                     and (not r.get("parameters") or (r["type"] == "update"
                                          and isinstance(r.get("parameters"), dict)
                                          and set(r["parameters"]) == {"update_allows_fetch_and_merge"}
                                          and r["parameters"]["update_allows_fetch_and_merge"] is False)) for r in rules)
                 and {r["type"] for r in rules} == required, "unknown or incomplete effective stable protection")
        self._admin(env, sorted({r["ruleset_id"] for r in rules}))
        reviews = self.get_pages(self.prefix + f"/actions/runs/{run_id}/approvals")
        matches = []
        for review in reviews:
            _require(isinstance(review, dict) and isinstance(review.get("environments"), list)
                     and isinstance(review.get("user"), dict) and review.get("state") in ("approved", "rejected"), "unknown review evidence shape")
            for reviewed_env in review["environments"]:
                _require(isinstance(reviewed_env, dict), "unknown reviewed environment")
                if reviewed_env.get("id") == env["id"]:
                    _require(reviewed_env.get("name") == environment, "reviewed environment mismatch")
                    matches.append(review)
        # No timestamps or ordering guarantee: ambiguous multiple reviews reject.
        _require(len(matches) == 1 and matches[0]["state"] == "approved", "missing, rejected or ambiguous environment approval")
        review = matches[0]
        evidence = {"repository": self.policy["repository"], "run_id": run_id, "candidate_sha": candidate_sha,
                    "environment_id": env["id"], "environment_name": environment,
                    "reviewer_github_id": review["user"].get("id"), "reviewer_login": review["user"].get("login"),
                    "state": review["state"], "observed_at": datetime.now(timezone.utc).isoformat(),
                    "url": f'https://github.com/{self.policy["repository"]}/actions/runs/{run_id}',
                    "binding": "trusted-run-name-first-attempt", "admin_evidence_reference": self.admin_evidence["evidence_reference"]}
        _require(not check_approval(evidence, self.policy, run_id, candidate_sha), "reviewer approval does not match activation policy")
        _require(self.get_json(self.prefix + f"/actions/runs/{run_id}") == run, "promotion run changed during approval collection")
        return evidence

    def _admin(self, env, ruleset_ids):
        admin = self.admin_evidence
        _require(isinstance(admin, dict), "Admin evidence not configured in protected environment")
        expected = {"schema_version": 1, "repository": self.policy["repository"], "environment_id": env["id"],
                    "reviewer_github_id": self.policy["reviewer_github_id"], "writer_app_id": self.policy.get("writer_app_id"),
                    "ruleset_ids": ruleset_ids, "bypass_review": "only-dedicated-writer-app", "environment_admin_bypass": "disabled"}
        _require(_positive(expected["writer_app_id"]) and all(admin.get(k) == v for k, v in expected.items()), "Admin evidence does not match activation identities/protections")
        _require(isinstance(admin.get("evidence_reference"), str) and bool(admin["evidence_reference"].strip()), "Admin evidence reference required")
        try:
            reviewed = datetime.fromisoformat(admin["reviewed_at"].replace("Z", "+00:00"))
            _require(reviewed.tzinfo is not None and reviewed <= datetime.now(timezone.utc), "invalid Admin review time")
            if "updated_at" in env:
                _require(datetime.fromisoformat(env["updated_at"].replace("Z", "+00:00")) <= reviewed, "environment changed since Admin review")
        except (KeyError, TypeError, ValueError, AttributeError):
            raise RuntimeError("valid Admin review time required") from None
