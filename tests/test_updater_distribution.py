from pathlib import Path
import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from team_updater.cli import runtime_files


class UpdaterDistributionTests(unittest.TestCase):
    def build(self, output: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/build-updater.py"), "--output", str(output)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_archive_is_the_bounded_runtime_allowlist_and_excludes_private_state(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "updater.zip"
            result = self.build(output)
            self.assertEqual(result.returncode, 0, result.stderr)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()

        self.assertEqual(names, sorted(runtime_files()))
        self.assertIn("scripts/team-update.py", names)
        self.assertFalse(any(".superpowers/" in name or name.endswith(".pem") for name in names))

    def test_archive_is_reproducible_and_runtime_imports_from_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            first = temporary / "first.zip"
            second = temporary / "second.zip"
            for output in (first, second):
                result = self.build(output)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(),
                             hashlib.sha256(second.read_bytes()).digest())

            extracted = temporary / "extracted"
            with zipfile.ZipFile(first) as archive:
                archive.extractall(extracted)
            probe = subprocess.run(
                [sys.executable, "-I", "-c",
                 "import sys; "
                 "sys.path.insert(0, sys.argv[1]); "
                 "from team_updater.cli import runtime_files; "
                 "from team_updater.release import Candidate; "
                 "from team_updater.store import Store; "
                 "assert 'scripts/team-update.py' in runtime_files(); "
                 "assert Candidate and Store",
                 str(extracted / "scripts")],
                cwd=temporary,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)


if __name__ == "__main__":
    unittest.main()
