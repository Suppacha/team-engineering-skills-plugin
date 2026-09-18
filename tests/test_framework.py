"""V2 contract: run the actual offline CLI against disposable local projects."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/team-engineering-skills"
CLI = PLUGIN / "scripts/bootstrap-project.py"


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / "project"
        self.project.mkdir()

    def run_cli(self, release=ROOT, *extra):
        self.assertTrue(CLI.is_file(), "V2 bootstrap CLI must be shipped in the plugin")
        return subprocess.run(
            [sys.executable, str(CLI), "--release", str(release),
             "--project", str(self.project), *extra], capture_output=True, text=True)

    def test_bootstrap_copies_policy_and_records_verifiable_evidence(self):
        (self.project / ".env").write_text("DO_NOT_READ_OR_UPLOAD=this-is-a-fixture")
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.project / "CLAUDE.md").read_text(),
                         "# Team AI adapter\n\n@AGENTS.md\n")
        agents = (self.project / "AGENTS.md").read_text()
        self.assertIn(".team-ai/standards/security.md", agents)
        self.assertIn("supply-chain-risk-auditor", agents)
        evidence = json.loads((self.project / ".team-ai/release.json").read_text())
        self.assertEqual(evidence["version"], "2.2.0")
        self.assertNotIn(str(self.project), json.dumps(evidence))
        for name, digest in evidence["sha256"].items():
            self.assertEqual(hashlib.sha256((self.project / ".team-ai" / name).read_bytes()).hexdigest(), digest)
        self.assertNotIn("DO_NOT_READ_OR_UPLOAD", agents + json.dumps(evidence) + result.stdout)
        self.assertEqual((self.project / ".env").read_text(), "DO_NOT_READ_OR_UPLOAD=this-is-a-fixture")

    def test_dry_run_writes_nothing(self):
        result = self.run_cli(ROOT, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_existing_targets_refused_before_any_write(self):
        for target in ("AGENTS.md", "CLAUDE.md", ".team-ai"):
            with self.subTest(target=target):
                path = self.project / target
                path.write_text("user-owned")
                result = self.run_cli()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("refusing", result.stderr.lower())
                self.assertEqual(list(self.project.iterdir()), [path])
                self.assertEqual(path.read_text(), "user-owned")
                path.unlink()

    def test_repeat_run_does_not_overwrite(self):
        self.assertEqual(self.run_cli().returncode, 0)
        before = (self.project / "AGENTS.md").read_bytes()
        self.assertNotEqual(self.run_cli().returncode, 0)
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), before)

    def test_dangling_destination_symlink_refused(self):
        outside = self.base / "absent"
        (self.project / "CLAUDE.md").symlink_to(outside)
        self.assertNotEqual(self.run_cli().returncode, 0)
        self.assertFalse(outside.exists())
        self.assertFalse((self.project / "AGENTS.md").exists())

    def test_symlinked_project_ancestor_refused(self):
        alias = self.base / "alias"
        alias.symlink_to(self.project, target_is_directory=True)
        self.project = alias
        self.assertNotEqual(self.run_cli().returncode, 0)
        self.assertEqual(list(alias.iterdir()), [])

    def test_missing_project_is_not_created(self):
        self.project = self.base / "missing"
        self.assertNotEqual(self.run_cli().returncode, 0)
        self.assertFalse(self.project.exists())

    def test_untrusted_release_rejected_before_writes(self):
        release = self.base / "release"
        shutil.copytree(PLUGIN, release / "plugins/team-engineering-skills")
        security = release / "plugins/team-engineering-skills/standards/security.md"
        self.assertTrue(security.is_file(), "release needs self-contained policy")
        security.write_text("tampered policy")
        self.assertNotEqual(self.run_cli(release).returncode, 0)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_explicit_release_is_required(self):
        self.assertTrue(CLI.is_file())
        result = subprocess.run([sys.executable, str(CLI), "--project", str(self.project)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.project.iterdir()), [])


class ReleaseSafetyTests(unittest.TestCase):
    def test_export_uses_allowlist_and_filters_nested_secrets(self):
        script = ROOT / "scripts/release_files.py"
        self.assertTrue(script.is_file(), "release must use an explicit file-selection policy")
        spec = importlib.util.spec_from_file_location("release_files", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("README.md", ".gitattributes", "docs/guide.md", "private-notes.md", ".sdd/internal.md",
                         "docs/.env", "docs/.env.production", "plugins/example/private.key",
                         "docs/id_rsa", "docs/cert.pem", ".github/workflows/verify.yml"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture")
            selected = [name for name, path in module.release_files(root)]
            self.assertEqual(
                selected,
                [".gitattributes", ".github/workflows/verify.yml", "README.md", "docs/guide.md"],
            )

    def test_autocrlf_checkout_preserves_registry_bytes_and_binary_template(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            source = base / "source"
            checkout = base / "checkout"
            shutil.copytree(PLUGIN, source / "plugins/team-engineering-skills")
            attributes = ROOT / ".gitattributes"
            if attributes.is_file():
                shutil.copy2(attributes, source / ".gitattributes")

            subprocess.run(["git", "init", "-q", str(source)], check=True)
            subprocess.run(["git", "-C", str(source), "add", "."], check=True)
            checkout.mkdir()
            subprocess.run(
                [
                    "git", "-C", str(source), "-c", "core.autocrlf=true",
                    "checkout-index", "--force", "--all",
                    "--prefix=" + str(checkout) + os.sep,
                ],
                check=True,
            )

            framework_path = checkout / "plugins/team-engineering-skills/scripts/framework.py"
            spec = importlib.util.spec_from_file_location("filtered_checkout_framework", framework_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.validate_release(checkout / "plugins/team-engineering-skills")

            template = "skills/test-case-design/assets/templates/test-design-template.xlsx"
            self.assertEqual(
                (checkout / "plugins/team-engineering-skills" / template).read_bytes(),
                (PLUGIN / template).read_bytes(),
            )


class RegistryTests(unittest.TestCase):
    def setUp(self):
        script = PLUGIN / "scripts/framework.py"
        self.assertTrue(script.is_file(), "V2 metadata validator must exist")
        spec = importlib.util.spec_from_file_location("framework", script)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.plugin = Path(self.temp.name).resolve() / "plugin"
        shutil.copytree(PLUGIN, self.plugin)

    def mutate_registry(self, mutation):
        path = self.plugin / "registry.json"
        registry = json.loads(path.read_text())
        mutation(registry)
        path.write_text(json.dumps(registry))

    def test_valid_release_covers_all_fifteen_skills(self):
        registry = self.module.validate_release(self.plugin)
        lock = json.loads((ROOT / "config/skills-lock.json").read_text())
        self.assertEqual({s["name"] for s in registry["skills"]}, {s["name"] for s in lock["skills"]})
        self.assertEqual(len(registry["skills"]), 15)
        self.assertEqual(registry["owner"], "Suppacha")

    def test_invalid_metadata_is_rejected(self):
        mutations = [
            lambda r: r.update(owner=""),
            lambda r: r.update(version="1.0.0"),
            lambda r: r["skills"].append(r["skills"][0]),
            lambda r: r["skills"][0].update(name="../../escape"),
            lambda r: r["skills"][0].update(routes=[]),
            lambda r: r["skills"][0].update(version="latest"),
            lambda r: r["skills"][0].update(owner=""),
            lambda r: r["standards"].pop("security.md"),
        ]
        original = (self.plugin / "registry.json").read_bytes()
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                (self.plugin / "registry.json").write_bytes(original)
                self.mutate_registry(mutation)
                with self.assertRaises(ValueError):
                    self.module.validate_release(self.plugin)

    def test_skill_resource_changes_require_registry_update(self):
        (self.plugin / "skills/load-testing/new-resource.txt").write_text("changed")
        with self.assertRaises(ValueError):
            self.module.validate_release(self.plugin)

    def test_symlinked_policy_is_rejected_even_with_matching_content(self):
        target = self.plugin / "standards/security.md"
        outside = self.plugin.parent / "policy.md"
        target.rename(outside)
        target.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.module.validate_release(self.plugin)


if __name__ == "__main__":
    unittest.main()
