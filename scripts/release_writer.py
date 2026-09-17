"""Narrow GitHub writes and application-immutable release records.

No retries or redirects, no token in errors, no delete/force operation. GitHub
release immutability is NOT claimed: record/tag/asset consistency is enforced
by this workflow, not server-side WORM storage. The reader stays GET-only.
"""
import hashlib
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from release_policy import validate_sha, version_tuple

MAX_RECORD = 64 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    require(len(raw) <= MAX_RECORD, "release metadata too large")
    return raw


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def writer_request(token, repository):
    """A separate, fixed-host allowlisted POST/PATCH transport; never retries."""
    require(isinstance(token, str) and bool(token) and not any(c in token for c in "\r\n"),
            "writer credential required")
    require(isinstance(repository, str) and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository),
            "invalid writer repository")
    prefix = "/repos/" + repository
    opener = build_opener(NoRedirect())

    def request(method, path, body, *, upload=False):
        require(isinstance(path, str) and path.startswith(prefix + "/"), "writer repository mismatch")
        route = path[len(prefix):]
        if upload:
            require(method == "POST" and re.fullmatch(r"/releases/[1-9][0-9]*/assets\?name=release-record\.json", route)
                    and isinstance(body, bytes) and len(body) <= MAX_RECORD, "invalid release asset write")
            host, raw = "https://uploads.github.com", body
        else:
            require(isinstance(body, dict), "JSON write object required")
            allowed = False
            if method == "POST" and route == "/git/refs":
                ref = body.get("ref", "")
                allowed = set(body) == {"ref", "sha"} and (ref == "refs/heads/stable" or
                    re.fullmatch(r"refs/tags/v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", ref))
                validate_sha(body.get("sha"))
            elif method == "PATCH" and route == "/git/refs/heads/stable":
                allowed = set(body) == {"sha", "force"} and body.get("force") is False
                validate_sha(body.get("sha"))
            elif method == "POST" and route == "/releases":
                allowed = set(body) == {"tag_name", "target_commitish", "name", "body", "draft", "prerelease"}
                allowed = allowed and body.get("draft") is True and body.get("prerelease") is False
                validate_sha(body.get("target_commitish"))
            elif method == "PATCH" and re.fullmatch(r"/releases/[1-9][0-9]*", route):
                allowed = set(body) == {"body", "draft", "make_latest"} and body.get("draft") is False and body.get("make_latest") == "false"
            require(allowed, "write operation outside publisher scope")
            host, raw = "https://api.github.com", encoded(body)
        req = Request(host + path, data=raw, method=method, headers={
            "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
            "Content-Type": "application/json", "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "team-plugin-release-publisher"})
        try:
            with opener.open(req, timeout=20) as response:
                require(response.code in (200, 201), "unconfirmed GitHub write")
                data = response.read(MAX_RECORD + 1)
                require(len(data) <= MAX_RECORD, "write response too large")
                return json.loads(data)
        except (HTTPError, URLError, OSError, ValueError):
            raise RuntimeError("GitHub write unconfirmed; read back remote state before any retry") from None
    return request


class ReleaseWriter:
    def __init__(self, reader, write):
        self.reader, self.write = reader, write
        self.prefix = reader.prefix

    def _tag(self, version):
        version_tuple(version)
        return "v" + version

    def _tag_sha(self, tag):
        status, _, data = self.reader._get(self.prefix + "/git/ref/tags/" + tag, missing=True)
        if status == 404:
            # Successful matching-ref response distinguishes absence from a
            # missing permission; draft visibility additionally requires App.
            refs = self.reader.get_json(self.prefix + "/git/matching-refs/tags/" + tag)
            require(isinstance(refs, list) and all(isinstance(r, dict) for r in refs)
                    and not any(r.get("ref") == "refs/tags/" + tag for r in refs), "tag absence unconfirmed")
            return None
        require(isinstance(data, dict) and data.get("ref") == "refs/tags/" + tag
                and isinstance(data.get("object"), dict) and data["object"].get("type") == "commit",
                "version tag must directly name a commit")
        return validate_sha(data["object"].get("sha"))

    def _release(self, tag):
        # /releases/tags excludes drafts: enumerate with writer read authority.
        releases = self.reader.get_pages(self.prefix + "/releases?per_page=100")
        require(all(isinstance(r, dict) for r in releases), "invalid release list")
        matches = [r for r in releases if r.get("tag_name") == tag]
        require(len(matches) <= 1, "duplicate version release records")
        return matches[0] if matches else None

    def _metadata(self, release, version):
        require(type(release.get("id")) is int and release["id"] > 0, "invalid release ID")
        require(isinstance(release.get("body"), str) and len(release["body"].encode()) <= MAX_RECORD,
                "invalid release body")
        try:
            body = json.loads(release["body"])
        except ValueError:
            raise ValueError("release body is not a publisher record") from None
        require(isinstance(body, dict) and body.get("state") in ("prepared", "promoted")
                and isinstance(body.get("record"), dict), "invalid release metadata")
        record = body["record"]
        require(record.get("schema_version") == 1 and record.get("version") == version
                and record.get("repository") == self.reader.policy["repository"], "release identity mismatch")
        validate_sha(record.get("candidate_sha"))
        if record.get("previous_stable_sha") is not None:
            validate_sha(record["previous_stable_sha"])
        require(type(record.get("run_id")) is int and record["run_id"] > 0
                and isinstance(record.get("approval"), dict), "release approval provenance missing")
        require(release.get("target_commitish") == record["candidate_sha"]
                and release.get("prerelease") is False, "release target differs from fixed candidate")
        require(self._tag_sha(self._tag(version)) == record["candidate_sha"], "version tag differs from release")
        require((body["state"] == "prepared" and release.get("draft") is True)
                or (body["state"] == "promoted" and release.get("draft") is False
                    and isinstance(body.get("finalization_approval"), dict)), "release publication state mismatch")
        return body

    def _asset_matches(self, release, record):
        assets = self.reader.get_pages(self.prefix + f'/releases/{release["id"]}/assets?per_page=100')
        require(all(isinstance(a, dict) for a in assets), "invalid asset list")
        require(len(assets) <= 1, "unexpected assets on publisher record")
        if not assets:
            return False
        raw = encoded(record)
        asset = assets[0]
        require(asset.get("name") == "release-record.json" and asset.get("state") == "uploaded"
                and asset.get("content_type") == "application/json" and asset.get("size") == len(raw)
                and asset.get("digest") == "sha256:" + hashlib.sha256(raw).hexdigest(),
                "release JSON asset conflicts with canonical record")
        return True

    def read_record(self, version):
        release = self._release(self._tag(version))
        if release is None:
            return None
        body = self._metadata(release, version)
        require(self._asset_matches(release, body["record"]), "prepared record missing JSON asset; manual repair required")
        return {"record": body["record"], "state": "prepared" if release["draft"] else "recorded"}

    @staticmethod
    def _once(action, confirmed):
        try:
            action()
        except (RuntimeError, ValueError, OSError):
            pass
        require(confirmed(), "write unconfirmed after readback; manual repair required")

    def prepare_record(self, record):
        tag = self._tag(record["version"])
        sha = validate_sha(record["candidate_sha"])
        existing_sha = self._tag_sha(tag)
        require(existing_sha in (None, sha), "version tag already names a different SHA")
        if existing_sha is None:
            self._once(lambda: self.write("POST", self.prefix + "/git/refs", {"ref": "refs/tags/" + tag, "sha": sha}),
                       lambda: self._tag_sha(tag) == sha)
        release = self._release(tag)
        if release is None:
            payload = {"tag_name": tag, "target_commitish": sha, "name": tag,
                       "body": encoded({"state": "prepared", "record": record}).decode(),
                       "draft": True, "prerelease": False}
            self._once(lambda: self.write("POST", self.prefix + "/releases", payload),
                       lambda: self._release(tag) is not None)
            release = self._release(tag)
        body = self._metadata(release, record["version"])
        require(body["record"] == record, "existing release record cannot be overwritten")
        if not self._asset_matches(release, record):
            require(release["draft"] is True, "published release cannot gain an asset")
            self._once(lambda: self.write("POST", self.prefix + f'/releases/{release["id"]}/assets?name=release-record.json',
                                          encoded(record), upload=True),
                       lambda: self._asset_matches(release, record))

    def finalize_record(self, record, approval):
        release = self._release(self._tag(record["version"]))
        require(release is not None, "prepared release missing")
        body = self._metadata(release, record["version"])
        require(body["record"] == record and self._asset_matches(release, record), "prepared record changed")
        if release["draft"] is False:
            return
        payload = {"draft": False, "make_latest": "false", "body": encoded({
            "state": "promoted", "record": record, "finalization_approval": approval}).decode()}
        self._once(lambda: self.write("PATCH", self.prefix + f'/releases/{release["id"]}', payload),
                   lambda: self.read_record(record["version"])["state"] == "recorded")

    def create_stable(self, candidate):
        self.write("POST", self.prefix + "/git/refs", {"ref": "refs/heads/stable", "sha": validate_sha(candidate)})

    def update_stable(self, candidate, *, force):
        require(force is False, "force updates are forbidden")
        self.write("PATCH", self.prefix + "/git/refs/heads/stable", {"sha": validate_sha(candidate), "force": False})
