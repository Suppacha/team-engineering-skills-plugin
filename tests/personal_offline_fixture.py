"""Child-process fixture: real extracted entry/store/reader/client; fake OS/network edges."""
import base64
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
from unittest.mock import patch


def main():
    extracted, fixture, repository = map(Path, sys.argv[1:])
    sys.path.insert(0, str(extracted / "scripts"))
    from team_updater import cli, client as client_module
    from team_updater.release import PublicReleaseClient
    from team_updater.store import Store
    assert Path(cli.__file__).is_relative_to(extracted)
    real_run = subprocess.run
    source = fixture / "git-source"
    source.mkdir()
    for name in ("plugins/team-engineering-skills", ".agents", ".claude-plugin"):
        shutil.copytree(repository / name, source / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (source / "config").mkdir()
    shutil.copy2(repository / "config/skills-lock.json", source / "config/skills-lock.json")
    shutil.copy2(repository / "LICENSE", source / "LICENSE")
    def git(*args):
        return real_run(["git", "-C", str(source), *args], check=True,
                        capture_output=True, text=True).stdout.strip()
    git("init", "-q")
    def commit():
        git("add", ".")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-qm", "fixture")
        return git("rev-parse", "HEAD")
    first = commit()
    plugin = source / "plugins/team-engineering-skills"
    for path in (plugin / "registry.json", plugin / ".codex-plugin/plugin.json",
                 plugin / ".claude-plugin/plugin.json"):
        data = json.loads(path.read_bytes())
        data["version"] = "2.2.1"
        path.write_text(json.dumps(data), encoding="utf-8")
    (plugin / "VERSION").write_text("2.2.1\n", encoding="utf-8")
    catalog = source / ".claude-plugin/marketplace.json"
    data = json.loads(catalog.read_bytes())
    data["plugins"][0]["version"] = "2.2.1"
    catalog.write_text(json.dumps(data), encoding="utf-8")
    second = commit()
    selected = {"sha": first}
    prefix = "/repos/Suppacha/team-engineering-skills-plugin"
    repo_url = "https://github.com/Suppacha/team-engineering-skills-plugin"
    requested = []
    def approval(run):
        return {"repository": "Suppacha/team-engineering-skills-plugin", "run_id": run,
                "candidate_sha": selected["sha"], "environment_id": 77,
                "environment_name": "team-plugin-stable", "reviewer_github_id": 12345,
                "reviewer_login": "Suppacha", "state": "approved",
                "observed_at": "2026-09-17T01:02:03+00:00", "url": repo_url + f"/actions/runs/{run}",
                "binding": "trusted-run-name-first-attempt",
                "admin_evidence_reference": "admin/offline-fixture"}
    def request(path):
        requested.append(path)
        sha = selected["sha"]
        version_raw = git("show", sha + ":plugins/team-engineering-skills/VERSION") + "\n"
        version = version_raw.strip()
        record = {"schema_version": 1, "repository": "Suppacha/team-engineering-skills-plugin",
                  "version": version, "candidate_sha": sha, "previous_stable_sha": "b" * 40,
                  "baseline_sha": "b" * 40, "baseline_version": "2.1.0", "run_id": 991,
                  "run_url": repo_url + "/actions/runs/991", "ci_run_id": 881,
                  "ci_url": repo_url + "/actions/runs/881", "approval": approval(991)}
        canonical = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
        routes = {
            prefix + "/git/ref/heads/stable": {"ref": "refs/heads/stable", "object": {"type": "commit", "sha": sha}},
            prefix + f"/contents/plugins/team-engineering-skills/VERSION?ref={sha}": {
                "type": "file", "encoding": "base64", "size": len(version_raw), "sha": "c" * 40,
                "content": base64.b64encode(version_raw.encode()).decode()},
            prefix + "/releases/tags/v" + version: {"id": 42, "tag_name": "v" + version,
                "target_commitish": sha, "draft": False, "prerelease": False,
                "body": json.dumps({"state": "promoted", "record": record, "finalization_approval": approval(992)})},
            prefix + "/git/ref/tags/v" + version: {"ref": "refs/tags/v" + version, "object": {"type": "commit", "sha": sha}},
            prefix + "/releases/42/assets?per_page=100&page=1": [{"id": 43, "name": "release-record.json",
                "state": "uploaded", "content_type": "application/json", "size": len(canonical),
                "digest": "sha256:" + hashlib.sha256(canonical).hexdigest()}],
        }
        return routes[path]
    def transport(command, **kwargs):
        command = list(command)
        remote = "https://github.com/Suppacha/team-engineering-skills-plugin.git"
        if remote in command:
            command[command.index(remote)] = str(source)
        if "protocol.file.allow=never" in command:
            command[command.index("protocol.file.allow=never")] = "protocol.file.allow=always"
        return real_run(command, **kwargs)
    profile = fixture / "desktop profile"
    untouched = fixture / "other profile"
    untouched.mkdir()
    (untouched / "sentinel").write_bytes(b"do not modify")
    root = fixture / "updater state"
    inventories = {}
    mutations = []
    def client_transport(command, **kwargs):
        home = Path(kwargs["env"]["CODEX_HOME"])
        state = inventories.setdefault(str(home), {"source": None, "version": None, "enabled": True})
        args = command[1:]
        market, name = "team-engineering-skills-marketplace", "team-engineering-skills"
        selector = name + "@" + market
        local = state["source"]
        if args in (["--version"], ["plugin", "--help"], ["plugin", "marketplace", "--help"]):
            return subprocess.CompletedProcess(command, 0, b"codex-cli fixture", b"")
        if args == ["plugin", "marketplace", "list", "--json"]:
            body = {"marketplaces": [] if local is None else [{"name": market, "root": str(local),
                    "marketplaceSource": {"sourceType": "local", "source": str(local)}}]}
        elif args[:4] == ["plugin", "marketplace", "add", "--json"]:
            local = Path(args[4])
            state["source"] = local
            mutations.append((str(home), "register"))
            body = {"marketplaceName": market, "installedRoot": str(local), "alreadyAdded": False}
        elif args == ["plugin", "list", "--json"]:
            installed = [] if state["version"] is None else [{"pluginId": selector, "name": name,
                "marketplaceName": market, "version": state["version"], "installed": True,
                "enabled": state["enabled"], "installPolicy": "AVAILABLE", "authPolicy": "ON_USE",
                "source": {"source": "local", "path": str(local / "plugins" / name)},
                "marketplaceSource": {"sourceType": "local", "source": str(local)}}]
            body = {"installed": installed, "available": []}
        elif args == ["plugin", "add", "--json", selector]:
            version = (local / "plugins" / name / "VERSION").read_text().strip()
            cache = home / "plugins/cache" / market / name / version
            cache.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(local / "plugins" / name, cache)
            state["version"] = version
            mutations.append((str(home), "install"))
            body = {"pluginId": selector, "name": name, "marketplaceName": market,
                    "version": version, "installedPath": str(cache), "authPolicy": "ON_USE"}
        else:
            raise AssertionError(args)
        return subprocess.CompletedProcess(command, 0, json.dumps(body).encode(), b"")
    class Schedule:
        active = False
        enables = 0
        def status(self): return self.active
        def enable(self): self.enables += 1; self.active = True
        def disable(self): self.active = False
    schedule = Schedule()
    def invoke(command, *args, expected=0):
        output, errors = io.StringIO(), io.StringIO()
        argv = [str(extracted / "scripts/team-update.py"), command, "--state-dir", str(root), "--json", *args]
        with patch.object(sys, "argv", argv), redirect_stdout(output), redirect_stderr(errors):
            try:
                runpy.run_path(argv[0], run_name="__main__")
            except SystemExit as error:
                assert error.code == expected, (argv, error.code, errors.getvalue())
        return json.loads(output.getvalue()) if output.getvalue() else None
    install_args = ["--codex", str(Path(sys.executable).resolve()), "--git", shutil.which("git"),
                    "--codex-home", str(profile)]
    platform = "win32" if os.name == "nt" else "darwin"
    with patch.object(cli.sys, "platform", platform), \
            patch.object(cli, "Store", side_effect=lambda path: Store(path, run=transport)), \
            patch.object(cli, "PublicReleaseClient", side_effect=lambda: PublicReleaseClient(request)), \
            patch.object(cli, "Scheduler", side_effect=lambda *args: schedule), \
            patch.object(client_module, "_bounded_run", side_effect=client_transport):
        initial = invoke("install", *install_args)
        assert initial["installed_version"] == "2.2.0" and initial["loaded_session"] == "unknown"
        assert initial["management_command"]
        count = len(mutations)
        invoke("install", *install_args)
        assert len(mutations) == count and schedule.enables == 1
        assert not (root / "previous").exists()
        selected["sha"] = second
        update = invoke("install", *install_args)
        assert update["installed_version"] == "2.2.1"
        assert (root / "previous/plugins/team-engineering-skills/VERSION").read_text().strip() == "2.2.0"
        count = len(mutations)
        invoke("install", *install_args)
        assert len(mutations) == count and schedule.enables == 1
        selected["sha"] = first
        invoke("install", *install_args, expected=2)
        assert b"release-regression" in (root / "logs/updater.log").read_bytes()
        assert invoke("status")["last_result"] == "release-regression"
        assert len(mutations) == count
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
            "commit", "--allow-empty", "-qm", "same-version-drift")
        selected["sha"] = git("rev-parse", "HEAD")
        invoke("install", *install_args, expected=2)
        assert invoke("status")["last_result"] == "release-regression" and len(mutations) == count
        config_before = (root / cli.CONFIG).read_bytes()
        alternate = fixture / "unapproved-new-profile"
        invoke("install", *install_args[:-1], str(alternate), expected=2)
        assert (root / cli.CONFIG).read_bytes() == config_before and not alternate.exists()
        store = Store(root)
        state = store.read_state()
        # Force an integrity failure, then verify that resume/reinstall cannot clear it.
        cache_file = Path(state["installed"]["cache"]["installed_path"]) / "VERSION"
        saved = cache_file.read_bytes()
        cache_file.write_bytes(b"tampered")
        selected["sha"] = second
        state["next_check"] = None
        store.write_state(state)
        assert invoke("check")["last_result"] == "repair-required"
        invoke("resume", expected=2)
        invoke("install", *install_args, expected=2)
        invoke("repair-verify", expected=2)
        assert store.read_state()["repair_required"]
        cache_file.write_bytes(saved)
        assert invoke("repair-verify")["last_result"] == "repair-verified"
        assert not store.read_state()["repair_required"]
        invoke("resume")
        store.write_journal({"schema": 1, "phase": "installing", "version": "2.2.1", "sha": second, "initial": False})
        invoke("pause")
        assert not schedule.active and store.read_journal()["phase"] == "installing"
        assert invoke("status")["last_result"] == "repair-required"
        invoke("uninstall-updater")
        assert store.read_journal() is not None
        store.write_journal({"phase": "unknown"})
        invoke("repair-verify", expected=2)
        assert store.read_journal() == {"phase": "unknown"}
        store.write_journal(None)
        unknown_state = store.read_state()
        unknown_state["schema"] = 99
        store.write_state(unknown_state)
        invoke("repair-verify", expected=2)
        assert store.read_state()["repair_required"]
        assert all(home == str(profile) for home, _ in mutations)
        assert (untouched / "sentinel").read_bytes() == b"do not modify"
        assert list(untouched.iterdir()) == [untouched / "sentinel"]
        assert any("/contents/plugins/team-engineering-skills/VERSION?ref=" in path for path in requested)
        logs = b"".join(path.read_bytes() for path in (root / "logs").iterdir())
        assert b"release-regression" in logs and b"repair-required" in logs
    print("offline extracted-entry A-to-B, repeated-install, regression, repair, stop, two-profile isolation: PASS")


if __name__ == "__main__":
    main()
