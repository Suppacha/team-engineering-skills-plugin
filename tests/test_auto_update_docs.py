from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AutoUpdateDocumentationTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_claude_example_is_a_narrow_stable_marketplace_fragment(self):
        config = json.loads(self.read("config/claude-code-stable.example.json"))
        self.assertEqual(set(config), {"extraKnownMarketplaces"})
        marketplaces = config["extraKnownMarketplaces"]
        self.assertEqual(set(marketplaces), {"team-engineering-skills-marketplace"})
        entry = marketplaces["team-engineering-skills-marketplace"]
        self.assertEqual(
            entry,
            {
                "source": {
                    "source": "github",
                    "repo": "Suppacha/team-engineering-skills-plugin",
                    "ref": "stable",
                },
                "autoUpdate": True,
            },
        )
        serialized = json.dumps(config)
        self.assertNotIn('"permissions"', serialized)
        self.assertNotIn('"env"', serialized)

    def test_admin_guide_documents_exact_runtime_configuration_and_evidence(self):
        admin = self.read("docs/AUTO_UPDATE_ADMIN_TH.md")
        for value in (
            "team-plugin-stable",
            "RELEASE_WRITER_PRIVATE_KEY",
            "RELEASE_WRITER_APP_ID",
            "RELEASE_REVIEWER_ID",
            "RELEASE_ADMIN_EVIDENCE",
            "environment_id",
            "reviewer_github_id",
            "writer_app_id",
            "ruleset_ids",
            "evidence_ref",
            "stable",
            "Suppacha/team-engineering-skills-plugin",
            "daily",
        ):
            with self.subTest(value=value):
                self.assertIn(value, admin)
        self.assertRegex(admin, r"(?i)NOT ACTIVATED|ยังไม่เปิดใช้งาน")
        self.assertRegex(admin, r"(?i)company Workspace")
        self.assertRegex(admin, r"(?i)human.*live|คน.*live|คน.*สถานะจริง")

    def test_stable_is_bootstrapped_only_by_an_approved_first_promotion(self):
        admin = self.read("docs/AUTO_UPDATE_ADMIN_TH.md")
        sequence = (
            "ตั้ง protections และ Admin evidence",
            "reviewed main SHA",
            "exact three-OS CI",
            "first approved promotion",
            "ตรวจ `stable` ref และ release record",
            "จึง import",
        )
        positions = [admin.index(step) for step in sequence]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("ห้ามสร้าง `stable` ว่าง", admin)
        self.assertIn("Metadata: read", admin)
        self.assertIn("Actions: read", admin)
        self.assertIn("Environments: read", admin)
        self.assertRegex(admin, r"Environments: read.*เกิน.*endpoint")

    def test_first_promotion_preserves_the_runtime_baseline_ancestry(self):
        admin = self.read("docs/AUTO_UPDATE_ADMIN_TH.md")
        baseline = "6ca868dbccba7d2e2f15dfd5cc6ac105980a8b13"
        self.assertIn(baseline, admin)
        self.assertIn("git merge-base --is-ancestor", admin)
        self.assertRegex(admin, r"(?i)ห้าม.*squash|squash.*ห้าม")
        self.assertRegex(admin, r"(?i)missing history|history.*หาย")
        self.assertRegex(admin, r"(?i)baseline correction|แก้.*baseline")
        self.assertRegex(admin, r"(?i)ไม่.*ลด.*gate|ห้าม.*ลด.*gate")

    def test_migration_is_explicit_and_does_not_destroy_local_state(self):
        admin = self.read("docs/AUTO_UPDATE_ADMIN_TH.md")
        for concept in ("ZIP", "ชื่อซ้ำ", "backup", "project", "uninstall", "disable"):
            with self.subTest(concept=concept):
                self.assertIn(concept, admin)
        self.assertRegex(admin, r"(?i)merge")
        self.assertRegex(admin, r"(?i)ไม่ได้ติดตั้ง|does not install")

    def test_pilot_has_four_blank_native_client_rows_and_required_evidence(self):
        pilot = self.read("docs/AUTO_UPDATE_PILOT_TH.md")
        rows = [line for line in pilot.splitlines() if re.match(r"^\| (Codex|Claude Code) ", line)]
        self.assertEqual(len(rows), 4)
        self.assertTrue(all("NOT RUN" in row for row in rows))
        for value in (
            "Version A",
            "Version B",
            "SHA/source",
            "account scope",
            "automatic check",
            "installed evidence",
            "loaded evidence",
            "session/reload time",
            "limitation",
            "macOS",
            "Windows",
        ):
            with self.subTest(value=value):
                self.assertIn(value, pilot)
        self.assertIn("ไม่ส่ง", pilot)
        self.assertNotRegex(pilot, r"(?i)PASS|ผ่านแล้ว")

    def test_pilot_covers_failure_and_recovery_scenarios_for_every_pair(self):
        pilot = self.read("docs/AUTO_UPDATE_PILOT_TH.md")
        for pair_id in ("C-MAC", "C-WIN", "CC-MAC", "CC-WIN"):
            self.assertIn(f"### {pair_id}", pilot)
            section = pilot.split(f"### {pair_id}", 1)[1].split("### ", 1)[0]
            rows = [line for line in section.splitlines() if re.match(r"^\| S[1-8] ", line)]
            self.assertEqual(len(rows), 8, pair_id)
            self.assertTrue(all("NOT RUN" in row for row in rows), pair_id)
        for phrase in (
            "A → B automatic",
            "offline/reconnect",
            "failed sync",
            "stale session",
            "wrong Workspace/personal account",
            "duplicate source migration",
            "project instruction byte equality",
            "forward recovery",
            "owner acceptance",
        ):
            self.assertIn(phrase, pilot)

    def test_readme_has_pinned_scoped_test_dependency_setup(self):
        readme = self.read("README.md")
        self.assertIn("PyYAML==6.0.2", readme)
        self.assertIn("PYTHON_BIN", readme)
        self.assertIn(".test-venv", readme)
        self.assertIn("macOS", readme)
        self.assertIn("Windows PowerShell", readme)
        self.assertIn("mandatory development/test dependency", readme)
        self.assertIn("optional client validator", readme)
        self.assertNotIn("or PyYAML for the Codex validator", readme)

    def test_user_docs_keep_four_tools_and_separate_version_meanings(self):
        quick = self.read("docs/QUICKSTART_TH.md")
        for heading in ("## Codex", "## ChatGPT", "## Claude", "## Claude Code"):
            self.assertIn(heading, quick)
        for value in ("หลังผู้ดูแลเปิดใช้งานและผ่าน pilot", "ZIP", "installed", "loaded", "package", "Skill", "project snapshot"):
            with self.subTest(value=value):
                self.assertIn(value, quick)
        self.assertIn("AUTO_UPDATE_ADMIN_TH.md", self.read("README.md"))
        self.assertIn("AUTO_UPDATE_PILOT_TH.md", self.read("docs/MANUAL_SOURCES_TH.md"))

    def test_new_relative_markdown_links_resolve(self):
        markdown_link = re.compile(r"\[[^]]+\]\(([^)]+)\)")
        for relative in (
            "README.md",
            "docs/QUICKSTART_TH.md",
            "docs/MANUAL_SOURCES_TH.md",
            "docs/AUTO_UPDATE_ADMIN_TH.md",
            "docs/AUTO_UPDATE_PILOT_TH.md",
        ):
            path = ROOT / relative
            for target in markdown_link.findall(path.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (path.parent / target.split("#", 1)[0]).resolve()
                self.assertTrue(resolved.exists(), f"missing link from {relative}: {target}")


if __name__ == "__main__":
    unittest.main()
