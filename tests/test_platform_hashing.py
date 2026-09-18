"""Hash ordering must not inherit the host filesystem's case comparison."""
import hashlib
import importlib.util
from pathlib import Path, PureWindowsPath
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "platform_hash_framework", ROOT / "plugins/team-engineering-skills/scripts/framework.py")
framework = importlib.util.module_from_spec(spec)
spec.loader.exec_module(framework)


class PlatformHashTests(unittest.TestCase):
    def test_hash_preserves_case_sensitive_component_order_on_windows(self):
        # Catches native Path sorting, case folding, and flat-string sorting.
        # Use real files; only simulate Windows Path comparison on other hosts.
        ordered_payloads = [("Z.md", b"upper"), ("a/child.md", b"nested"),
                            ("a.md", b"sibling")]
        expected = hashlib.sha256()
        for name, payload in ordered_payloads:
            expected.update(name.encode("utf-8") + b"\0")
            expected.update(hashlib.sha256(payload).digest())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, payload in reversed(ordered_payloads):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
            def windows_less_than(left, right):
                return PureWindowsPath(left.as_posix()) < PureWindowsPath(right.as_posix())
            with mock.patch.object(type(root), "__lt__", windows_less_than):
                self.assertEqual(framework.tree_digest(root), expected.hexdigest())


if __name__ == "__main__":
    unittest.main()
