"""V2.1 contracts for the repository-owned team workflow skills."""

import csv
import hashlib
from html import unescape
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/team-engineering-skills"
SKILLS = PLUGIN / "skills"
LOCK = ROOT / "config/skills-lock.json"
NEW_SKILLS = {
    "requirement-analysis",
    "ui-design-specification",
    "test-case-design",
}
SCENARIO_HEADERS = [
    "Issue Key to Link", "User story", "Issue Link Type", "Issue Type",
    "Scenario ID", "TOR", "Summary", "Component", "Module / Feature",
    "Preconditions", "Scenario Name", "Test Data", "Expected Result",
    "Priority", "Remarks", "Scenario Status", "Upload jira",
]
CASE_HEADERS = [
    "Issue Type", "Scenario ID", "TOR", "Scenario Name", "Test Case ID",
    "Parent", "Test Case Type", "Summary", "Test Case Name",
    "Preconditions", "Test Steps", "Expected Result", "Test Data",
    "Actual Result", "Remarks", "Component", "Module / Feature", "Platform",
    "Test Case Priority", "Test Type", "Environment", "Tested By",
    "Test Date", "Scenario Status", "Upload jira",
]
LOCAL_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")


def load_module(relative_path, name):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tree_digest(root):
    result = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).parts):
        if path.is_file():
            result.update(path.relative_to(root).as_posix().encode("utf-8"))
            result.update(b"\0")
            result.update(hashlib.sha256(path.read_bytes()).digest())
    return result.hexdigest()


def read_csv_rows(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.reader(stream))


def workbook_rows(path):
    """Return ordered sheet names and rows without optional XML dependencies."""
    def attrs(fragment):
        return {
            key: unescape(value)
            for key, value in re.findall(r'([\w:]+)="([^"]*)"', fragment)
        }

    def text_nodes(fragment):
        return "".join(
            unescape(re.sub(r"<[^>]+>", "", value))
            for value in re.findall(
                r"<(?:\w+:)?t(?:\s[^>]*)?>(.*?)</(?:\w+:)?t>", fragment, re.DOTALL
            )
        )

    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            xml = archive.read("xl/sharedStrings.xml").decode("utf-8")
            shared = [
                text_nodes(item)
                for item in re.findall(
                    r"<(?:\w+:)?si(?:\s[^>]*)?>(.*?)</(?:\w+:)?si>", xml, re.DOTALL
                )
            ]

        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        rels = archive.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        targets = {
            fields["Id"]: fields["Target"]
            for fields in (
                attrs(fragment)
                for fragment in re.findall(r"<Relationship\b([^>]*)/>", rels)
            )
        }
        result = {}
        for sheet_fragment in re.findall(r"<(?:\w+:)?sheet\b([^>]*)/>", workbook):
            sheet = attrs(sheet_fragment)
            name = sheet["name"]
            target = targets[sheet["r:id"]].lstrip("/")
            member = target if target.startswith("xl/") else f"xl/{target}"
            xml = archive.read(member).decode("utf-8")
            rows = []
            for row in re.findall(
                r"<(?:\w+:)?row\b[^>]*>(.*?)</(?:\w+:)?row>", xml, re.DOTALL
            ):
                values = []
                for cell_fragment, cell_body in re.findall(
                    r"<(?:\w+:)?c\b([^>]*)>(.*?)</(?:\w+:)?c>", row, re.DOTALL
                ):
                    kind = attrs(cell_fragment).get("t")
                    value_match = re.search(
                        r"<(?:\w+:)?v>(.*?)</(?:\w+:)?v>", cell_body, re.DOTALL
                    )
                    if kind == "inlineStr":
                        values.append(text_nodes(cell_body))
                    elif value_match is None:
                        values.append("")
                    elif kind == "s":
                        values.append(shared[int(value_match.group(1))])
                    else:
                        values.append(unescape(value_match.group(1)))
                rows.append(values)
            result[name] = rows
        return result


