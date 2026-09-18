#!/usr/bin/env python3
"""Validate workflow linkage or preview allowlisted metadata, entirely offline."""

import argparse
import json
from pathlib import Path
import re
import sys
import uuid


sys.dont_write_bytecode = True

MAX_INPUT_BYTES = 1024 * 1024
MAX_RECORDS = 10000
LAYERS = ("requirements", "use_cases", "screens", "scenarios", "test_cases")
PREFIXES = {
    "requirements": "REQ",
    "use_cases": "UC",
    "screens": "UI",
    "scenarios": "TS",
    "test_cases": "TC",
}
ID_PATTERN = re.compile(r"[A-Z][A-Z0-9-]{1,63}")
VERSION_PATTERN = re.compile(
    r"(?:unknown|v?[0-9]+(?:\.[0-9]+){0,3}(?:[-+][A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)?)"
)
METADATA_FIELDS = {
    "schema_version",
    "project_id",
    "client",
    "client_version",
    "framework_version",
    "skill_version",
    "task_category",
    "selected_skill",
    "invocation_mode",
    "outcome",
}
CATEGORY_SKILLS = {
    "requirement": "requirement-analysis",
    "ui-design": "ui-design-specification",
    "test-case": "test-case-design",
}


def load_bounded_json(path):
    try:
        size = path.stat().st_size
        if size > MAX_INPUT_BYTES:
            raise ValueError("input is too large; maximum is 1 MiB")
        value = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        raise ValueError("input must be UTF-8 JSON") from error
    except json.JSONDecodeError as error:
        raise ValueError("malformed JSON: " + str(error)) from error
    if not isinstance(value, dict):
        raise ValueError("input JSON must be an object")
    return value


def validate_traceability(payload):
    fields = set(payload)
    if fields != set(LAYERS):
        missing = sorted(set(LAYERS) - fields)
        extra = sorted(fields - set(LAYERS))
        raise ValueError("traceability fields mismatch; missing=%s extra=%s" % (missing, extra))

    records = {}
    record_layers = {}
    for layer_index, layer in enumerate(LAYERS):
        items = payload[layer]
        if not isinstance(items, list):
            raise ValueError(layer + " must be an array")
        if len(items) > MAX_RECORDS:
            raise ValueError(layer + " contains too many records")
        for index, item in enumerate(items):
            location = "%s[%d]" % (layer, index)
            if not isinstance(item, dict):
                raise ValueError(location + " must be an object")
            if set(item) != {"id", "references"}:
                raise ValueError(location + " must contain only id and references")
            identifier = item["id"]
            references = item["references"]
            if not isinstance(identifier, str):
                raise ValueError(location + ".id must be a string")
            expected_prefix = PREFIXES[layer] + "-"
            if not ID_PATTERN.fullmatch(identifier) or not identifier.startswith(expected_prefix):
                raise ValueError(location + ".id must be a bounded " + PREFIXES[layer] + " identifier")
            if identifier in records:
                raise ValueError("duplicate id: " + identifier)
            if not isinstance(references, list):
                raise ValueError(location + ".references must be an array")
            if len(references) > MAX_RECORDS:
                raise ValueError(location + " contains too many references")
            if any(not isinstance(reference, str) for reference in references):
                raise ValueError(location + ".references entries must be strings")
            if any(not ID_PATTERN.fullmatch(reference) for reference in references):
                raise ValueError(location + " contains an invalid reference identifier")
            if len(references) != len(set(references)):
                raise ValueError(location + " contains duplicate references")
            records[identifier] = tuple(references)
            record_layers[identifier] = layer_index

    missing_references = sorted({
        reference
        for references in records.values()
        for reference in references
        if reference not in records
    })
    for identifier, references in records.items():
        for reference in references:
            if reference not in records:
                continue
            if record_layers[reference] >= record_layers[identifier]:
                raise ValueError(
                    "references must point upstream; %s -> %s is unsupported (cycles are unsupported)"
                    % (identifier, reference)
                )

    def ancestors(identifier):
        found = set()
        pending = list(records[identifier])
        while pending:
            reference = pending.pop()
            if reference in records and reference not in found:
                found.add(reference)
                pending.extend(records[reference])
        return found

    covered = set()
    for test_case in payload["test_cases"]:
        covered.update(
            identifier
            for identifier in ancestors(test_case["id"])
            if record_layers[identifier] == 0
        )
    requirements = {record["id"] for record in payload["requirements"]}
    return {
        "linkage_status": "invalid" if missing_references else "valid",
        "missing_references": missing_references,
        "uncovered_requirements": sorted(requirements - covered),
        "business_completeness": "not-assessed",
        "notice": "Linkage validation does not certify requirement quality or business completeness.",
    }


def preview_metadata(payload):
    fields = set(payload)
    if fields != METADATA_FIELDS:
        missing = sorted(METADATA_FIELDS - fields)
        extra = sorted(fields - METADATA_FIELDS)
        raise ValueError("metadata fields mismatch; missing=%s extra=%s" % (missing, extra))
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValueError("schema_version must be integer 1; boolean is not accepted")
    for field in sorted(METADATA_FIELDS - {"schema_version"}):
        if not isinstance(payload[field], str):
            raise ValueError(field + " must be a string")
    try:
        project_id = uuid.UUID(payload["project_id"])
    except (ValueError, AttributeError) as error:
        raise ValueError("project_id must be a random UUID v4") from error
    if project_id.version != 4 or str(project_id) != payload["project_id"]:
        raise ValueError("project_id must be a canonical random UUID v4")
    if payload["client"] not in {"codex", "claude-code"}:
        raise ValueError("client must be codex or claude-code")
    for field in ("client_version", "framework_version", "skill_version"):
        value = payload[field]
        if len(value) > 48 or not VERSION_PATTERN.fullmatch(value):
            raise ValueError(field + " must be a short version identifier or unknown")
    category = payload["task_category"]
    if category not in CATEGORY_SKILLS:
        raise ValueError("task_category is unsupported")
    if payload["selected_skill"] != CATEGORY_SKILLS[category]:
        raise ValueError("selected_skill does not match task category")
    if payload["invocation_mode"] not in {"automatic", "explicit", "unknown"}:
        raise ValueError("invocation_mode is unsupported")
    if payload["outcome"] not in {"pass", "fail", "not-assessed"}:
        raise ValueError("outcome is unsupported")
    return {
        "status": "PREVIEW ONLY",
        "metadata": payload,
        "retention": "undecided",
        "will_persist": False,
        "will_send": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("validate-traceability", "validate bounded artifact identifiers and upstream references"),
        ("preview-metadata", "validate and display an allowlisted metadata event without saving or sending it"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument("--input", required=True, type=Path, help="UTF-8 JSON file (maximum 1 MiB)")
    args = parser.parse_args()
    try:
        payload = load_bounded_json(args.input)
        if args.command == "validate-traceability":
            result = validate_traceability(payload)
        else:
            result = preview_metadata(payload)
    except (ValueError, OSError) as error:
        print("Validation stopped: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.command == "validate-traceability" and result["linkage_status"] == "invalid":
        print("Validation stopped: missing references: " + ", ".join(result["missing_references"]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
