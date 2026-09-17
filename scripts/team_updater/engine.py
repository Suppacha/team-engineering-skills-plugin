"""Journaled update orchestration for the personal Desktop updater."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from team_updater.release import Candidate, check_upgrade


INTERVAL = timedelta(hours=4)


def _stamp(value):
    return value.astimezone(timezone.utc).isoformat()


class Updater:
    def __init__(self, store, releases, client, git_executable: Path, clock=None):
        self.store = store
        self.releases = releases
        self.client = client
        self.git_executable = git_executable
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self):
        value = self.clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError("invalid-clock")
        return value.astimezone(timezone.utc)

    def _base(self, state, now):
        result = dict(state)
        result.setdefault("schema", 1)
        result.setdefault("enabled", False)
        result.setdefault("installed", None)
        result.setdefault("available", None)
        result.setdefault("reload_required", False)
        result["last_check"] = _stamp(now)
        result["next_check"] = _stamp(now + INTERVAL)
        result.setdefault("codex_home", str(getattr(self.client, "codex_home", Path("/profile"))))
        return result

    def status(self) -> dict:
        with self.store.lock():
            return self.store.read_state()

    def _reconcile_locked(self, state) -> bool:
        journal = self.store.read_journal()
        if journal is None:
            return True
        if (not isinstance(journal, dict) or journal.get("schema") != 1
                or journal.get("phase") != "verified"
                or set(journal) != {"schema", "phase", "version", "sha", "initial",
                                    "final_state"}
                or journal.get("final_state") != state):
            return False
        try:
            candidate = Candidate(journal["version"], journal["sha"], {})
            self._bind(state.get("installed"))
            if not self.client.verify(self.store.current, candidate):
                return False
        except (KeyError, TypeError, ValueError, RuntimeError):
            return False
        self.store.write_journal(None)
        return True

    def reconcile_completed(self) -> dict:
        """Clear one proven-complete journal before an external state edit.

        Returns the unchanged state.  Raises ``repair-required`` when the
        journal is incomplete, malformed, mismatched, or its cache cannot be
        verified; callers must not edit state after that error.
        """
        with self.store.lock():
            return self.reconcile_completed_locked()

    def reconcile_completed_locked(self) -> dict:
        """Reconcile while the caller holds this store's lifecycle lock."""
        state = self.store.read_state()
        try:
            reconciled = self._reconcile_locked(state)
        except ValueError:
            reconciled = False
        if not reconciled:
            raise RuntimeError("repair-required")
        return state

    def _bind(self, installed):
        bind = getattr(self.client, "bind_evidence", None)
        if bind is not None:
            evidence = None
            if isinstance(installed, dict) and "cache" in installed:
                evidence = installed["cache"]
            bind(evidence)

    def check(self) -> dict:
        with self.store.lock():
            now = self._now()
            original = self.store.read_state()
            state = self._base(original, now)
            try:
                reconciled = self._reconcile_locked(original)
            except ValueError:
                reconciled = False
            if not reconciled:
                state["last_result"] = "repair-required"
                self.store.write_state(state)
                return state
            if not state["enabled"]:
                state["last_result"] = "disabled"
                self.store.write_state(state)
                return state
            next_check = original.get("next_check")
            if isinstance(next_check, str):
                try:
                    due = datetime.fromisoformat(next_check)
                    if due.tzinfo is not None and now < due.astimezone(timezone.utc):
                        state["last_result"] = "cooldown"
                        state["next_check"] = next_check
                        self.store.write_state(state)
                        return state
                except ValueError:
                    pass
            self._bind(state.get("installed"))
            validate_source = getattr(self.client, "validate_source", None)
            if validate_source is not None:
                validate_source(self.store.current)
            try:
                candidate = self.releases.candidate()
            except RuntimeError:
                state["last_result"] = "release-unavailable"
                self.store.write_state(state)
                return state
            state["available"] = {"version": candidate.version, "sha": candidate.sha}
            selector = None
            if isinstance(state.get("installed"), dict):
                selector = {key: state["installed"].get(key) for key in ("version", "sha")}
            try:
                upgrade = check_upgrade(candidate, selector)
            except ValueError:
                state["last_result"] = "release-regression"
                self.store.write_state(state)
                return state
            if not upgrade:
                if self.client.verify(self.store.current, candidate):
                    state["last_result"] = "up-to-date"
                else:
                    state["last_result"] = "repair-required"
                self.store.write_state(state)
                return state
            return self._install(state, candidate, now, initial=False)

    def install_initial(self) -> dict:
        with self.store.lock():
            now = self._now()
            original = self.store.read_state()
            state = self._base(original, now)
            try:
                reconciled = self._reconcile_locked(original)
            except ValueError:
                reconciled = False
            if not reconciled:
                state["last_result"] = "repair-required"
                self.store.write_state(state)
                return state
            state["enabled"] = False
            validate_source = getattr(self.client, "validate_source", None)
            if validate_source is not None:
                validate_source(self.store.current)
            candidate = self.releases.candidate()
            state["available"] = {"version": candidate.version, "sha": candidate.sha}
            return self._install(state, candidate, now, initial=True)

    def _install(self, state, candidate, now, *, initial):
        staged = self.store.stage(candidate, self.git_executable)
        transaction = {"schema": 1, "phase": "prepared", "version": candidate.version,
                       "sha": candidate.sha, "initial": initial}
        self.store.write_journal(transaction)
        if self.releases.read_stable() != candidate.sha:
            state["last_result"] = "stable-moved"
            self.store.write_journal(None)
            self.store.write_state(state)
            return state
        self.store.activate(staged)
        transaction["phase"] = "swapped"
        self.store.write_journal(transaction)
        self.client.register(self.store.current)
        transaction["phase"] = "installing"
        self.store.write_journal(transaction)
        evidence = self.client.install(self.store.current, candidate)
        if not self.client.verify(self.store.current, candidate):
            state["last_result"] = "repair-required"
            self.store.write_state(state)
            return state
        cache = {"installed_path": evidence["installed_path"], "tree": evidence["tree"]} \
            if "installed_path" in evidence else None
        state["installed"] = {"version": candidate.version, "sha": candidate.sha}
        if cache is not None:
            state["installed"]["cache"] = cache
        state["available"] = {"version": candidate.version, "sha": candidate.sha}
        state["last_result"] = "installed" if initial else "updated"
        state["reload_required"] = True
        state["enabled"] = False if initial else state["enabled"]
        state["last_check"] = _stamp(now)
        state["next_check"] = _stamp(now + INTERVAL)
        transaction["phase"] = "verified"
        transaction["final_state"] = state
        self.store.write_journal(transaction)
        self.store.write_state(state)
        return state