class TeamWorkflowPackageTests(unittest.TestCase):
    def test_three_workflow_skills_are_standalone_and_locally_linked(self):
        for name in NEW_SKILLS:
            with self.subTest(skill=name):
                root = SKILLS / name
                self.assertTrue((root / "SKILL.md").is_file())
                self.assertTrue((root / "agents/openai.yaml").is_file())
                self.assertTrue((root / "assets/templates").is_dir())
                self.assertTrue((root / "examples").is_dir())
                markdown_files = list(root.rglob("*.md"))
                self.assertTrue(markdown_files)
                for markdown in markdown_files:
                    for raw_target in LOCAL_LINK.findall(markdown.read_text(encoding="utf-8")):
                        target = raw_target.split("#", 1)[0].strip("<>")
                        if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                            continue
                        resolved = (markdown.parent / target).resolve()
                        self.assertTrue(resolved.is_relative_to(root.resolve()), raw_target)
                        self.assertTrue(resolved.exists(), raw_target)

                agent = (root / "agents/openai.yaml").read_text(encoding="utf-8")
                self.assertIn("allow_implicit_invocation: true", agent)
                self.assertIn(f"${name}", agent)

    def test_synthetic_examples_form_an_explicit_trace_chain(self):
        example_text = "\n".join(
            path.read_text(encoding="utf-8")
            for name in sorted(NEW_SKILLS)
            for path in sorted((SKILLS / name / "examples").rglob("*"))
            if path.is_file() and path.suffix.lower() in {".md", ".csv"}
        )
        for identifier in ("REQ-001", "UC-001", "UI-001", "TS-001", "TC-001"):
            self.assertIn(identifier, example_text)
        self.assertIn("appointment", example_text.casefold())

    def test_test_design_csv_and_blank_workbook_preserve_compatible_headers(self):
        template_root = SKILLS / "test-case-design/assets/templates"
        scenario_rows = read_csv_rows(template_root / "test-scenario-header.csv")
        case_rows = read_csv_rows(template_root / "test-case-header.csv")
        self.assertEqual(scenario_rows, [SCENARIO_HEADERS])
        self.assertEqual(case_rows, [CASE_HEADERS])

        sheets = workbook_rows(template_root / "test-design-template.xlsx")
        self.assertEqual(list(sheets), ["Test Scenario", "Test Case"])
        self.assertEqual(sheets["Test Scenario"], [SCENARIO_HEADERS])
        self.assertEqual(sheets["Test Case"], [CASE_HEADERS])

        # A reusable design template cannot imply that a test was run or uploaded.
        evidence_columns = {"Actual Result", "Tested By", "Test Date", "Scenario Status", "Upload jira"}
        for sheet_rows in sheets.values():
            self.assertFalse(sheet_rows[1:], "blank workbook must contain headers only")
            self.assertTrue(evidence_columns.intersection(sheet_rows[0]))

    def test_lock_registry_payload_and_candidate_surfaces_agree_on_v2_2(self):
        lock = json.loads(LOCK.read_text(encoding="utf-8"))["skills"]
        registry = json.loads((PLUGIN / "registry.json").read_text(encoding="utf-8"))
        lock_names = {entry["name"] for entry in lock}
        registry_names = {entry["name"] for entry in registry["skills"]}
        payload_names = {path.name for path in SKILLS.iterdir() if path.is_dir()}
        self.assertEqual(lock_names, registry_names)
        self.assertEqual(lock_names, payload_names)
        self.assertEqual(len(lock_names), 15)
        self.assertTrue(NEW_SKILLS.issubset(lock_names))
        for entry in lock:
            if entry["name"] in NEW_SKILLS:
                self.assertEqual(entry["ownership"], "Team-owned")
                self.assertEqual(entry["source"], "Repository-owned canonical skill")
        for entry in registry["skills"]:
            self.assertEqual(entry["tree_sha256"], tree_digest(SKILLS / entry["name"]))
        claude_catalog = json.loads(
            (ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
        )
        candidate_versions = {
            (PLUGIN / "VERSION").read_text(encoding="utf-8").strip(),
            registry["version"],
            json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())["version"],
            json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())["version"],
            next(
                entry["version"]
                for entry in claude_catalog["plugins"]
                if entry["name"] == "team-engineering-skills"
            ),
        }
        self.assertEqual(candidate_versions, {"2.2.0"})

    def test_sync_keeps_repository_owned_skills_without_global_copies(self):
        module = load_module("scripts/sync-skills.py", "sync_skills_v21_test")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            plugin = root / "plugin"
            canonical = plugin / "skills/requirement-analysis"
            canonical.mkdir(parents=True)
            (canonical / "SKILL.md").write_text("repository canonical payload", encoding="utf-8")
            external = root / "global-skills"
            external.mkdir()
            module.plugin_root = plugin
            module.load_lock = lambda: [{
                "name": "requirement-analysis",
                "ownership": "Team-owned",
                "license": "Team-owned",
                "source": "Repository-owned canonical skill",
                "revision": "Repository source",
                "attribution": "Team Engineering Skills Marketplace",
            }]
            with mock.patch.dict("os.environ", {"CODEX_SKILLS_SOURCE": str(external)}):
                module.sync()
            self.assertEqual(
                (canonical / "SKILL.md").read_text(encoding="utf-8"),
                "repository canonical payload",
            )


if __name__ == "__main__":
    unittest.main()
