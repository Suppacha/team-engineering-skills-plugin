from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class OfflineArtifactTests(unittest.TestCase):
    def test_extracted_public_lifecycle_with_real_package_git_reader_and_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory).resolve()
            archive = fixture / "updater.zip"
            subprocess.run([sys.executable, str(ROOT / "scripts/build-updater.py"), "--output", str(archive)],
                           check=True, capture_output=True)
            extracted = fixture / "extracted"
            with zipfile.ZipFile(archive) as data:
                data.extractall(extracted)
            home = fixture / "child-home"
            home.mkdir()
            env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), CODEX_HOME=str(home / ".codex"),
                       PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run([sys.executable, "-I", str(ROOT / "tests/personal_offline_fixture.py"),
                                     str(extracted), str(fixture), str(ROOT)], env=env,
                                    capture_output=True, text=True, timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("two-profile isolation: PASS", result.stdout)
