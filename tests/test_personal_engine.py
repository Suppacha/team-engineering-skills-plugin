from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from team_updater.engine import Updater
from team_updater.release import Candidate

SHA_A = "a" * 40
SHA_B = "b" * 40
NOW = datetime(2026, 9, 17, 4, 0, tzinfo=timezone.utc)


class MemoryStore:
    def __init__(self):
        self.state_value = {}
        self.journal_value = None
        self.current = Path("/owned/current")
        self.previous = Path("/owned/previous")
        self.events = []
        self.fail_after = None
        self.fail_state_after_write = False

    @contextmanager
    def lock(self):
        self.events.append("lock")
        yield

    def read_state(self): return dict(self.state_value)
    def write_state(self, value):
        self.events.append("state")
        self.state_value = dict(value)
        if self.fail_state_after_write:
            self.fail_state_after_write = False
            raise RuntimeError("crash-after-state")
    def read_journal(self): return self.journal_value
    def write_journal(self, value):
        self.journal_value = None if value is None else dict(value)
        phase = None if value is None else value["phase"]
        self.events.append("journal:" + str(phase))
        if phase is not None and phase == self.fail_after:
            raise RuntimeError("crash")
    def stage(self, candidate, git):
        self.events.append("stage")
        return Path("/owned/staging") / candidate.sha
    def activate(self, staged): self.events.append("activate")


class Releases:
    def __init__(self, candidate, stable=None):
        self.value = candidate
        self.stable = stable if stable is not None else candidate.sha
    def candidate(self): return self.value
    def read_stable(self): return self.stable


class Client:
    def __init__(self): self.installed = False
    def validate_source(self, source): pass
    def inventory(self): return None
    def register(self, source): pass
    def install(self, source, candidate): self.installed = True; return {"version": candidate.version}
    def verify(self, source, candidate): return self.installed


