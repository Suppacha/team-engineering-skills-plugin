"""Read and validate public stable-channel release eligibility evidence."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from release_policy import validate_sha, version_tuple


REPOSITORY = "Suppacha/team-engineering-skills-plugin"
PREFIX = "/repos/" + REPOSITORY
CHANNEL = "stable"
ENVIRONMENT = "team-plugin-stable"
REVIEWER_LOGIN = "Suppacha"
MAX_RESPONSE = 1024 * 1024
MAX_VERSION = 128
MAX_RECORD = 64 * 1024
MAX_PAGES = 10


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _positive(value: object) -> bool:
    return type(value) is int and value > 0


@dataclass(frozen=True)
class Candidate:
    version: str
    sha: str
    record: dict


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _api_path(path: str) -> str:
    parts = urlsplit(path) if isinstance(path, str) else None
    _require(
        isinstance(path, str)
        and path.startswith(PREFIX + "/")
        and not path.startswith("//")
        and not any(character in path for character in "\\\r\n\t#")
        and not parts.scheme
        and not parts.netloc,
        "release-unavailable",
    )
    return path


def _public_request():
    opener = build_opener(_NoRedirect())

    def request(path: str):
        path = _api_path(path)
        req = Request(
            "https://api.github.com" + path,
            method="GET",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": "team-plugin-personal-updater",
            },
        )
        for attempt in range(3):
            try:
                with opener.open(req, timeout=20) as response:
                    raw = response.read(MAX_RESPONSE + 1)
                    if len(raw) > MAX_RESPONSE:
                        raise ValueError("response too large")
                    return json.loads(raw)
            except HTTPError as error:
                if error.code not in (500, 502, 503, 504) or attempt == 2:
                    raise RuntimeError("release-unavailable") from None
            except (URLError, OSError):
                if attempt == 2:
                    raise RuntimeError("release-unavailable") from None
            except (UnicodeError, ValueError):
                raise RuntimeError("release-unavailable") from None
            time.sleep(0.1 * (attempt + 1))
        raise RuntimeError("release-unavailable")

    return request


class PublicReleaseClient:
    """GET-only reader for one fixed public repository and stable channel."""

    def __init__(self, request=None):
        self.request = request if request is not None else _public_request()

    def _get(self, path: str):
        try:
            return self.request(_api_path(path))
        except Exception:
            raise RuntimeError("release-unavailable") from None

    def read_stable(self) -> str:
        data = self._get(PREFIX + "/git/ref/heads/" + CHANNEL)
        try:
            _require(isinstance(data, dict) and data.get("ref") == "refs/heads/" + CHANNEL,
                     "stable-unavailable")
            target = data.get("object")
            _require(isinstance(target, dict) and target.get("type") == "commit", "stable-unavailable")
            return validate_sha(target.get("sha"))
        except ValueError:
            raise ValueError("stable-unavailable") from None

    def _version(self, sha: str) -> str:
        data = self._get(PREFIX + "/contents/plugins/team-engineering-skills/VERSION?ref=" + sha)
        _require(isinstance(data, dict) and data.get("type") == "file"
                 and data.get("encoding") == "base64", "invalid-version-evidence")
        size = data.get("size")
        _require(type(size) is int and 0 < size <= MAX_VERSION, "invalid-version-evidence")
        content = data.get("content")
        _require(isinstance(content, str) and len(content) <= MAX_VERSION * 2,
                 "invalid-version-evidence")
        try:
            raw = base64.b64decode("".join(content.split()), validate=True)
            text = raw.decode("utf-8")
        except (binascii.Error, UnicodeError):
            raise ValueError("invalid-version-evidence") from None
        _require(len(raw) == size and len(raw) <= MAX_VERSION and text.endswith("\n")
                 and text.count("\n") == 1, "invalid-version-evidence")
        version = text[:-1]
        version_tuple(version)
        return version

    @staticmethod
    def _url(run_id: int) -> str:
        return f"https://github.com/{REPOSITORY}/actions/runs/{run_id}"

    def _approval(self, value, *, candidate_sha: str, run_id: int | None = None) -> None:
        _require(isinstance(value, dict), "invalid-approval")
        expected_keys = {
            "repository", "run_id", "candidate_sha", "environment_id", "environment_name",
            "reviewer_github_id", "reviewer_login", "state", "observed_at", "url", "binding",
            "admin_evidence_reference",
        }
        _require(set(value) == expected_keys, "invalid-approval")
        approval_run = value.get("run_id")
        _require(_positive(approval_run) and (run_id is None or approval_run == run_id), "invalid-approval")
        _require(value.get("repository") == REPOSITORY and value.get("candidate_sha") == candidate_sha,
                 "invalid-approval")
        _require(_positive(value.get("environment_id")) and value.get("environment_name") == ENVIRONMENT,
                 "invalid-approval")
        _require(_positive(value.get("reviewer_github_id")) and value.get("reviewer_login") == REVIEWER_LOGIN,
                 "invalid-approval")
        _require(value.get("state") == "approved"
                 and isinstance(value.get("observed_at"), str) and bool(value["observed_at"])
                 and value.get("url") == self._url(approval_run)
                 and value.get("binding") == "trusted-run-name-first-attempt"
                 and isinstance(value.get("admin_evidence_reference"), str)
                 and bool(value["admin_evidence_reference"].strip()), "invalid-approval")

    def _record(self, body, *, version: str, sha: str) -> dict:
        _require(isinstance(body, dict) and body.get("state") == "promoted", "release-not-promoted")
        record = body.get("record")
        _require(isinstance(record, dict), "invalid-release-record")
        required = {
            "schema_version", "repository", "version", "candidate_sha", "previous_stable_sha",
            "baseline_sha", "baseline_version", "run_id", "run_url", "ci_run_id", "ci_url", "approval",
        }
        _require(set(record) == required and record.get("schema_version") == 1
                 and record.get("repository") == REPOSITORY and record.get("version") == version
                 and record.get("candidate_sha") == sha, "invalid-release-record")
        validate_sha(record.get("baseline_sha"))
        previous = record.get("previous_stable_sha")
        if previous is not None:
            validate_sha(previous)
        version_tuple(record.get("baseline_version"))
        run_id, ci_run_id = record.get("run_id"), record.get("ci_run_id")
        _require(_positive(run_id) and _positive(ci_run_id), "invalid-release-record")
        _require(record.get("run_url") == self._url(run_id)
                 and record.get("ci_url") == self._url(ci_run_id), "invalid-evidence-url")
        self._approval(record.get("approval"), candidate_sha=sha, run_id=run_id)
        self._approval(body.get("finalization_approval"), candidate_sha=sha)
        return record

    def _assets(self, release_id: int) -> list:
        assets = []
        for page in range(1, MAX_PAGES + 1):
            data = self._get(PREFIX + f"/releases/{release_id}/assets?per_page=100&page={page}")
            _require(isinstance(data, list) and all(isinstance(asset, dict) for asset in data),
                     "invalid-release-assets")
            assets.extend(data)
            if len(data) < 100:
                return assets
        raise ValueError("release-asset-pagination-limit")

    def candidate(self) -> Candidate:
        sha = self.read_stable()
        version = self._version(sha)
        release = self._get(PREFIX + "/releases/tags/v" + version)
        _require(isinstance(release, dict) and _positive(release.get("id")), "invalid-release")
        _require(release.get("tag_name") == "v" + version
                 and release.get("target_commitish") == sha
                 and release.get("draft") is False
                 and release.get("prerelease") is False, "invalid-release")
        raw_body = release.get("body")
        _require(isinstance(raw_body, str) and len(raw_body.encode("utf-8")) <= MAX_RECORD,
                 "invalid-release-record")
        try:
            body = json.loads(raw_body)
        except (UnicodeError, ValueError):
            raise ValueError("invalid-release-record") from None
        record = self._record(body, version=version, sha=sha)

        tag = self._get(PREFIX + "/git/ref/tags/v" + version)
        target = tag.get("object") if isinstance(tag, dict) else None
        _require(isinstance(tag, dict) and tag.get("ref") == "refs/tags/v" + version
                 and isinstance(target, dict) and target.get("type") == "commit"
                 and target.get("sha") == sha, "invalid-release-tag")

        canonical = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        _require(len(canonical) <= MAX_RECORD, "invalid-release-record")
        assets = self._assets(release["id"])
        _require(len(assets) == 1, "invalid-release-assets")
        asset = assets[0]
        _require(asset.get("name") == "release-record.json" and asset.get("state") == "uploaded"
                 and asset.get("content_type") == "application/json" and asset.get("size") == len(canonical)
                 and asset.get("digest") == "sha256:" + hashlib.sha256(canonical).hexdigest(),
                 "invalid-release-asset-digest")
        return Candidate(version, sha, record)


def check_upgrade(candidate: Candidate, installed: dict | None) -> bool:
    """Return upgrade eligibility, rejecting rollback and same-version drift."""
    if not isinstance(candidate, Candidate):
        raise ValueError("invalid-candidate")
    new = version_tuple(candidate.version)
    validate_sha(candidate.sha)
    if installed is None:
        return True
    if not isinstance(installed, dict) or set(installed) != {"version", "sha"}:
        raise ValueError("invalid-installed-selector")
    old = version_tuple(installed.get("version"))
    installed_sha = validate_sha(installed.get("sha"))
    if new < old or (new == old and candidate.sha != installed_sha):
        raise ValueError("release-regression")
    return new > old
