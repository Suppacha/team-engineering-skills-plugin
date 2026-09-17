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
