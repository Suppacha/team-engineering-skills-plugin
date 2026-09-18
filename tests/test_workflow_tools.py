"""Behavioral tests for the offline traceability and metadata preview CLI."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "plugins/team-engineering-skills/scripts/team_workflows.py"


class WorkflowToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def run_cli(self, command, payload):
        source = self.root / "input.json"
        if isinstance(payload, bytes):
            source.write_bytes(payload)
        elif isinstance(payload, str):
            source.write_text(payload, encoding="utf-8")
        else:
            source.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(CLI), command, "--input", str(source)],
            capture_output=True,
            text=True,
        )

    @staticmethod
    def valid_traceability():
        return {
            "requirements": [{"id": "REQ-001", "references": []}],
            "use_cases": [{"id": "UC-001", "references": ["REQ-001"]}],
            "screens": [{"id": "UI-001", "references": ["REQ-001", "UC-001"]}],
            "scenarios": [{"id": "TS-001", "references": ["REQ-001", "UI-001"]}],
            "test_cases": [{"id": "TC-001", "references": ["TS-001"]}],
        }

    @staticmethod
    def valid_metadata():
        return {
            "schema_version": 1,
            "project_id": "2dcd63c7-bc7a-4cb4-9162-31c1fbb801d4",
            "client": "codex",
            "client_version": "5.6.1",
            "framework_version": "2.1.0",
            "skill_version": "1.0.0",
            "task_category": "requirement",
            "selected_skill": "requirement-analysis",
            "invocation_mode": "automatic",
            "outcome": "not-assessed",
        }

    def test_valid_trace_chain_reports_linkage_without_semantic_certification(self):
        result = self.run_cli("validate-traceability", self.valid_traceability())
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["missing_references"], [])
        self.assertEqual(report["uncovered_requirements"], [])
        self.assertEqual(report["linkage_status"], "valid")
        self.assertEqual(report["business_completeness"], "not-assessed")

    def test_requirement_without_ui_is_allowed_when_covered_by_tests(self):
        payload = self.valid_traceability()
        payload["screens"] = []
        payload["scenarios"][0]["references"] = ["REQ-001", "UC-001"]
        result = self.run_cli("validate-traceability", payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["uncovered_requirements"], [])

    def test_uncovered_requirements_are_reported_separately(self):
        payload = self.valid_traceability()
        payload["requirements"].append({"id": "REQ-002", "references": []})
        result = self.run_cli("validate-traceability", payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["missing_references"], [])
        self.assertEqual(report["uncovered_requirements"], ["REQ-002"])

    def test_missing_links_and_uncovered_requirements_share_a_structured_report(self):
        payload = self.valid_traceability()
        payload["requirements"].append({"id": "REQ-002", "references": []})
        payload["test_cases"][0]["references"] = ["TS-404"]
        result = self.run_cli("validate-traceability", payload)
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(report["missing_references"], ["TS-404"])
        self.assertEqual(report["uncovered_requirements"], ["REQ-001", "REQ-002"])
        self.assertEqual(report["linkage_status"], "invalid")

    def test_missing_duplicate_and_non_upstream_references_are_rejected(self):
        cases = []
        missing = self.valid_traceability()
        missing["test_cases"][0]["references"] = ["TS-404"]
        cases.append((missing, "missing"))
        duplicate = self.valid_traceability()
        duplicate["requirements"].append({"id": "REQ-001", "references": []})
        cases.append((duplicate, "duplicate"))
        downstream_cycle = self.valid_traceability()
        downstream_cycle["requirements"][0]["references"] = ["TC-001"]
        cases.append((downstream_cycle, "upstream"))
        for payload, error_text in cases:
            with self.subTest(error=error_text):
                result = self.run_cli("validate-traceability", payload)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error_text, result.stderr.casefold())

    def test_malformed_json_shape_and_record_types_are_rejected(self):
        cases = [
            ("{not-json", "json"),
            ([], "object"),
            ({**self.valid_traceability(), "screens": "UI-001"}, "array"),
            ({**self.valid_traceability(), "screens": [{"id": 3, "references": []}]}, "string"),
            ({**self.valid_traceability(), "screens": [{"id": "UI-001", "references": "UC-001"}]}, "array"),
        ]
        for payload, error_text in cases:
            with self.subTest(error=error_text):
                result = self.run_cli("validate-traceability", payload)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error_text, result.stderr.casefold())

    def test_metadata_preview_is_explicitly_non_operational(self):
        metadata = self.valid_metadata()
        result = self.run_cli("preview-metadata", metadata)
        self.assertEqual(result.returncode, 0, result.stderr)
        preview = json.loads(result.stdout)
        self.assertEqual(preview["status"], "PREVIEW ONLY")
        self.assertEqual(preview["retention"], "undecided")
        self.assertFalse(preview["will_persist"])
        self.assertFalse(preview["will_send"])
        self.assertEqual(preview["metadata"], metadata)

    def test_metadata_rejects_extra_private_and_free_text_fields(self):
        for field, value in (
            ("notes", "customer asked for a refund"),
            ("email", "person@example.invalid"),
            ("url", "https://example.invalid/project"),
            ("retention", "forever"),
            ("send", "yes"),
        ):
            with self.subTest(field=field):
                metadata = self.valid_metadata()
                metadata[field] = value
                result = self.run_cli("preview-metadata", metadata)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("extra", result.stderr.casefold())

    def test_metadata_requires_integer_schema_and_string_fields(self):
        cases = [
            ("schema_version", True, "schema_version"),
            ("project_id", 123, "string"),
            ("client", ["codex"], "string"),
            ("outcome", None, "string"),
        ]
        for field, value, error_text in cases:
            with self.subTest(field=field):
                metadata = self.valid_metadata()
                metadata[field] = value
                result = self.run_cli("preview-metadata", metadata)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error_text, result.stderr.casefold())

    def test_metadata_rejects_unbounded_versions_invalid_uuid_and_mismatched_skill(self):
        cases = [
            ("client_version", "release from customer workstation", "version"),
            ("framework_version", "2.1.0" + "x" * 100, "version"),
            ("project_id", "project-name", "uuid"),
            ("selected_skill", "test-case-design", "category"),
        ]
        for field, value, error_text in cases:
            with self.subTest(field=field):
                metadata = self.valid_metadata()
                metadata[field] = value
                result = self.run_cli("preview-metadata", metadata)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error_text, result.stderr.casefold())

    def test_inputs_are_bounded(self):
        result = self.run_cli("validate-traceability", b" " * (1024 * 1024 + 1))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("large", result.stderr.casefold())


if __name__ == "__main__":
    unittest.main()