class EngineTests(unittest.TestCase):
    def engine(self, store=None, releases=None, client=None):
        return Updater(store or MemoryStore(), releases or Releases(Candidate("2.2.0", SHA_B, {})),
                       client or Client(), Path("/usr/bin/git"), clock=lambda: NOW)

    def enabled_store(self):
        store = MemoryStore()
        store.state_value = {"schema": 1, "enabled": True,
            "installed": {"version": "2.1.0", "sha": SHA_A}, "available": None,
            "last_check": None, "last_result": "installed", "next_check": None,
            "reload_required": False, "codex_home": "/profile"}
        return store

    def test_disabled_check_does_not_mutate_plugin(self):
        store = MemoryStore()
        client = Client()
        result = self.engine(store=store, client=client).check()
        self.assertEqual(result["last_result"], "disabled")
        self.assertFalse(client.installed)
        self.assertNotIn("stage", store.events)

    def test_locked_reconciliation_does_not_acquire_a_nested_store_lock(self):
        store = MemoryStore()
        with store.lock():
            result = self.engine(store=store).reconcile_completed_locked()
        self.assertEqual(result, {})
        self.assertEqual(store.events.count("lock"), 1)

    def test_public_reconciliation_delegates_to_single_locked_implementation(self):
        store = MemoryStore()
        engine = self.engine(store=store)
        calls = []

        def locked():
            calls.append("locked")
            return {"delegated": True}

        engine.reconcile_completed_locked = locked
        self.assertEqual(engine.reconcile_completed(), {"delegated": True})
        self.assertEqual(calls, ["locked"])
        self.assertEqual(store.events.count("lock"), 1)

    def test_source_collision_is_rejected_before_staging_or_activation(self):
        class Collision(Client):
            def validate_source(self, source): raise ValueError("source-collision")
        store = self.enabled_store()
        with self.assertRaisesRegex(ValueError, "source-collision"):
            self.engine(store=store, client=Collision()).check()
        self.assertNotIn("stage", store.events)
        self.assertNotIn("activate", store.events)

    def test_future_next_check_observes_cooldown(self):
        store = self.enabled_store()
        store.state_value["next_check"] = "2026-09-17T05:00:00+00:00"
        result = self.engine(store=store).check()
        self.assertEqual(result["last_result"], "cooldown")
        self.assertNotIn("stage", store.events)

    def test_changed_stable_cannot_activate(self):
        store = self.enabled_store()
        client = Client()
        candidate = Candidate("2.2.0", SHA_B, {})
        result = self.engine(store, Releases(candidate, stable=SHA_A), client).check()
        self.assertEqual(result["last_result"], "stable-moved")
        self.assertNotIn("activate", store.events)
        self.assertFalse(client.installed)

    def test_success_journals_each_phase_then_writes_state_last(self):
        store = self.enabled_store()
        result = self.engine(store=store).check()
        self.assertEqual(result["last_result"], "updated")
        self.assertTrue(result["reload_required"])
        self.assertEqual(store.events[-2:], ["journal:verified", "state"])
        self.assertEqual(store.journal_value["final_state"], result)
        self.assertLess(store.events.index("journal:prepared"), store.events.index("activate"))
        self.assertLess(store.events.index("journal:swapped"), store.events.index("journal:installing"))

    def test_crash_journal_suppresses_future_mutation_as_repair_required(self):
        for phase in ("prepared", "swapped", "installing", "verified"):
            with self.subTest(phase=phase):
                store = self.enabled_store()
                store.fail_after = phase
                with self.assertRaises(RuntimeError):
                    self.engine(store=store).check()
                store.fail_after = None
                store.events.clear()
                result = self.engine(store=store).check()
                self.assertEqual(result["last_result"], "repair-required")
                self.assertNotIn("stage", store.events)

    def test_crash_after_final_state_write_reconciles_only_after_cache_verification(self):
        store = self.enabled_store()
        client = Client()
        store.fail_state_after_write = True
        with self.assertRaisesRegex(RuntimeError, "crash-after-state"):
            self.engine(store=store, client=client).check()
        self.assertEqual(store.journal_value["phase"], "verified")
        store.events.clear()
        result = self.engine(store=store, client=client).check()
        self.assertEqual(result["last_result"], "cooldown")
        self.assertIn("journal:None", store.events)

    def test_verified_journal_with_unverifiable_cache_requires_repair(self):
        store = self.enabled_store()
        client = Client()
        store.fail_state_after_write = True
        with self.assertRaises(RuntimeError):
            self.engine(store=store, client=client).check()
        client.installed = False
        result = self.engine(store=store, client=client).check()
        self.assertEqual(result["last_result"], "repair-required")
        self.assertEqual(store.journal_value["phase"], "verified")

    def test_public_reconcile_completed_clears_only_verified_matching_operation(self):
        store = self.enabled_store()
        client = Client()
        store.fail_state_after_write = True
        with self.assertRaises(RuntimeError):
            self.engine(store=store, client=client).check()
        result = self.engine(store=store, client=client).reconcile_completed()
        self.assertEqual(result, store.state_value)
        self.assertIsNone(store.journal_value)

    def test_up_to_date_still_requires_installed_byte_verification(self):
        store = self.enabled_store()
        store.state_value["installed"] = {"version": "2.2.0", "sha": SHA_B}
        client = Client()
        result = self.engine(store=store, client=client).check()
        self.assertEqual(result["last_result"], "repair-required")

    def test_initial_install_keeps_disabled_until_verified(self):
        store = MemoryStore()
        result = self.engine(store=store).install_initial()
        self.assertFalse(result["enabled"])
        self.assertEqual(result["last_result"], "installed")
        self.assertEqual(result["codex_home"], "/profile")

    def test_network_failure_retains_installed_and_sets_bounded_next_check(self):
        class Offline:
            def candidate(self): raise RuntimeError("release-unavailable")
        store = self.enabled_store()
        result = self.engine(store=store, releases=Offline()).check()
        self.assertEqual(result["installed"], {"version": "2.1.0", "sha": SHA_A})
        self.assertEqual(result["last_result"], "release-unavailable")
        self.assertEqual(result["next_check"], "2026-09-17T08:00:00+00:00")


if __name__ == "__main__": unittest.main()
